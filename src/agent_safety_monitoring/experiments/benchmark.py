"""Stable, resumable development trials; independent trials intentionally start cold."""

import os
import re
import time
from pathlib import Path

from agent_safety_monitoring.experiments.runner import run_sync, source_identity
from agent_safety_monitoring.io import FileLock, atomic_json, digest, immutable_json, now, read_json


def benchmark(
    data: Path, output: Path, configuration: dict, gpus: int, limit: int, trial_id="default"
):
    if configuration["model"].get("backend") != "vllm":
        raise ValueError("GPU workload benchmarks require a real model backend")
    if not os.environ.get("SLURM_JOB_ID"):
        raise ValueError("Run GPU benchmark inside a Slurm allocation")
    if gpus < 1 or limit < 1 or not re.fullmatch(r"[A-Za-z0-9_-]+", trial_id):
        raise ValueError("Positive GPUs/limit and a simple explicit trial id required")
    allocated = os.environ.get("SLURM_GPUS_ON_NODE", "")
    if not allocated.isdecimal() or int(allocated) != gpus:
        raise ValueError("GPU count must match numeric SLURM_GPUS_ON_NODE")
    if int(os.environ.get("SLURM_JOB_NUM_NODES", "1")) != 1:
        raise ValueError("Homogeneous local-server benchmark requires one allocated node")
    root = output / "trials" / trial_id
    identity = {
        "configuration": configuration,
        "data_manifest": digest(read_json(data / "manifest.json")),
        "sources": source_identity(),
        "gpus": gpus,
        "limit": limit,
    }
    with FileLock(root / ".lock"):
        immutable_json(root / "benchmark.json", identity)
        path = root / "pilot-measurements.json"
        ledger = (
            read_json(path)
            if path.exists()
            else {
                "version": 2,
                "trial_id": trial_id,
                "trials": [],
                "backend_validated": False,
                "measurement_identity": digest(identity),
                "note": "Dedicated GPUs times workload wall time; startup separate.",
            }
        )
        for index, method in enumerate(configuration["methods"]):
            if index < len(ledger["trials"]) and ledger["trials"][index]["state"] == "complete":
                continue
            trial = {**configuration, "methods": [method]}
            workload_root = root / f"method-{index}"
            if index == len(ledger["trials"]):
                ledger["trials"].append(
                    {
                        "method": method,
                        "configuration_hash": digest(trial),
                        "state": "pending",
                        "executions": [],
                    }
                )
            row = ledger["trials"][index]
            execution = {"job_id": os.environ["SLURM_JOB_ID"], "started": now(), "state": "running"}
            row["executions"].append(execution)
            row["state"] = "running"
            atomic_json(path, ledger)
            clock = time.perf_counter()
            result = None
            try:
                result = run_sync(data, workload_root, trial, limit=limit)
                execution["state"] = result["state"]
                row.update(
                    run_root=result["run_root"],
                    completed=result["completed"],
                    invalid=result["invalid"],
                    state=result["state"],
                )
                summary = read_json(Path(result["run_root"]) / "development-shard-0-summary.json")
                row["costs"] = summary["costs"]
                execution["resumed"] = result["resumed"]
                execution["cache_hits"] = summary["physical_attempt"].get("cache_hits", 0)
            except BaseException:
                execution["state"] = row["state"] = "failed"
                raise
            finally:
                execution.update(workload_seconds=time.perf_counter() - clock, finished=now())
                elapsed = sum(e.get("workload_seconds", 0) for e in row["executions"])
                clean = (
                    len(row["executions"]) == 1
                    and execution["state"] == "complete"
                    and not execution.get("resumed")
                    and not execution.get("cache_hits")
                )
                row.update(
                    workload_seconds=elapsed,
                    gpus=gpus,
                    gpu_seconds=elapsed * gpus,
                    independent_cold=clean,
                    timing_incomplete=any("finished" not in e for e in row["executions"]),
                    gpu_seconds_per_trajectory=(
                        elapsed * gpus / row["completed"] if row.get("completed") else None
                    ),
                )
                atomic_json(path, ledger)
            if result["state"] != "complete":
                break
            if not result["completed"] or result["invalid"] == result["completed"]:
                raise RuntimeError(
                    "Every development judgment was invalid; diagnose before more GPU use"
                )
        return {
            "output": str(path),
            "trials": len(ledger["trials"]),
            "state": "complete"
            if all(t["state"] == "complete" for t in ledger["trials"])
            and len(ledger["trials"]) == len(configuration["methods"])
            else "incomplete",
        }
