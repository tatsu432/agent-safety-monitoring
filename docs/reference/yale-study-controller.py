#!/usr/bin/env python3
"""Serial, cap-checked continuation of the frozen Yale study, one Slurm job per stage."""

import getpass
import math
import os
import subprocess
from pathlib import Path

from agent_safety_monitoring.experiments.resources import allocation_usage
from agent_safety_monitoring.io import FileLock, atomic_json, digest, now, read_json

ROOT = Path.cwd()
CAP = 90.0
FREEZE = "b86533ed57f70956b55d8a5e26eac1f833dc622ef92b36060e1f71382c70ae5d"
SCRATCH = "/nfs/roberts/scratch/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring"


def next_stage(split, shard):
    if split not in {"calibration", "test"} or not 0 <= shard < 8:
        raise ValueError("Invalid completed shard")
    if shard < 7:
        return split, shard + 1
    return ("test", 0) if split == "calibration" else None


def verify_shard(study_root, split, shard, job_id):
    study = read_json(study_root / "study.json")
    if study["freeze"] != FREEZE:
        raise ValueError("Study freeze mismatch")
    execution = read_json(study_root / f"{split}-execution.json")
    manifest = read_json(study_root / f"{split}-shard-{shard}-manifest.json")
    summary = read_json(study_root / f"{split}-shard-{shard}-summary.json")
    expected = len(manifest["selected"]) * len(study["configuration"]["methods"])
    if (
        execution["shards"] != 8
        or manifest["shards"] != 8
        or manifest["shard"] != shard
        or manifest["identity"] != study["identity"]
        or summary["run_identity"] != study["identity"]
        or str(summary["job_id"]) != str(job_id)
        or summary["state"] != "complete"
        or summary["expected"] != expected
        or summary["completed_results"] != expected
    ):
        raise ValueError("Shard coverage or provenance is incomplete")
    return expected


def gpu_environment(split, shard):
    env = {key: value for key, value in os.environ.items() if not key.startswith("SLURM_")}
    env.update(
        {
            "ASM_SCRATCH": SCRATCH,
            "HF_HOME": SCRATCH + "/huggingface",
            "UV_CACHE_DIR": SCRATCH + "/uv-cache",
            "UV_PROJECT_ENVIRONMENT": SCRATCH + "/frozen-inference-venv",
            "UV_OFFLINE": "1",
            "HF_HUB_OFFLINE": "1",
            "ASM_IMAGE": str(ROOT / "images/vllm-openai-v0.11.0.sif"),
            "ASM_IMAGE_SHA256": "056a8f8f182b1652c88ecf567d11dfa18a5b0a7ddd33d17b3fcc5d5869731c03",
            "ASM_MODEL_REVISION": "6cee5e81ee83917806bbde320786a8fb61efebee",
            "ASM_GPUS": "1",
            "ASM_TP": "1",
            "ASM_CONTEXT": "131072",
            "ASM_CONCURRENCY": "1",
            "ASM_FREEZE": "runs/study-freeze.json",
            "ASM_DATA": "data/prepared",
            "ASM_TRACKING_MODE": "online",
            "ASM_ACTION": "run",
            "ASM_OUTPUT": "runs/study",
            "ASM_SHARDS": "8",
            "ASM_DRAIN_SECONDS": "840",
            "ASM_SPLIT": split,
            "ASM_SHARD": str(shard),
        }
    )
    if split == "injections":
        env.update(ASM_OUTPUT="runs/secondary", ASM_PRIMARY_REPORT="runs/report/metrics.json")
    return env


def output(*args, **kwargs):
    return subprocess.check_output(list(args), text=True, **kwargs).strip()


