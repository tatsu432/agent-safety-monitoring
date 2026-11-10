"""Dependency-triggered continuation using the existing project submission ledger."""

import argparse
import asyncio
import math
import os
import subprocess
from pathlib import Path

from agent_safety_monitoring.experiments.followup import freeze_followup, run_followup, seed_cache
from agent_safety_monitoring.experiments.resources import allocation_usage
from agent_safety_monitoring.io import FileLock, atomic_json, read_json


def command(*args, env=None):
    return subprocess.check_output([str(a) for a in args], text=True, env=env).strip()


def next_phase(phase):
    phases = (
        ["pilot", "timing", "development", "seed-1", "seed-2"]
        + [f"calibration-{i}" for i in range(8)]
        + [f"test-{i}" for i in range(8)]
        + ["review-dev", "review-test", "replacement", "analysis"]
    )
    return phases[phases.index(phase) + 1]


def main(phase, prior):
    root = Path.cwd()
    base = root / "runs/extra-check"
    frozen_root = root.parent / "agent-safety-monitoring-frozen-prep"
    freeze = frozen_root / "runs/study-freeze.json"
    data = root / "data/prepared"
    run_root = frozen_root / (
        "runs/study/5b64a37e16b77e48da4707a5428f3b429cebaafe9b94524660bb9ec5776239d3"
    )
    client = root / ".venv/bin/python"
    config = root / "configs/followup/scoring.json"
    state_path = base / "continuation.json"
    with FileLock(base / "controller.lock"):
        state = read_json(state_path) if state_path.exists() else {"completed": {}, "cap_hours": 90}
        if phase in state["completed"]:
            raise ValueError("Phase already reconciled; inspect ledger instead of submitting again")
        text = command(
            "sacct", "-j", prior, "-X", "--parsable2", "--format=JobID,State,ElapsedRaw,AllocTRES"
        )
        sacct = base / f"{phase}-{prior}-sacct.txt"
        sacct.write_text(text + "\n")
        jobs = allocation_usage(text)["jobs"]
        if len(jobs) != 1 or jobs[0]["job_id"] != prior or jobs[0]["state"] != "COMPLETED":
            raise ValueError("Prior allocation failed/incomplete; reconcile before retrying")
        if phase in {"pilot", "development", "seed-1", "seed-2"} or phase.startswith(
            ("calibration-", "test-")
        ):
            directory = (
                base / phase
                if phase in {"pilot", "development", "seed-1", "seed-2"}
                else base / "scoring"
            )
            split, shard = (
                phase.rsplit("-", 1)
                if phase.startswith(("calibration-", "test-"))
                else ("development", "0")
            )
            summary = read_json(directory / f"{split}-{shard}-summary.json")
            if summary["state"] != "complete" or summary["completed"] != summary["expected"]:
                raise ValueError("Allocation completed without full scientific coverage")
        if phase == "pilot":
            if summary["software_only"] or summary["invalid"] / summary["completed"] > 0.05:
                raise ValueError("Pilot did not meet physical acceptance validity")
            # Verify completed-result restart with generation explicitly forbidden.
            from agent_safety_monitoring.inference.backend import Backend

            original_generate = Backend.generate

            async def forbidden(*args, **kwargs):
                raise RuntimeError("Completed-result replay unexpectedly requested generation")

            Backend.generate = forbidden
            try:
                asyncio.run(run_followup(data, freeze, config, base / "pilot", limit=3))
            finally:
                Backend.generate = original_generate
            atomic_json(
                base / "pilot-resume-check.json",
                {
                    "passed": True,
                    "job_id": prior,
                    "definition": "Completed-result replay; model generation forbidden. "
                    "Not an in-flight GPU interruption experiment.",
                },
            )
            seed_cache(run_root, freeze, data, base / "scoring")
        if phase == "timing":
            measured = read_json(base / "timing/measurements.json")
            if len(measured["methods"]) != 8:
                raise ValueError("All eight homogeneous timing conditions required")
            usage_text = command(
                "sacct",
                "-u",
                os.environ["USER"],
                "-S",
                "2026-10-28",
                "-X",
                "--parsable2",
                "--format=JobID,State,ElapsedRaw,AllocTRES",
            )
            usage = allocation_usage(usage_text)
            m = measured["methods"]
            five = m["five-n5"]["gpu_seconds_per_trajectory"]
            hundred = m["hundred-n5"]["gpu_seconds_per_trajectory"]
            workload = 1038 * (0.6 * five + hundred) + 190 * (five + hundred)
            remaining = workload / 3600 + 2.5  # reviewer, startup and reporting allowance
            cap = 5 * math.ceil((usage["allocated_gpu_hours"] + 1.25 * remaining) / 5)
            # Reuse the predeclared N=5 timing samples for scientific development.
            # Different cold N trials are measurements, not alternate samples to select from.
            import shutil

            cache = base / "development/cache"
            cache.mkdir(parents=True, exist_ok=True)
            imported = 0
            for scale in ("five", "hundred"):
                for source in sorted((base / f"timing/{scale}-n5/cache").glob("*.json")):
                    target = cache / source.name
                    if target.exists() and target.read_bytes() != source.read_bytes():
                        raise ValueError("Conflicting development cache import")
                    if not target.exists():
                        shutil.copy2(source, target)
                        imported += 1
            atomic_json(
                base / "development/cache-provenance.json",
                {
                    "source": "Completed homogeneous N=5 timing trials, chosen in advance",
                    "imported_entries": imported,
                    "timing_identity": measured["identity"],
                },
            )
            state["cap_hours"] = max(state["cap_hours"], cap)
            atomic_json(
                base / "budget-amendment.json",
                {
                    "authority": "User standing authorization; evidence-based agent amendment",
                    "historical_cap_hours": 90,
                    "revised_cap_hours": state["cap_hours"],
                    "consumed_gpu_hours": usage["allocated_gpu_hours"],
                    "projected_remaining_hours": remaining,
                    "contingency_multiplier": 1.25,
                    "measurement_identity": measured["identity"],
                    "note": "Internal accounting cap; not a scheduler resource grant.",
                },
            )
        if phase == "development":
            from agent_safety_monitoring.analysis.followup import select_development

            selection = base / "selection.json"
            select_development(base / "development", base / "timing/measurements.json", selection)
            freeze_followup(
                base / "development",
                base / "context.json",
                base / f"development/jobs/{prior}-followup-runtime.json",
                sacct,
                base / "followup-freeze.json",
                selection,
            )
        if phase == "review-dev":
            from agent_safety_monitoring.analysis.model_review import accept_development

            accept_development(
                base / "review-dev/summary.json",
                base / f"review-dev/jobs/{prior}/runtime.json",
                sacct,
                base / "review-accepted.json",
            )
        if phase in {"review-dev", "review-test"}:
            review_summary = read_json(base / phase / "summary.json")
            if review_summary["completed"] != review_summary["expected"]:
                raise ValueError("Incomplete diagnostic review coverage")
        if phase == "review-test":
            from agent_safety_monitoring.analysis.model_review import annotation_retention

            annotation_retention(
                data,
                run_root,
                read_json(freeze),
                base / "review-test",
                base / "objective-aware-retention.json",
            )
        following = next_phase(phase)
        state["completed"][phase] = {"job_id": prior, "allocation": jobs[0]}
        state["next_phase"] = following
        atomic_json(state_path, state)
        if following == "analysis":
            from agent_safety_monitoring.analysis.followup import report
            from agent_safety_monitoring.analysis.followup_figures import render

            report(base / "scoring", base / "scoring-report.json")
            render(
                base / "scoring-report.json", base / "figures", base / "timing/measurements.json"
            )
            command(client, "scripts/analysis/seed_variability.py", "--base", base)
            state["state"] = "inference_and_aggregate_analysis_complete; synthesis_pending"
            atomic_json(state_path, state)
            return
        env = os.environ.copy()
        for key in ("ASM_LIMIT", "ASM_FOLLOWUP_IDS", "ASM_FOLLOWUP_FREEZE"):
            env.pop(key, None)
        scratch = "/nfs/roberts/scratch/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring"
        env.update(
            ASM_SCRATCH=scratch,
            HF_HOME=f"{scratch}/huggingface",
            UV_CACHE_DIR=f"{scratch}/uv-cache",
            HF_HUB_OFFLINE="1",
            ASM_IMAGE=str(root / "images/vllm-openai-v0.11.0.sif"),
            ASM_IMAGE_SHA256="056a8f8f182b1652c88ecf567d11dfa18a5b0a7ddd33d17b3fcc5d5869731c03",
            ASM_MODEL_REVISION="6cee5e81ee83917806bbde320786a8fb61efebee",
            ASM_GPUS="1",
            ASM_TP="1",
            ASM_CONTEXT="131072",
            ASM_CONCURRENCY="1",
            ASM_FREEZE=str(freeze),
            ASM_FOLLOWUP_CONFIG=str(config),
            ASM_DATA=str(data),
            ASM_TRACKING_MODE="online",
            ASM_ACTION="followup",
            ASM_DRAIN_SECONDS="840",
            ASM_OUTPUT=str(base / following),
            ASM_SPLIT="development",
            ASM_SHARD="0",
            ASM_SHARDS="1",
            ASM_CLIENT_PYTHON=str(client),
        )
        script, minutes = "scripts/yale/inference.sbatch", 480
        if following == "timing":
            env.update(ASM_ACTION="followup-timing", ASM_TIMING_IDS=str(base / "screen-ids.json"))
            minutes = 360
        elif following.startswith("seed-"):
            offset = int(following[-1]) * 10000
            obj = read_json(config)
            obj["seed"] += offset
            seed_config = base / f"{following}-config.json"
            atomic_json(seed_config, obj)
            env.update(
                ASM_FOLLOWUP_CONFIG=str(seed_config), ASM_FOLLOWUP_IDS=str(base / "screen-ids.json")
            )
            minutes = 240
        elif following.startswith(("calibration-", "test-")):
            split, shard = following.rsplit("-", 1)
            env.update(
                ASM_OUTPUT=str(base / "scoring"),
                ASM_SPLIT=split,
                ASM_SHARD=shard,
                ASM_SHARDS="8",
                ASM_FOLLOWUP_FREEZE=str(base / "followup-freeze.json"),
            )
            minutes = 300
        elif following.startswith("review-"):
            script = "scripts/analysis/model-review.sbatch"
            env.update(
                ASM_REVIEW_CONFIG=str(root / "configs/analysis/model-review-repair-2.json"),
                ASM_REVIEW_PACKET=str(
                    base
                    / (
                        "objective-aware-development-packet.json"
                        if following == "review-dev"
                        else "objective-aware-test-packet.json"
                    )
                ),
                ASM_REVIEW_OUTPUT=str(base / following),
            )
            if following == "review-test":
                env["ASM_REVIEW_PROOF"] = str(base / "review-accepted.json")
            minutes = 30 if following == "review-dev" else 120
        elif following == "replacement":
            script, minutes = "scripts/analysis/replacement.sbatch", 30
            env.update(
                ASM_REVIEW_ROOT=str(base / "review-test"),
                ASM_REPLACEMENT_OUTPUT=str(base / "replacement"),
                ASM_RUN_ROOT=str(run_root),
            )
        submission = command(
            client,
            "scripts/yale/submit.py",
            "--ledger",
            "runs/submissions.json",
            "--identity",
            f"extra-check-{following}-1",
            "--gpus",
            "1",
            "--minutes",
            minutes,
            "--cap-hours",
            state["cap_hours"],
            "--controller-self",
            "--",
            "--account=cpsc4710",
            "--partition=gpu_h200",
            "--mem=48G",
            "--cpus-per-task=4",
            f"--output=logs/extra-{following}-%j.out",
            script,
            env=env,
        )
        import json

        job = json.loads(submission)["job_id"]
        controller = command(
            "sbatch",
            "--parsable",
            "--account=cpsc4710",
            "--partition=day",
            "--mem=8G",
            "--cpus-per-task=1",
            "--time=30",
            f"--dependency=afterany:{job}",
            "--output=logs/extra-controller-%j.out",
            "scripts/analysis/followup-controller.sbatch",
            following,
            job,
            env=env,
        )
        state.update(state="running", next_job=job, controller_job=controller.split(";")[0])
        atomic_json(state_path, state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase")
    parser.add_argument("prior_job")
    args = parser.parse_args()
    try:
        main(args.phase, args.prior_job)
    except Exception as exc:
        atomic_json(
            Path("runs/extra-check/controller-failure.json"),
            {
                "phase": args.phase,
                "prior_job": args.prior_job,
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
        )
        raise
