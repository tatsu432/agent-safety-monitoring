"""Versioned private view construction and aggregate-only screening of archive evidence."""

import json
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import local
from typing import Literal

import numpy as np

from agent_safety_monitoring.analysis.audit import verify_manifest
from agent_safety_monitoring.experiments.followup import FINE_SYSTEM
from agent_safety_monitoring.inference.backend import ModelConfig, Tokenizer
from agent_safety_monitoring.io import FileLock, digest, file_hash, immutable_json, read_json
from agent_safety_monitoring.monitors.core import (
    chunks,
    evidence_payload,
    extraction_payload,
    prompt,
)
from agent_safety_monitoring.schema import CanonicalTrajectory, Segment, StrictModel

SCHEMA = "reasoning-visibility-v1"
VIEWS = (
    "ACTION_ONLY",
    "REASONING_ONLY",
    "ACTION_PLUS_REASONING",
    "REASONING_MASKED_CONTROL",
)


class UnusableEvidence(ValueError):
    """A fixed exclusion category that can be published without source text."""


class ReasoningSegment(Segment):
    kind: Literal["reasoning", "reasoning_availability"]
    role: Literal["assistant"] = "assistant"


class EvidenceView(CanonicalTrajectory):
    segments: list[ReasoningSegment | Segment]


class ReleaseProof(StrictModel):
    """A reviewed source receipt, approved separately from the mechanical mapping audit."""

    version: Literal[1]
    sources: dict[str, str]
    field: Literal["metadata.control_tower_overlay.actions[].extended_thinking"]
    author: Literal["monitored_agent"]
    representation: Literal["provider_reasoning", "provider_reasoning_or_summary"]
    release_evidence: str

    def verify(self, sources):
        if self.sources != sources or not self.release_evidence.strip():
            raise ValueError("Authorship proof does not cover this release")


def linked_actions(sample):
    """Require a bijection with tool calls in both recorded sequences."""
    actions = (sample.metadata or {}).get("control_tower_overlay", {}).get("actions")
    if not isinstance(actions, list):
        raise UnusableEvidence("missing_overlay")
    visible = [
        (i, call)
        for i, m in enumerate(sample.messages)
        if m.role == "assistant"
        for call in (m.tool_calls or [])
    ]
    generated = [
        call
        for event in sample.events or []
        if event.event == "model"
        for choice in event.output.choices
        if choice.message.role == "assistant"
        for call in (choice.message.tool_calls or [])
    ]
    if len(actions) != len(visible) or len(visible) != len(generated):
        raise UnusableEvidence("link_count")
    ids, indices = set(), []
    result = []
    thinking_messages = set()
    for action, (message, call), event_call in zip(actions, visible, generated, strict=True):
        identifier = action.get("tool_call_id")
        if not identifier or identifier in ids or identifier != call.id or call.id != event_call.id:
            raise UnusableEvidence("ambiguous_call_id")
        if (
            action.get("function") != call.function
            or call.function != event_call.function
            or action.get("arguments") != call.arguments
            or call.arguments != event_call.arguments
        ):
            raise UnusableEvidence("call_payload_mismatch")
        text = action.get("extended_thinking")
        if text is not None and not isinstance(text, str):
            raise UnusableEvidence("reasoning_type")
        if text and text.strip():
            if message in thinking_messages:
                raise UnusableEvidence("ambiguous_multi_call_reasoning")
            thinking_messages.add(message)
        ids.add(identifier)
        indices.append(action.get("index"))
        result.append((message, call.function, text))
    if any(type(i) is not int for i in indices) or sorted(set(indices)) != indices:
        raise UnusableEvidence("nonmonotonic_overlay")
    return result


def restricted_copy(trajectory, linked, tokenizer, maximum=None):
    """Construct payloads for local tokenization. Use a ReleaseProof before materializing."""
    visible = {seg.text.strip() for seg in trajectory.segments if seg.role == "assistant"}
    by_message = defaultdict(list)
    for step in trajectory.segments:
        by_message[step.source_message].append(step)
    real, masked = {}, {}
    for number, (message, function, text) in enumerate(linked):
        if function == "submit" or not text or not text.strip() or text.strip() in visible:
            continue
        if maximum is not None and len(real) >= maximum:
            break
        if message not in by_message:
            raise UnusableEvidence("missing_canonical_anchor")
        anchor = by_message[message][0]
        count = tokenizer.count(text)
        coarse = "1–63" if count < 64 else "64–255" if count < 256 else "256+"
        base = dict(id=f"r{number:05d}", source_message=message, interaction=anchor.interaction)
        real[message] = ReasoningSegment(
            **base,
            text=text,
            kind="reasoning",
            source_end=len(text),
        )
        marker = f"Recorded reasoning present (approximate tokens: {coarse})"
        masked[message] = ReasoningSegment(
            **base,
            text=marker,
            kind="reasoning_availability",
            source_end=len(marker),
        )
    views = {"ACTION_ONLY": trajectory}
    # Strip action-relative position and interaction counts from the reasoning-only payload.
    reasoning_only = [
        step.model_copy(update={"id": f"r{i:05d}", "interaction": i + 1})
        for i, step in enumerate(real.values())
    ]
    views["REASONING_ONLY"] = EvidenceView(
        id=trajectory.id,
        task=trajectory.task,
        segments=reasoning_only,
    )
    for name, additions in (
        ("ACTION_PLUS_REASONING", real),
        ("REASONING_MASKED_CONTROL", masked),
    ):
        segments, seen = [], set()
        for step in trajectory.segments:
            message = step.source_message
            if message in additions and message not in seen:
                segments.append(additions[message])
                seen.add(message)
            segments.append(step)
        views[name] = EvidenceView(id=trajectory.id, task=trajectory.task, segments=segments)
    return views


