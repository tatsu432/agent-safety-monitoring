"""Homogeneous fixed-hardware workload measurements; cold request caches per trial."""

import os
import time
from pathlib import Path

from agent_safety_monitoring.experiments.runner import run_sync
from agent_safety_monitoring.io import atomic_json, digest, read_json


def benchmark(data: Path, output: Path, configuration: dict, gpus: int, limit: int):
    if configuration["model"].get("backend") != "vllm":
        raise ValueError("GPU workload benchmarks require a real model backend")
    if not os.environ.get("SLURM_JOB_ID"):
        raise ValueError("Run GPU benchmark inside a Slurm allocation")
    if gpus < 1 or limit < 1:
        raise ValueError("Positive GPU count and development limit required")
    trials = []
    for i, method in enumerate(configuration["methods"]):
        trial = {**configuration, "methods": [method]}
        # New output/cache for every method: inference reuse cannot erase measured cost.
        trial_root = output / f"trial-{time.time_ns()}-{i}"
        start = time.perf_counter()
        result = run_sync(data, trial_root, trial, limit=limit)
        elapsed = time.perf_counter() - start
        summary = read_json(Path(result["run_root"]) / "development-shard-0-summary.json")
        completed = result["completed"]
        trials.append(
            {
                "method": method,
                "configuration_hash": digest(trial),
                "run_root": result["run_root"],
                "completed": completed,
                "invalid": result["invalid"],
                "workload_seconds": elapsed,
                "gpus": gpus,
                "gpu_seconds": elapsed * gpus,
                "gpu_seconds_per_trajectory": elapsed * gpus / completed if completed else None,
                "costs": summary["costs"],
            }
        )
        atomic_json(
            output / "pilot-measurements.json",
            {
                "slurm_job_id": os.environ["SLURM_JOB_ID"],
                "trials": trials,
                "startup": "External server startup is recorded by the job wrapper separately.",
                "backend_validated": False,
                "note": (
                    "Review outputs, context extremes, memory and effort controls "
                    "before acceptance."
                ),
            },
        )
    return {"output": str(output / "pilot-measurements.json"), "trials": len(trials)}
