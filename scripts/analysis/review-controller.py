"""Slurm-triggered continuation of the independent model evidence diagnostic."""

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

from agent_safety_monitoring.analysis.model_review import accept_development, annotation_retention
from agent_safety_monitoring.io import atomic_json, read_json


def command(*args, env=None):
    return subprocess.check_output(args, text=True, env=env).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", choices=["development", "diagnostic", "replacement"], required=True
    )
    parser.add_argument("--prior-job", required=True)
    args = parser.parse_args()
    root = Path.cwd()
    base = root / "runs/model-review"
    frozen_root = Path(
        "/nfs/roberts/project/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring-frozen-prep"
    )
    data = frozen_root / "data/prepared"
    freeze = read_json(frozen_root / "runs/study-freeze.json")
    run_root = (
        frozen_root / "runs/study/5b64a37e16b77e48da4707a5428f3b429cebaafe9b94524660bb9ec5776239d3"
    )
    status_path = base / "continuation-status.json"
    sacct_text = command(
        "sacct",
        "-j",
        args.prior_job,
        "-X",
        "--parsable2",
        "--format=JobID,State,ElapsedRaw,AllocTRES",
    )
    sacct_path = base / f"{args.phase}-{args.prior_job}-sacct.txt"
    sacct_path.write_text(sacct_text + "\n")
    rows = [line.split("|") for line in sacct_text.splitlines()[1:] if line]
    if len(rows) != 1 or rows[0][0] != args.prior_job or rows[0][1] != "COMPLETED":
        atomic_json(
            status_path,
            {
                "phase": args.phase,
                "prior_job": args.prior_job,
                "state": "blocked",
                "reason": "prior allocation did not complete",
            },
        )
        raise SystemExit("Prior allocation did not complete successfully")
    elapsed = int(rows[0][2])
    env = os.environ.copy()
    if args.phase == "development":
        dev = base / "development-repair-1"
        proof = base / "repair-development-accepted.json"
        accepted = accept_development(
            dev / "summary.json", dev / "jobs" / args.prior_job / "runtime.json", sacct_path, proof
        )
        minutes = max(30, min(240, math.ceil(elapsed * 10 * 1.35 / 60 + 5)))
        env.update(
            ASM_REVIEW_PACKET=str(base / "diagnostic-review-repair.json"),
            ASM_REVIEW_OUTPUT=str(base / "diagnostic-repair-1"),
            ASM_REVIEW_PROOF=str(proof),
        )
        identity, script = (
            "model-review-diagnostic-repair-1",
            "scripts/analysis/model-review.sbatch",
        )
        estimate = {
            "development_gpu_seconds": accepted["allocation_gpu_seconds"],
            "diagnostic_requested_minutes": minutes,
            "assumptions": "30/3 record extrapolation, 35% contingency, 5 min startup",
        }
        atomic_json(base / "diagnostic-resource-plan.json", estimate)
        next_phase = "diagnostic"
    elif args.phase == "diagnostic":
        diag = base / "diagnostic-repair-1"
        summary = read_json(diag / "summary.json")
        if summary["completed"] != summary["expected"] or summary["expected"] != 30:
            raise SystemExit("Diagnostic sample is incomplete")
        retention = annotation_retention(
            data, run_root, freeze, diag, base / "retention-aggregate.json"
        )
        if retention["model_supported_records"] == 0:
            atomic_json(
                status_path,
                {
                    "phase": args.phase,
                    "state": "complete_no_supported_references",
                    "prior_job": args.prior_job,
                },
            )
            return
        env.update(
            ASM_REVIEW_ROOT=str(diag),
            ASM_REPLACEMENT_OUTPUT=str(base / "replacement-1"),
            ASM_FREEZE=str(frozen_root / "runs/study-freeze.json"),
            ASM_DATA=str(data),
            ASM_RUN_ROOT=str(run_root),
        )
        minutes = max(20, min(120, math.ceil(retention["model_supported_records"] * 1.5 + 10)))
        atomic_json(
            base / "replacement-resource-plan.json",
            {
                "supported_records": retention["model_supported_records"],
                "requested_minutes": minutes,
                "assumptions": "1.5 min per supported record plus 10 min startup; exploratory",
            },
        )
        identity, script = "model-review-replacement-1", "scripts/analysis/replacement.sbatch"
        next_phase = "replacement"
    else:
        result = read_json(base / "replacement-1/summary.json")
        atomic_json(
            status_path,
            {
                "phase": args.phase,
                "state": "complete",
                "prior_job": args.prior_job,
                "eligible_records": result["eligible_records"],
            },
        )
        return
    submit = [
        sys.executable,
        "scripts/yale/submit.py",
        "--ledger",
        str(frozen_root / "runs/submissions.json"),
        "--identity",
        identity,
        "--gpus",
        "1",
        "--minutes",
        str(minutes),
        "--cap-hours",
        "90",
        "--controller-self",
        "--",
        "--account=cpsc4710",
        "--partition=gpu_h200",
        "--mem=48G",
        "--cpus-per-task=4",
        f"--output=runs/model-review/logs/{identity}-%j.out",
        script,
    ]
    response = json.loads(command(*submit, env=env))
    job_id = response["job_id"]
    atomic_json(
        status_path,
        {
            "phase": args.phase,
            "state": "submitted",
            "prior_job": args.prior_job,
            "next_job": job_id,
            "next_phase": next_phase,
        },
    )
    controller = command(
        "sbatch",
        "--parsable",
        "--job-name=asm-review-controller",
        "--account=cpsc4710",
        "--partition=education",
        "--cpus-per-task=2",
        "--mem=16G",
        "--time=00:30:00",
        f"--dependency=afterany:{job_id}",
        f"--output=runs/model-review/logs/controller-{next_phase}-%j.out",
        "scripts/analysis/review-controller.sbatch",
        next_phase,
        job_id,
        env=env,
    )
    atomic_json(
        status_path,
        {
            "phase": args.phase,
            "state": "submitted",
            "prior_job": args.prior_job,
            "next_job": job_id,
            "next_phase": next_phase,
            "controller_job": controller.split(";")[0],
        },
    )


if __name__ == "__main__":
    main()
