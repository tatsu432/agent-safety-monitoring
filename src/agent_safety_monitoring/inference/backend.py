"""One request/cache/retry implementation shared by all monitor stages."""

import asyncio
import json
import time
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from pydantic import Field

from agent_safety_monitoring.io import atomic_json, digest, now, read_json
from agent_safety_monitoring.schema import CallRecord, StrictModel, Usage


class ModelConfig(StrictModel):
    backend: Literal["mock", "vllm"] = "mock"
    model: str = "openai/gpt-oss-20b"
    revision: str = "UNVERIFIED"
    tokenizer_revision: str = "UNVERIFIED"
    engine_version: str = "UNVERIFIED"
    base_url: str = "http://127.0.0.1:8000/v1"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=4096, gt=0)
    context_limit: int = Field(default=131072, gt=0)
    concurrency: int = Field(default=1, gt=0)
    transport_retries: int = Field(default=2, ge=0, le=5)
    timeout_seconds: float = 600


class ContextOverflow(ValueError):
    pass


class Tokenizer:
    def __init__(self, config: ModelConfig):
        self.mock = config.backend == "mock"
        self.tokenizer = None
        if not self.mock:
            from transformers import AutoTokenizer

            if config.tokenizer_revision == "UNVERIFIED":
                raise ValueError("Pin tokenizer revision before real inference")
            self.tokenizer = AutoTokenizer.from_pretrained(
                config.model, revision=config.tokenizer_revision, trust_remote_code=False
            )

    def count(self, text: str) -> int:
        if self.mock:
            return len(text.split())
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def prompt(self, messages: list[dict], effort: str) -> int:
        if self.mock:
            return sum(self.count(m["content"]) + 4 for m in messages) + 4
        return len(
            self.tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, reasoning_effort=effort
            )
        )


class Backend:
    def __init__(self, config: ModelConfig, cache: Path, tokenizer=None, transport=None):
        if config.backend == "vllm" and urlparse(config.base_url).hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError("Benchmark inference must use a local server, not a hosted API")
        self.config = config
        self.cache = cache
        self.tokens = tokenizer or Tokenizer(config)
        self.semaphore = asyncio.Semaphore(config.concurrency)
        self.client = httpx.AsyncClient(timeout=config.timeout_seconds, transport=transport)
        self.locks: dict[str, asyncio.Lock] = {}

    async def close(self):
        await self.client.aclose()

    async def generate(self, messages, schema, stage, seed, effort="low", max_tokens=None):
        limit = max_tokens or self.config.max_tokens
        prompt_tokens = self.tokens.prompt(messages, effort)
        if prompt_tokens + limit > self.config.context_limit:
            raise ContextOverflow(
                f"Complete prompt {prompt_tokens} + reserve {limit} exceeds "
                f"context {self.config.context_limit}"
            )
        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "seed": seed,
            "max_tokens": limit,
            "reasoning_effort": effort,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            },
        }
        identity = {
            "body": body,
            "revision": self.config.revision,
            "tokenizer_revision": self.config.tokenizer_revision,
            "engine_version": self.config.engine_version,
            "backend": self.config.backend,
            "endpoint": self.config.base_url,
        }
        key = digest(identity)
        path = self.cache / f"{key}.json"
        async with self.locks.setdefault(key, asyncio.Lock()):
            if path.exists():
                calls = [CallRecord.model_validate(c) for c in read_json(path)["calls"]]
                # Original usage remains the logical cost; no physical generation occurs.
                return [c.model_copy(update={"cached": True, "stage": stage}) for c in calls]
            calls = []
            for attempt in range(self.config.transport_retries + 1):
                start, clock = now(), time.perf_counter()
                usage = Usage(input_tokens=prompt_tokens)
                output, error, finish = None, None, None
                retryable = False
                async with self.semaphore:
                    try:
                        if self.config.backend == "mock":
                            output = self._mock(messages, schema, seed)
                            usage.output_tokens = self.tokens.count(output)
                            finish = "stop"
                        else:
                            response = await self.client.post(
                                self.config.base_url.rstrip("/") + "/chat/completions", json=body
                            )
                            response.raise_for_status()
                            data = response.json()
                            choice = data["choices"][0]
                            message = choice["message"]
                            output = message.get("content") or ""
                            reasoning_text = message.get("reasoning_content") or message.get(
                                "reasoning"
                            )
                            finish = choice.get("finish_reason")
                            u = data.get("usage", {})
                            usage = Usage(
                                input_tokens=u.get("prompt_tokens", prompt_tokens),
                                output_tokens=u.get("completion_tokens", 0),
                                reasoning_tokens=(u.get("completion_tokens_details") or {}).get(
                                    "reasoning_tokens"
                                ),
                                reasoning_tokens_estimated=(
                                    self.tokens.count(reasoning_text)
                                    if isinstance(reasoning_text, str)
                                    else None
                                ),
                            )
                    except httpx.HTTPStatusError as exc:
                        error = f"HTTP {exc.response.status_code}"  # never response bodies
                        retryable = exc.response.status_code in {429, 500, 502, 503, 504}
                    except httpx.TransportError as exc:
                        error, retryable = type(exc).__name__, True
                    except (ValueError, KeyError, IndexError) as exc:
                        error = type(exc).__name__
                calls.append(
                    CallRecord(
                        key=key,
                        stage=stage,
                        attempt=attempt,
                        started=start,
                        completed=now(),
                        latency_seconds=time.perf_counter() - clock,
                        estimated_input_tokens=prompt_tokens,
                        usage=usage,
                        response=output,
                        error=error,
                        finish_reason=finish,
                    )
                )
                if error is None:
                    atomic_json(path, {"calls": [c.model_dump() for c in calls]})
                    return calls
                if not retryable or attempt == self.config.transport_retries:
                    return calls
                await asyncio.sleep(min(2**attempt, 4))
        return calls

    def _mock(self, messages, schema, seed):
        # Deliberately a software fixture, not an effectiveness simulator.
        payload = json.loads(messages[1]["content"])
        segments = payload.get("segments", [])
        if schema.__name__ == "EvidenceSelection":
            quotes = [{"step": s["id"], "text": s["text"][:400]} for s in segments if s["text"]][:1]
            return json.dumps({"quotes": quotes})
        value = {
            "score": 1 + seed % 5,
            "explanation": "Synthetic mock judgment; no scientific meaning.",
            "citations": [segments[0]["id"]] if segments else [],
        }
        if schema.__name__ == "Summary":
            value["summary"] = "Mock evidence state."
        return json.dumps(value)
