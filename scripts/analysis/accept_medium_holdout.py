"""Freeze a matched medium-effort comparison after physical pilot and context proof."""

import argparse
from pathlib import Path

from development_diagnostics import FineMonitoringResult

from agent_safety_monitoring.analysis.audit import verify_manifest
from agent_safety_monitoring.experiments.followup import FINE_SYSTEM
from agent_safety_monitoring.experiments.resources import allocation_usage
from agent_safety_monitoring.experiments.runner import source_identity
from agent_safety_monitoring.inference.backend import ModelConfig, Tokenizer
from agent_safety_monitoring.io import FileLock, digest, file_hash, immutable_json, read_json
from agent_safety_monitoring.monitors.core import evidence_payload, prompt
from agent_safety_monitoring.schema import CanonicalTrajectory


def accept(args):
    freeze = read_json(args.original_freeze)
    verify_manifest(freeze)
    pilot = read_json(args.pilot / "summary.json")
    identity = read_json(args.pilot / "identity.json")
    condition = read_json(args.config)["conditions"]["think-hundred"]
    sources = source_identity()
    scientific_sources = {
        "src/agent_safety_monitoring/experiments/followup.py",
        "src/agent_safety_monitoring/inference/backend.py",
        "src/agent_safety_monitoring/monitors/core.py",
        "src/agent_safety_monitoring/schema.py",
        "uv.lock",
    }
    if (
        identity["config"] != condition
        or digest(identity) != pilot["identity"]
        or identity["original_freeze"] != freeze["hash"]
        or pilot["records"] != 40
        or pilot["invalid"] > 2
        or any(identity["sources"][p] != sources[p] for p in scientific_sources)
    ):
        raise ValueError("Fine medium pilot does not physically accept the proposed method")
    ids = read_json(args.pilot_ids)
    if len(set(ids)) != 40 or digest(ids) != identity["screen_sha256"]:
        raise ValueError("Physical pilot screen identity mismatch")
    for uid in ids:
        row = read_json(args.pilot / f"{uid}.json")
        outcome = FineMonitoringResult.model_validate(row["result"])
        if outcome.trajectory_id != uid or row["identity"] != pilot["identity"]:
            raise ValueError("Pilot review artifact does not match the accepted screen")
    slurm = allocation_usage(args.pilot_sacct.read_text())["jobs"]
    if len(slurm) != 1 or slurm[0]["state"] != "COMPLETED" or slurm[0]["gpus"] != 1:
        raise ValueError("A complete one-GPU pilot allocation is required")
    timing = read_json(args.pilot_timing)
    if (
        timing["job_id"] != slurm[0]["job_id"]
        or timing["gpus"] != 1
        or timing["exit_code"] != 0
        or timing["interrupted"]
    ):
        raise ValueError("Pilot timing does not bind to the successful allocation")

    manifest = read_json(args.data / "manifest.json")
    if digest(manifest) != freeze["body"]["dataset_manifest"]:
        raise ValueError("Prepared held-out dataset differs from the freeze")
    model = ModelConfig.model_validate(freeze["body"]["config"]["model"])
    if model.model_dump() != identity["model"] or model.backend != "vllm":
        raise ValueError("Pilot model identity differs")
    expected = {
        split: sorted(
            r["trajectory_id"]
            for r in manifest["records"]
            if (r["split"] == split and not r["exclusion"])
        )
        for split in ("calibration", "test")
    }
    tokenizer = Tokenizer(model)
    maximum = 0
    reserve = 2 * model.max_tokens + 128
    for ids in expected.values():
        for uid in ids:
            path = args.data / "trajectories" / f"{uid}.json"
            if file_hash(path) != freeze["body"]["trajectory_hashes"][uid]:
                raise ValueError("Held-out source differs from the original freeze")
            trajectory = CanonicalTrajectory.model_validate(read_json(path))
            messages = prompt(FINE_SYSTEM, evidence_payload(trajectory))
            maximum = max(maximum, tokenizer.prompt(messages, "medium"))
    if maximum + reserve > model.context_limit:
        raise ValueError("Medium-effort prompt exceeds context with retry reserve")
    cached = pilot["costs"]["cache_hits"]
    per_record = pilot["invocation_workload_seconds"] / (pilot["records"] - cached)
    projected = (per_record * sum(map(len, expected.values())) + timing["startup_seconds"]) * 1.25
    body = {
        "original_freeze": freeze["hash"],
        "condition": "think-hundred",
        "config": condition,
        "model": model.model_dump(),
        "expected": expected,
        "pilot_summary_sha256": file_hash(args.pilot / "summary.json"),
        "pilot_sacct_sha256": file_hash(args.pilot_sacct),
        "pilot_timing_sha256": file_hash(args.pilot_timing),
        "max_prompt_tokens": maximum,
        "retry_reserve_tokens": reserve,
        "projected_remaining_seconds_with_contingency": projected,
        "sources": sources,
        "runner_sha256": file_hash(Path(__file__).with_name("development_diagnostics.py")),
    }
    result = {"hash": digest(body), "body": body}
    with FileLock(args.output.with_suffix(".lock")):
        immutable_json(args.output, result)
    return {
        "freeze": result["hash"],
        "max_prompt_tokens": maximum,
        "estimated_hours": projected / 3600,
        "cohort_counts": {k: len(v) for k, v in expected.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in (
        "original-freeze",
        "pilot",
        "pilot-ids",
        "pilot-sacct",
        "pilot-timing",
        "config",
        "data",
        "output",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    print(accept(parser.parse_args()))
