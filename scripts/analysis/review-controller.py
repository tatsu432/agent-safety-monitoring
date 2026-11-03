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


def publish_result(root, retention, replacement):
    """Commit only aggregate diagnostics; reference text and record IDs stay private."""
    if command("git", "status", "--porcelain"):
        raise ValueError(
            "Analysis checkout has uncommitted changes; refusing automatic report commit"
        )
    output = root / "docs/reports"
    atomic_json(output / "model-evidence-retention.json", retention)
    if replacement is not None:
        atomic_json(output / "model-evidence-replacement.json", replacement)
    lines = [
        "# Exploratory model-based evidence review",
        "",
        f"The local 120B reviewer produced {retention['model_proposals']} validated proposals "
        f"and {retention['model_supported_records']} supported interpretations.",
        "All references are model-suggested, not human-verified. Exact source-span validation "
        "does not establish semantic correctness. The sample contains 30 selected attacks.",
        "",
        "| Method | References | Fully retained | Partly retained | Missing | Cited |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, values in sorted(retention["methods"].items()):
        fields = [values.get(key, "not applicable") for key in ["full", "partial", "missing"]]
        lines.append(
            f"| {method.split('-')[0]} | {values['references']} | {fields[0]} | {fields[1]} "
            f"| {fields[2]} | {values['cited']} |"
        )
    lines += [
        "",
        "Exact quotation containment applies only to EaE; citation omission does not "
        "prove misunderstanding. The reviewer selects passages up to 800 characters, so "
        "partial coverage may still include the decisive content. Retention is conditional "
        "on the model's fallible references. Cited counts match source steps, not necessarily "
        "the specific span within each cited step.",
    ]
    if replacement is not None:
        delta, ci = replacement["mean_alert_change"], replacement["ci95"]
        lines += [
            "",
            "## Evidence replacement",
            "",
            f"Eligible selected records: {replacement['eligible_records']}; "
            f"task groups: {replacement['tasks']}. Status counts: "
            f"{json.dumps(replacement['status_counts'], sort_keys=True)}.",
        ]
        if delta is not None and ci is not None:
            lines.append(
                f"Mean expected-alert change: {100 * delta:.1f} percentage points "
                f"(pointwise 95% task-bootstrap interval {100 * ci[0]:.1f} to "
                f"{100 * ci[1]:.1f})."
            )
        lines.append(
            "This is a selected-sample, post-hoc diagnostic using the original policy, "
            "not a full-system TPR or a human-verified evidence study."
        )
    else:
        lines += [
            "",
            "No supported reference sets were available; evidence replacement was not run.",
        ]
    (output / "model-evidence-results.md").write_text("\n".join(lines) + "\n")
    for name in ["eae-failure-analysis.md", "report-draft.md"]:
        path = output / name
        previous = path.read_text()
        path.write_text(
            "> **Evidence-review update:** The model-based diagnostic has completed. "
            "See [its aggregate results](model-evidence-results.md); earlier pending-status "
            "statements below are historical. References remain model-suggested.\n\n" + previous
        )
    files = [
        "docs/reports/model-evidence-results.md",
        "docs/reports/model-evidence-retention.json",
        "docs/reports/eae-failure-analysis.md",
        "docs/reports/report-draft.md",
    ]
    if replacement is not None:
        files.append("docs/reports/model-evidence-replacement.json")
    command("git", "add", *files)
    command(
        "git",
        "-c",
        "user.name=Codex",
        "-c",
        "user.email=codex@localhost",
        "commit",
        "-m",
        "Report exploratory model evidence diagnostics",
    )


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
        dev = base / "development-repair-2"
        proof = base / "repair-2-development-accepted.json"
        accepted = accept_development(
            dev / "summary.json", dev / "jobs" / args.prior_job / "runtime.json", sacct_path, proof
        )
        minutes = max(30, min(240, math.ceil(elapsed * 10 * 1.35 / 60 + 5)))
        env.update(
            ASM_REVIEW_PACKET=str(base / "diagnostic-review-repair-2.json"),
            ASM_REVIEW_OUTPUT=str(base / "diagnostic-repair-2"),
            ASM_REVIEW_PROOF=str(proof),
        )
        identity, script = (
            "model-review-diagnostic-repair-2",
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
        diag = base / "diagnostic-repair-2"
        summary = read_json(diag / "summary.json")
        if summary["completed"] != summary["expected"] or summary["expected"] != 30:
            raise SystemExit("Diagnostic sample is incomplete")
        retention = annotation_retention(
            data, run_root, freeze, diag, base / "retention-aggregate.json"
        )
        if retention["model_supported_records"] == 0:
            publish_result(root, retention, None)
            atomic_json(
                status_path,
                {
                    "phase": args.phase,
                    "state": "complete_no_supported_references",
                    "prior_job": args.prior_job,
                },
            )
            print(json.dumps({"event": "complete_no_supported_references"}), flush=True)
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
        retention = read_json(base / "retention-aggregate.json")
        publish_result(root, retention, result)
        atomic_json(
            status_path,
            {
                "phase": args.phase,
                "state": "complete",
                "prior_job": args.prior_job,
                "eligible_records": result["eligible_records"],
            },
        )
        print(json.dumps({"event": "complete", "prior_job": args.prior_job}), flush=True)
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
    print(
        json.dumps(
            {
                "event": "submitted",
                "job_id": job_id,
                "controller_job": controller.split(";")[0],
                "next_phase": next_phase,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        status = Path("runs/model-review/continuation-status.json")
        previous = read_json(status) if status.exists() else {}
        atomic_json(
            status, {**previous, "state": "controller_failed", "error_type": type(exc).__name__}
        )
        print(
            json.dumps({"event": "controller_failed", "error_type": type(exc).__name__}), flush=True
        )
        raise
