"""Bounded homogeneous cold development timings; never a held-out runner."""

import time

from agent_safety_monitoring.analysis.audit import verify_manifest
from agent_safety_monitoring.experiments.followup import (
    FollowupConfig,
    fine_review,
    protocol_identity,
)
from agent_safety_monitoring.experiments.runner import source_identity
from agent_safety_monitoring.inference.backend import Backend, ModelConfig
from agent_safety_monitoring.io import FileLock, atomic_json, digest, read_json
from agent_safety_monitoring.monitors.core import MethodConfig, Monitor
from agent_safety_monitoring.schema import CanonicalTrajectory


async def benchmark(data, original_freeze, config_path, output, ids_path, gpus):
    import os
    import platform

    if gpus != 1 or int(os.environ.get("SLURM_GPUS_ON_NODE", "0")) != gpus:
        raise ValueError("Real one-GPU Slurm allocation required")
    original = read_json(original_freeze)
    verify_manifest(original)
    config = FollowupConfig.model_validate(read_json(config_path))
    model = ModelConfig.model_validate(original["body"]["config"]["model"])
    if model.backend != "vllm":
        raise ValueError("Physical local vLLM timing required")
    manifest = read_json(data / "manifest.json")
    if digest(manifest) != original["body"]["dataset_manifest"]:
        raise ValueError("Dataset mismatch")
    selected = read_json(ids_path)
    rows = [r for r in manifest["records"] if r["trajectory_id"] in selected]
    if (
        len(rows) != 40
        or len(set(selected)) != 40
        or any(r["split"] != "development" or r["exclusion"] for r in rows)
    ):
        raise ValueError("Exactly 40 distinct eligible development records required")
    identity = {
        "version": 1,
        "client_python_version": platform.python_version(),
        "original_freeze": original["hash"],
        "protocol": protocol_identity(config),
        "sources": source_identity(),
        "model": model.model_dump(),
        "config": config.model_dump(),
        "manifest": digest(manifest),
        "expected": {
            split: sorted(
                r["trajectory_id"]
                for r in manifest["records"]
                if r["split"] == split and not r["exclusion"]
            )
            for split in ("development", "calibration", "test")
        },
    }
    from agent_safety_monitoring.io import file_hash, immutable_json

    with FileLock(output / "timing.lock"):
        immutable_json(output / "identity.json", identity)
        report_path = output / "measurements.json"
        result = (
            read_json(report_path)
            if report_path.exists()
            else {
                "identity": digest(identity),
                "software_only": False,
                "methods": {},
                "cohort_sha256": file_hash(ids_path),
                "definition": "Independent cold homogeneous workload wall time times GPUs; "
                "server startup excluded. Cold trials intentionally regenerate compatible requests "
                "for timing only; scientific inference reuses exact compatible cache entries.",
            }
        )
        for scale in config.score_scales:
            for n in (1, 2, 3, 5):
                name = f"{scale}-n{n}"
                if name in result["methods"]:
                    continue
                trial = output / name
                if trial.exists():
                    raise ValueError("Interrupted cold trial cannot resume as a cold measurement")
                trial.mkdir()
                backend = Backend(model, trial / "cache")
                invalid = 0
                started = time.monotonic()
                try:
                    for row in rows:
                        path = data / "trajectories" / f"{row['trajectory_id']}.json"
                        if (
                            file_hash(path)
                            != original["body"]["trajectory_hashes"][row["trajectory_id"]]
                        ):
                            raise ValueError("Canonical source mismatch")
                        t = CanonicalTrajectory.model_validate(read_json(path))
                        for i in range(n):
                            seed = config.seed + i * config.seed_stride
                            if scale == "five":
                                review = (
                                    await Monitor(backend).run(
                                        t, MethodConfig(method="single", seed=seed)
                                    )
                                ).model_dump()
                            else:
                                review = await fine_review(backend, t, seed)
                            if review["status"] in {"error", "context_overflow"}:
                                raise RuntimeError("Timing infrastructure/context failure")
                            invalid += review["status"] != "valid"
                            atomic_json(trial / "reviews" / f"{t.id}-{i}.json", review)
                    elapsed = time.monotonic() - started
                finally:
                    await backend.close()
                result["methods"][name] = {
                    "gpu_seconds_per_trajectory": elapsed * gpus / len(rows),
                    "workload_seconds": elapsed,
                    "cold_complete": True,
                    "invalid_reviews": invalid,
                    "required_reviews": len(rows) * n,
                    "job_id": os.environ["SLURM_JOB_ID"],
                    "cohort_n": len(rows),
                }
                atomic_json(report_path, result)
        return {"output": str(report_path), "methods": len(result["methods"])}
