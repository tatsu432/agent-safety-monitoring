#!/usr/bin/env python3
"""Project-local submission ledger. Run on Yale; secrets belong in environment files."""

import argparse
import getpass
import json
import os
import subprocess
from pathlib import Path

from agent_safety_monitoring.experiments.resources import allocation_usage
from agent_safety_monitoring.io import FileLock, atomic_json, digest, now, read_json


def active_jobs(reserved, controller_self, environment):
    active = reserved.splitlines()
    if controller_self:
        self_id = environment.get("SLURM_JOB_ID")
        if (
            not self_id
            or environment.get("SLURM_JOB_NAME") != "asm-review-controller"
            or environment.get("SLURM_JOB_GPUS") not in (None, "", "N/A")
        ):
            raise ValueError("Controller exemption requires the current CPU controller job")
        active = [job for job in active if job != self_id]
    return active


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument(
        "--identity", required=True, help="Study/split/shard or development trial identity"
    )
    parser.add_argument("--gpus", type=int, required=True)
    parser.add_argument("--minutes", type=int, required=True)
    parser.add_argument("--cap-hours", type=float, required=True)
    parser.add_argument("--since", default="2026-10-28")
    parser.add_argument("--controller-self", action="store_true")
    parser.add_argument("sbatch_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.sbatch_args
    if command and command[0] == "--":
        command = command[1:]
    if args.gpus < 1 or args.minutes < 1 or not command:
        parser.error("Positive resources and sbatch arguments/script required")
    # Explicit time/GPU overrides would defeat the cap check.
    if any(
        v.startswith(("--time", "--gpus", "--gres", "--array", "--nodes"))
        or v.startswith(("-t", "-N", "-a", "-G"))
        for v in command
    ):
        parser.error("Set resources through this wrapper; arrays/multi-node jobs are unsupported")
    user = getpass.getuser()
    sacct_args = [
        "sacct",
        "-u",
        user,
        "-S",
        args.since,
        "-X",
        "--parsable2",
        "--format=JobID,State,ElapsedRaw,AllocTRES,Comment",
    ]
    token = "asm-" + digest(args.identity)[:24]
    with FileLock(args.ledger.with_suffix(".lock")):
        ledger = read_json(args.ledger) if args.ledger.exists() else {"submissions": []}
        records = subprocess.check_output(sacct_args, text=True)
        queued = subprocess.check_output(["squeue", "-u", user, "-h", "-o", "%i|%k"], text=True)
        if any(token in line for line in queued.splitlines()):
            raise SystemExit("Matching job is queued/running; reconcile it before retrying")
        matching = [line for line in records.splitlines() if token in line]
        previous = [r for r in ledger["submissions"] if r["identity"] == args.identity]
        if previous and previous[-1]["state"] == "submitting" and not matching:
            raise SystemExit("Ambiguous submission; reconcile Slurm before ledger repair")
        if matching:
            states = [line.split("|")[1] for line in matching]
            if any(state.startswith("COMPLETED") for state in states):
                raise SystemExit(
                    "Completed allocation exists; inspect coverage before a new attempt"
                )
        usage = allocation_usage(records)
        reserved = subprocess.check_output(
            ["squeue", "-u", user, "-h", "-o", "%i"], text=True
        ).strip()
        active = active_jobs(reserved, args.controller_self, os.environ)
        if active:
            raise SystemExit("Other jobs are active; reconcile reserved budget first")
        if usage["allocated_gpu_hours"] + args.gpus * args.minutes / 60 > args.cap_hours:
            raise SystemExit("Requested allocation exceeds remaining approved total cap")
        entry = {
            "identity": args.identity,
            "token": token,
            "state": "submitting",
            "time": now(),
            "gpus": args.gpus,
            "minutes": args.minutes,
            "usage_before": usage,
            "command_hash": digest(command),
        }
        ledger["submissions"].append(entry)
        atomic_json(args.ledger, ledger)
        response = subprocess.check_output(
            [
                "sbatch",
                "--parsable",
                f"--comment={token}",
                f"--gpus={args.gpus}",
                f"--time={args.minutes}",
                *command,
            ],
            text=True,
        ).strip()
        entry.update(job_id=response.split(";")[0], state="submitted")
        atomic_json(args.ledger, ledger)
        print(json.dumps({"job_id": entry["job_id"], "identity": args.identity}))


if __name__ == "__main__":
    main()