def context_counts(views, tokens):
    from agent_safety_monitoring.monitors.core import stage_system
    from agent_safety_monitoring.schema import PassageSelection, Summary

    class RecordTokens:
        """Reuse passage token counts across views of the same trajectory."""

        def __init__(self):
            self.counts = {}

        def count(self, text):
            if text not in self.counts:
                self.counts[text] = tokens.count(text)
            return self.counts[text]

    memo = RecordTokens()

    result = {}
    for name, view in views.items():
        counts = {"single": tokens.prompt(prompt(FINE_SYSTEM, evidence_payload(view)), "low")}
        if name != "REASONING_ONLY":
            payload = extraction_payload(view, 3000, memo)
            counts["eae_extract"] = tokens.prompt(
                prompt(stage_system(PassageSelection), payload),
                "low",
            )
            sizes = sorted(
                (
                    len(json.dumps(p, ensure_ascii=True)) + 96
                    for s in payload["segments"]
                    for p in s["text"]
                ),
                reverse=True,
            )
            empty_judge = tokens.prompt(
                prompt(FINE_SYSTEM, {"task": view.task, "quotes": []}), "low"
            )
            counts["eae_judge_upper_bound"] = empty_judge + sum(sizes[:24])
            groups = chunks(view.segments, 5, 12000, memo)
            counts["mrt_leaf"] = max(
                (
                    tokens.prompt(
                        prompt(
                            stage_system(Summary),
                            {
                                **evidence_payload(view, chunk),
                                "summary_budget": 512,
                            },
                        ),
                        "low",
                    )
                    for chunk in groups
                ),
                default=0,
            )
            # JSON-escaped carried state has a greater payload cost than its standalone cap.
            counts["mrt_sequential_upper_bound"] = counts["mrt_leaf"] + 8 * 512 + 128
            counts["mrt_merge_upper_bound"] = empty_judge + 16 * 512 + 512
        result[name] = counts
    return result