def submit_next(split, shard):
    """Commit submission intent before sbatch; refuse duplicates and budget oversubscription."""
    job_id = os.environ["SLURM_JOB_ID"]
    identity = (
        "injections-attempt-1" if split == "injections" else f"main-{split}-{shard}-attempt-1"
    )
    token = "asm-" + digest(identity)[:24]
    ledger_path = Path("runs/submissions.json")
    with FileLock(ledger_path.with_suffix(".lock")):
        ledger = read_json(ledger_path)
        sacct = output(
            "sacct",
            "-u",
            getpass.getuser(),
            "-S",
            "2026-10-28",
            "-X",
            "--parsable2",
            "--format=JobID,State,ElapsedRaw,AllocTRES,Comment",
        )
        queue = output("squeue", "-u", getpass.getuser(), "-h", "-o", "%i|%k")
        others = [line for line in queue.splitlines() if line.split("|", 1)[0] != job_id]
        if others:
            raise RuntimeError("Another Slurm job is active; stop and reconcile")
        if (
            token in sacct
            or token in queue
            or any(e["identity"] == identity for e in ledger["submissions"])
        ):
            raise RuntimeError("Prior or ambiguous submission for this identity; reconcile")
        usage = allocation_usage(sacct)
        minutes = min(480, math.floor((CAP - usage["allocated_gpu_hours"]) * 60))
        if minutes < 60:
            raise RuntimeError("Insufficient remaining GPU cap for a useful allocation")
        if split == "injections":
            from agent_safety_monitoring.io import file_hash

            if (
                file_hash(Path("runs/injections.sbatch"))
                != "6ebfa1165e63e3fbac8787475de7462a8298021d0609e84920adfe07561d2008"
            ):
                raise RuntimeError("Injection launcher checksum mismatch")
        script = (
            "runs/injections.sbatch" if split == "injections" else "scripts/yale/inference.sbatch"
        )
        command = [
            "--account=cpsc4710",
            "--partition=gpu_h200",
            "--mem=48G",
            "--cpus-per-task=4",
            f"--output=logs/main-{split}-{shard}-%j.out",
            script,
        ]
        entry = {
            "identity": identity,
            "token": token,
            "state": "submitting",
            "time": now(),
            "gpus": 1,
            "minutes": minutes,
            "usage_before": usage,
            "command_hash": digest(command),
        }
        ledger["submissions"].append(entry)
        atomic_json(ledger_path, ledger)
        response = output(
            "sbatch",
            "--parsable",
            f"--comment={token}",
            "--gpus=1",
            f"--time={minutes}",
            *command,
            env=gpu_environment(split, shard),
        )
        submitted = response.split(";", 1)[0]
        if not submitted.isdecimal():
            raise RuntimeError("Unexpected submission response; reconcile")
        entry.update(job_id=submitted, state="submitted")
        atomic_json(ledger_path, ledger)
    return submitted


def submit_controller(job_id, split, shard):
    env = {key: value for key, value in os.environ.items() if not key.startswith("SLURM_")}
    env.update(ASM_PREV_JOB=str(job_id), ASM_PREV_SPLIT=split, ASM_PREV_SHARD=str(shard))
    return output(
        "sbatch",
        "--parsable",
        "--account=cpsc4710",
        "--cpus-per-task=2",
        "--mem=12G",
        "--time=120",
        f"--dependency=afterany:{job_id}",
        "--output=logs/study-controller-%j.out",
        "runs/study-controller.sbatch",
        env=env,
    )


def main():
    previous, split, shard = (
        os.environ["ASM_PREV_JOB"],
        os.environ["ASM_PREV_SPLIT"],
        int(os.environ["ASM_PREV_SHARD"]),
    )
    state = output(
        "sacct", "-j", previous, "-X", "-n", "-P", "--format=State,ExitCode"
    ).splitlines()
    if not state or state[0] != "COMPLETED|0:0":
        raise RuntimeError(f"Previous allocation {previous} did not complete successfully: {state}")
    if split == "injections":
        frozen = read_json(Path("runs/study-freeze.json"))
        metrics = read_json(Path("runs/secondary/injection-metrics.json"))
        expected = (
            len(frozen["body"]["injections"]["trajectory_ids"])
            * len(frozen["body"]["injections"]["method_hashes"])
            * len(frozen["body"]["injections"]["payloads"])
            * 2
        )
        if metrics["freeze"] != FREEZE or len(metrics["rows"]) != expected:
            raise RuntimeError("Injection results are incomplete or from a different freeze")
        files = list((Path("runs/secondary/injections") / FREEZE).glob("*/*/*.json"))
        if len(files) != expected * 2 or any(
            read_json(p)["result"]["status"] == "error" for p in files
        ):
            raise RuntimeError("Injection variants are incomplete or include infrastructure errors")
        atomic_json(
            Path("runs/study-completion.json"),
            {
                "state": "complete",
                "freeze": FREEZE,
                "injection_job": previous,
                "injection_comparisons": expected,
                "time": now(),
            },
        )
        print(
            f"Completed primary and secondary study: {expected} matched injection comparisons",
            flush=True,
        )
        return
    roots = list(Path("runs/study").glob("*/study.json"))
    if len(roots) != 1:
        raise RuntimeError("Expected exactly one frozen study root")
    root = roots[0].parent
    n = verify_shard(root, split, shard, previous)
    print(f"Verified {split} shard {shard}: {n} persisted judgments", flush=True)
    stage = next_stage(split, shard)
    if stage is None:
        output(".venv/bin/asm", "report", "--run-root", str(root), "--output", "runs/report")
        output(
            ".venv/bin/asm",
            "experiment",
            "structural",
            "--frozen",
            "runs/study-freeze.json",
            "--data",
            "data/prepared",
            "--run-root",
            str(root),
            "--output",
            "runs/structural",
        )
        print("Primary report and structural analysis completed", flush=True)
        stage = ("injections", 0)
    new_job = submit_next(*stage)
    print(f"Submitted {stage[0]} shard {stage[1]} as {new_job}", flush=True)
    controller = submit_controller(new_job, *stage)
    print(f"Submitted dependent controller {controller}", flush=True)


if __name__ == "__main__":
    main()
