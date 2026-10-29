"""Complete tokenizer/chat-template preflight shared by full-record methods."""

from pathlib import Path

from agent_safety_monitoring.inference.backend import ModelConfig, Tokenizer
from agent_safety_monitoring.io import atomic_json, digest, read_json
from agent_safety_monitoring.monitors.core import (
    evidence_payload,
    prompt,
    prompt_identity,
    stage_system,
)
from agent_safety_monitoring.schema import CanonicalTrajectory, EvidenceSelection, Judgment


def audit_context(data: Path, config: ModelConfig):
    if config.backend == "mock":
        raise ValueError("A scientific context audit requires the real tokenizer")
    tokens = Tokenizer(config)
    manifest = read_json(data / "manifest.json")
    records = []
    for record in manifest["records"]:
        t = CanonicalTrajectory.model_validate(
            read_json(data / "trajectories" / f"{record['trajectory_id']}.json")
        )
        payload = evidence_payload(t)
        counts = {
            effort: tokens.prompt(prompt(stage_system(Judgment), payload), effort)
            for effort in ["low", "medium", "high"]
        }
        counts["extract"] = tokens.prompt(
            prompt(stage_system(EvidenceSelection), {**payload, "quote_budget": 3000}), "low"
        )
        # Reserve both one generated answer and a previous maximal corrective answer.
        reserve = 2 * config.max_tokens + 128
        records.append(
            {
                "trajectory_id": t.id,
                "prompt_tokens": counts,
                "source_tokens": sum(tokens.count(s.text) for s in t.segments),
                "reserved_tokens": reserve,
                "fits": max(counts.values()) + reserve <= config.context_limit,
            }
        )
    report = {
        "model": config.model_dump(),
        "manifest_hash": digest(manifest),
        "prompt_hash": prompt_identity(),
        "records": records,
        "total": len(records),
        "overflow": sum(not r["fits"] for r in records),
        "max_prompt_tokens": max(max(r["prompt_tokens"].values()) for r in records),
        "physical_backend_validated": False,
    }
    atomic_json(data / "context-audit.json", report)
    return {k: v for k, v in report.items() if k not in {"records", "model"}}