def summarize(features):
    groups = defaultdict(list)
    positions = defaultdict(Counter)
    for row in features:
        for dimension in ("assignment", "outcome", "objective", "split"):
            groups[f"{dimension}/{row[dimension] or 'none'}"].append(row)
        groups[f"split_class/{row['split']}/{row['assignment']}"].append(row)
        groups["all"].append(row)
        for action, length in enumerate(row["action_tokens"]):
            position = min(3, 4 * action // len(row["action_tokens"]))
            p = positions[f"{row['split']}/{row['assignment']}/quartile-{position + 1}"]
            p.update(actions=1, with_reasoning=int(length > 0), tokens=length)
    metrics = {}
    for label, rows in groups.items():
        lengths = [n for row in rows for n in row["action_tokens"] if n]
        totals = [sum(row["action_tokens"]) for row in rows]
        fits = [r for r in rows if r["single_cohort"]]
        tasks = defaultdict(list)
        for row in rows:
            tasks[row["task_id"]].append(row)
        task_fractions = [
            sum(r["reasoning_actions"] for r in entries)
            / max(1, sum(len(r["action_tokens"]) for r in entries))
            for entries in tasks.values()
        ]
        metrics[label] = {
            "records": len(rows),
            "tasks": len(tasks),
            "records_with_reasoning": sum(t > 0 for t in totals),
            "actions": sum(len(r["action_tokens"]) for r in rows),
            "actions_with_reasoning": len(lengths),
            "reasoning_token_total": sum(lengths),
            "reasoning_tokens_per_record_quantiles": np.quantile(
                totals, [0, 0.25, 0.5, 0.75, 1]
            ).tolist(),
            "tokens_per_reasoning_action_quantiles": (
                np.quantile(lengths, [0, 0.25, 0.5, 0.75, 1]).tolist() if lengths else None
            ),
            "per_task_action_coverage_quantiles": np.quantile(
                task_fractions,
                [0, 0.25, 0.5, 0.75, 1],
            ).tolist(),
            "single_cohort_records": len(fits),
            "single_cohort_tasks": len({r["task_id"] for r in fits}),
            "max_prompt_tokens": {
                name: max((r["context"].get(name, {}).get("single", 0) for r in rows), default=0)
                for name in VIEWS
            },
        }
    return metrics, {k: dict(v) for k, v in positions.items()}


def _matches_privileged_prompt(sample, view):
    md = sample.metadata or {}
    overlay = md.get("control_tower_overlay", {})
    originals = [overlay.get("system_prompt"), overlay.get("initial_user_message")]
    for metadata in md.get("side_tasks", []):
        originals.extend(metadata.get(k) for k in ("description", "prompt", "instructions"))
    private = [
        s.strip()
        for s in originals
        if isinstance(s, str) and len(s.strip()) >= 40 and s.strip() != view.task.strip()
    ]
    return any(secret in segment.text for secret in private for segment in view.segments)


def audit(
    raw: Path,
    data: Path,
    frozen: Path,
    output: Path,
    proof: Path | None = None,
    *,
    workers=4,
):
    from inspect_ai.log import read_eval_log_samples

    original = read_json(frozen)
    verify_manifest(original)
    manifest = read_json(data / "manifest.json")
    if digest(manifest) != original["body"]["dataset_manifest"]:
        raise ValueError("Prepared manifest differs from original freeze")
    sources = manifest["sources"]
    receipt = ReleaseProof.model_validate(read_json(proof)) if proof else None
    if receipt:
        receipt.verify(sources)
    config = ModelConfig.model_validate(original["body"]["config"]["model"])
    tokenizer = local()
    available = deque(Tokenizer(config) for _ in range(workers))
    rows = {r["trajectory_id"]: r for r in manifest["records"]}
    features, seen, issues = [], set(), Counter()
    reserve = 2 * config.max_tokens + 128

    def initialize_worker():
        tokenizer.tokens = available.popleft()

    def measure(uid, sample):
        tokens = tokenizer.tokens
        row = rows[uid]
        tpath = data / "trajectories" / f"{uid}.json"
        if file_hash(tpath) != original["body"]["trajectory_hashes"][uid]:
            raise ValueError("Canonical trajectory differs from freeze")
        trajectory = CanonicalTrajectory.model_validate(read_json(tpath))
        # Model events support mapping only. Canonical data supplies all visible evidence.
        issue = None
        try:
            links = linked_actions(sample)
            views = restricted_copy(trajectory, links, tokens)
            if _matches_privileged_prompt(sample, views["ACTION_PLUS_REASONING"]):
                raise UnusableEvidence("privileged_source_copy")
        except UnusableEvidence as exc:
            issue = str(exc)
            links, views = [], {}
        counts = context_counts(views, tokens) if views and not row["exclusion"] else {}
        action_tokens = [
            tokens.count(text) if text and text.strip() else 0
            for _, function, text in links
            if function != "submit"
        ]
        single_fit = bool(counts) and all(
            c["single"] + reserve <= config.context_limit for c in counts.values()
        )
        record = {
            **{k: row[k] for k in ("split", "task_id", "assignment", "objective", "outcome")},
            "trajectory_id": uid,
            "action_tokens": action_tokens,
            "reasoning_actions": sum(n > 0 for n in action_tokens),
            "tool_count": sum(seg.kind == "tool_call" for seg in trajectory.segments),
            "context": counts,
            "single_cohort": single_fit,
        }
        if receipt and single_fit:
            hashes = {}
            for name, view in views.items():
                path = output / "views" / name / f"{uid}.json"
                immutable_json(path, view.model_dump())
                hashes[name] = file_hash(path)
            record["view_hashes"] = hashes
        return record, issue

    def collect(future):
        record, issue = future.result()
        features.append(record)
        if issue:
            issues[issue] += 1

    with (
        FileLock(output / "audit.lock"),
        ThreadPoolExecutor(max_workers=workers, initializer=initialize_worker) as pool,
    ):
        pending = deque()
        for filename, sha in sorted(sources.items()):
            path = raw / filename
            if file_hash(path) != sha:
                raise ValueError("Source archive hash differs from the original freeze")
            for sample in read_eval_log_samples(path, resolve_attachments=False):
                uid = digest({"source": sha, "id": str(sample.id), "epoch": sample.epoch})
                if uid not in rows or uid in seen:
                    raise ValueError("Unexpected or duplicate raw record")
                seen.add(uid)
                pending.append(pool.submit(measure, uid, sample))
                if len(pending) >= 2 * workers:
                    collect(pending.popleft())
        for future in pending:
            collect(future)
        if seen != set(rows):
            raise ValueError("Missing archived record")
        metrics, positions = summarize(features)
        private = {"version": SCHEMA, "original_freeze": original["hash"], "features": features}
        immutable_json(output / "features.json", private)
        report = {
            "version": SCHEMA,
            "original_freeze": original["hash"],
            "source_sha256": sources,
            "authorship_verified": receipt is not None,
            "release_proof_sha256": file_hash(proof) if proof else None,
            "record_counts": metrics,
            "position_counts": positions,
            "mapping_exclusions": dict(issues),
            "reserve_tokens": reserve,
            "context_limit": config.context_limit,
            "feature_sha256": digest(private),
            "physical_backend_validated": False,
        }
        immutable_json(output / "audit.json", report)
        return report
