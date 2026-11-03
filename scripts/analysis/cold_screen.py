"""Verify the accepted development timing source and export only aggregates."""

import argparse
from pathlib import Path

from agent_safety_monitoring.io import atomic_json, file_hash, read_json


def summarize(measurement, acceptance):
    proof = read_json(acceptance)
    if (
        not proof["backend_validated"]
        or file_hash(measurement) != proof["evidence"]["measurement_sha256"]
    ):
        raise ValueError("Cold screen does not match accepted proof")
    data = read_json(measurement)
    if data["trial_id"] != "selected-cold-1":
        raise ValueError("Unexpected development screen identity")
    result = {}
    for trial in data["trials"]:
        family = trial["method"]["method"]
        if (
            family in result
            or trial["state"] != "complete"
            or not trial["independent_cold"]
            or trial["timing_incomplete"]
            or trial["gpus"] != 1
            or trial["completed"] != 40
        ):
            raise ValueError("Cold trial incomplete or duplicated")
        costs = trial["costs"]
        result[family] = {
            "n": trial["completed"],
            "invalid": trial["invalid"],
            "workload_gpu_seconds": trial["gpu_seconds"],
            "gpu_seconds_per_trajectory": trial["gpu_seconds_per_trajectory"],
            **{
                k: costs[k]
                for k in [
                    "logical_calls",
                    "cache_hits",
                    "input_tokens",
                    "output_tokens",
                    "reasoning_tokens_estimated",
                ]
            },
        }
    if set(result) != {"single", "think", "average", "eae", "mrt"}:
        raise ValueError("Missing development method")
    return {
        "source_sha256": file_hash(measurement),
        "acceptance_sha256": file_hash(acceptance),
        "accepted_backend_validated": True,
        "individual_trials": result,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--measurement", type=Path, required=True)
    p.add_argument("--acceptance", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    atomic_json(a.output, summarize(a.measurement, a.acceptance))


if __name__ == "__main__":
    main()
