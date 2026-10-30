"""Explicit allocation accounting and provisional measured-cost projections."""

import csv
import io
from pathlib import Path

from agent_safety_monitoring.io import atomic_json, read_json


def allocation_usage(sacct_text):
    rows = []
    for row in csv.DictReader(io.StringIO(sacct_text.strip()), delimiter="|"):
        tres = dict(item.split("=", 1) for item in row["AllocTRES"].split(",") if "=" in item)
        count = int(tres.get("gres/gpu", 0))
        if not count:
            count = sum(int(v) for k, v in tres.items() if k.startswith("gres/gpu:"))
        if count:
            rows.append(
                {
                    "job_id": row["JobID"],
                    "state": row["State"],
                    "gpus": count,
                    "elapsed_seconds": int(row["ElapsedRaw"]),
                    "gpu_seconds": count * int(row["ElapsedRaw"]),
                }
            )
    if len({r["job_id"] for r in rows}) != len(rows):
        raise ValueError("Use sacct -X without duplicate jobs/steps")
    total = sum(r["gpu_seconds"] for r in rows)
    return {"jobs": rows, "allocated_gpu_seconds": total, "allocated_gpu_hours": total / 3600}


def estimate(measurements: Path, data: Path, output: Path, contingency=0.25):
    source = read_json(measurements)
    records = [r for r in read_json(data / "manifest.json")["records"] if not r["exclusion"]]
    phases = {
        "calibration": sum(r["split"] == "calibration" for r in records),
        "primary_test": sum(
            r["split"] == "test" and (r["assignment"] == "benign" or r["outcome"] == "success")
            for r in records
        ),
        "supplementary_test": sum(
            r["split"] == "test" and r["assignment"] == "attack" and r["outcome"] != "success"
            for r in records
        ),
    }
    methods = []
    for trial in source["trials"]:
        cost = trial.get("gpu_seconds_per_trajectory")
        if cost is None or cost <= 0:
            continue
        methods.append(
            {
                "method": trial["method"],
                "gpu_seconds_per_trajectory": cost,
                "invalid_rate": trial["invalid"] / max(1, trial["completed"]),
                "independent_cold": trial.get("independent_cold"),
                "timing_incomplete": trial.get("timing_incomplete"),
                "phase_gpu_hours": {phase: n * cost / 3600 for phase, n in phases.items()},
            }
        )
    # Provisional projection of the measured configurations, not final budget selection.
    primary = sum(sum(m["phase_gpu_hours"].values()) for m in methods)
    injections = sum(
        m["gpu_seconds_per_trajectory"] * 40 * 3 * 2 * 2 / 3600
        for m in methods
        if m["method"]["method"] in {"single", "eae"}
    )
    components = {
        "measured_configurations_primary_and_supplementary": primary,
        "injections_up_to_40_records": injections,
        "additional_development_assumption": 2.5,
        "startup_assumption_10_jobs_90_seconds": 0.25,
    }
    central = sum(components.values())
    report = {
        "provisional": True,
        "cohort_counts": phases,
        "methods": methods,
        "components_gpu_hours": components,
        "central_gpu_hours": central,
        "conservative_gpu_hours": central * (1 + contingency),
        "contingency_fraction": contingency,
        "limitations": [
            "Uses measured screen mixture; held-out lengths may differ.",
            "Invalid EaE can omit judge cost; retain validity coverage and remeasure cold cost.",
            "Resumed workload costs include all recorded segments; not cold selection proof.",
            "Recalculate after selection; deduplicate shared budget configs.",
            "Retries already present in trials; contingency covers extra failures.",
            "Consumed allocations are separate and are not deducted here.",
        ],
    }
    atomic_json(output, report)
    return report
