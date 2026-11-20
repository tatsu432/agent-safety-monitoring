"""One physical cold verification of the selected policy on six development records."""

import argparse
import asyncio
import os
import time
from bisect import bisect_left
from pathlib import Path

from agent_safety_monitoring.analysis.adaptive import continue_review
from agent_safety_monitoring.analysis.audit import verify_manifest
from agent_safety_monitoring.experiments.followup import fine_review
from agent_safety_monitoring.inference.backend import Backend, ModelConfig
from agent_safety_monitoring.io import FileLock, digest, file_hash, immutable_json, read_json
from agent_safety_monitoring.schema import CanonicalTrajectory


async def benchmark(data, frozen, policy, output):
    if int(os.environ.get("SLURM_GPUS_ON_NODE", "0")) != 1:
        raise ValueError("Adaptive timing needs a real one-GPU Slurm allocation")
    frozen = read_json(frozen)
    verify_manifest(frozen)
    config = ModelConfig.model_validate(frozen["body"]["config"]["model"])
    manifest = read_json(data / "manifest.json")
    if digest(manifest) != frozen["body"]["dataset_manifest"]:
        raise ValueError("Data differ from the original freeze")
    policy = read_json(policy)
    if policy["original_freeze"] != frozen["hash"] or not policy["mode"].startswith(
        ("gate-", "sequential-")
    ):
        raise ValueError("Use a development-selected adaptive policy from this study")
    rows = []
    for r in manifest["records"]:
        if r["split"] != "development" or r["exclusion"]:
            continue
        p = data / "trajectories" / f"{r['trajectory_id']}.json"
        rows.append((p.stat().st_size, p))
    rows.sort()
    selected = [rows[round((i + 0.5) * (len(rows) - 1) / 6)][1] for i in range(6)]
    cases = []
    for path in selected:
        if file_hash(path) != frozen["body"]["trajectory_hashes"][path.stem]:
            raise ValueError("Development trajectory differs from freeze")
        cases.append(CanonicalTrajectory.model_validate(read_json(path)))
    identity = digest(
        {
            "policy": policy,
            "cases": [c.id for c in cases],
            "source": file_hash(Path(__file__)),
            "original_freeze": frozen["hash"],
        }
    )
    output.mkdir(parents=True, exist_ok=True)
    with FileLock(output / "timing.lock"):
        if (output / "identity.json").exists():
            raise ValueError("An interrupted cold trial cannot be reused as a cold timing")
        immutable_json(
            output / "identity.json", {"hash": identity, "job_id": os.environ["SLURM_JOB_ID"]}
        )
        comparisons = {}
        for name in (policy["mode"], "fixed-5"):
            backend = Backend(config, output / name / "cache")
            total, calls, invalid = 0, 0, 0
            predicted = 0.0
            start = time.monotonic()
            try:
                for trajectory in cases:
                    scores, reviews = [], []
                    for i in range(5):
                        review = await fine_review(backend, trajectory, 20261028 + i * 100)
                        if review["status"] == "context_overflow" or any(
                            c["cached"] for c in review["calls"]
                        ):
                            raise ValueError("Cold timing contains overflow or a cached call")
                        reviews.append(review)
                        scores.append(review["score"])
                        if not continue_review(scores, name, policy["bands"]):
                            break
                    total += len(reviews)
                    observed_calls = sum(len(r["calls"]) for r in reviews)
                    calls += observed_calls
                    estimate = policy["cost_model"]
                    first_length = reviews[0]["calls"][0]["estimated_input_tokens"]
                    index = bisect_left(estimate["prompt_token_edges"], first_length)
                    predicted += observed_calls * estimate["estimated_gpu_seconds_per_call"][index]
                    invalid += sum(r["score"] is None for r in reviews)
                    immutable_json(output / name / "reviews" / f"{trajectory.id}.json", reviews)
                seconds = time.monotonic() - start
            finally:
                await backend.close()
            comparisons[name] = {
                "workload_h200_seconds": seconds,
                "records": len(cases),
                "reviews": total,
                "physical_calls_with_retries": calls,
                "invalid_reviews": invalid,
                "seconds_per_trajectory": seconds / len(cases),
                "simulated_seconds_per_trajectory": predicted / len(cases),
            }
        report = {
            "version": 1,
            "status": "cold matched development timing",
            "job_id": os.environ["SLURM_JOB_ID"],
            "identity": identity,
            "workload_excludes_startup": True,
            "methods": comparisons,
        }
        immutable_json(output / "timing-aggregate.json", report)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for field in ("data", "frozen", "policy", "output"):
        parser.add_argument(f"--{field}", type=Path, required=True)
    print(asyncio.run(benchmark(**vars(parser.parse_args()))))
