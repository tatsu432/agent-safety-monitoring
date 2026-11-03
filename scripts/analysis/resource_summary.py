"""Export project allocation totals without publishing private accounting logs."""

import argparse
from pathlib import Path

from agent_safety_monitoring.experiments.resources import allocation_usage
from agent_safety_monitoring.io import atomic_json, file_hash, read_json


def summarize(allocation, accounting, followups):
    data = read_json(allocation)
    if data != allocation_usage(accounting.read_text()):
        raise ValueError("Allocation summary does not match Slurm accounting")
    jobs = {j["job_id"]: j for j in data["jobs"]}
    if len(jobs) != len(data["jobs"]) or not set(followups) <= set(jobs):
        raise ValueError("Duplicate jobs or missing follow-up allocations")
    total = sum(j["gpu_seconds"] for j in jobs.values())
    if total != data["allocated_gpu_seconds"]:
        raise ValueError("Allocation total does not match job accounting")
    extra = sum(jobs[j]["gpu_seconds"] for j in followups)
    return {
        "account": "cpsc4710",
        "source_sha256": file_hash(accounting),
        "allocation_count": len(jobs),
        "allocated_gpu_seconds": total,
        "allocated_gpu_hours": total / 3600,
        "documented_cap_hours": 90,
        "follow_up_allocated_gpu_seconds": extra,
        "follow_up_allocated_gpu_hours": extra / 3600,
        "follow_up_allocations": {
            j: {"state": jobs[j]["state"], "gpu_seconds": jobs[j]["gpu_seconds"]} for j in followups
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allocation", type=Path, required=True)
    parser.add_argument("--accounting", type=Path, required=True)
    parser.add_argument("--follow-up", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    atomic_json(args.output, summarize(args.allocation, args.accounting, args.follow_up))


if __name__ == "__main__":
    main()
