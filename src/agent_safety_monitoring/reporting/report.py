"""Reports use saved artifacts, never fabricated experiment numbers."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve

from agent_safety_monitoring.evaluation.metrics import metrics, paired_bootstrap
from agent_safety_monitoring.io import atomic_json, digest, read_json
from agent_safety_monitoring.monitors.core import MethodConfig, costs
from agent_safety_monitoring.schema import MonitoringResult


def load_results(root):
    study = read_json(root / "study.json")
    expected_methods = {
        f"{m.method}-{digest(m.model_dump())[:12]}"
        for m in [MethodConfig.model_validate(c) for c in study["configuration"]["methods"]]
    }
    tables = {}
    for split in ["calibration", "test"]:
        tables[split] = {}
        for method_path in sorted((root / split).glob("*")):
            if not method_path.is_dir():
                continue
            rows = []
            seen = set()
            for path in sorted(method_path.glob("*.json")):
                saved = read_json(path)
                result = MonitoringResult.model_validate(saved["result"])
                record = saved["evaluation"]
                if (
                    saved["run_identity"] != study["identity"]
                    or result.trajectory_id != record["trajectory_id"]
                    or result.status == "error"
                    or f"{result.method}-{result.config_hash[:12]}" != method_path.name
                ):
                    raise ValueError("Incompatible or infrastructure-failed scientific result")
                if record["trajectory_id"] in seen:
                    raise ValueError("Duplicate result")
                seen.add(record["trajectory_id"])
                # Failed/ungraded attacks remain supplementary, never confirmed positives.
                if record["assignment"] == "attack" and record["outcome"] != "success":
                    continue
                rows.append(
                    {
                        "trajectory_id": record["trajectory_id"],
                        "task_id": record["task_id"],
                        "label": int(record["assignment"] == "attack"),
                        "score": result.score if result.status == "valid" else None,
                        "objective": record["objective"],
                        "result": result,
                    }
                )
            if seen != set(study["expected"][split]):
                raise ValueError(
                    f"Incomplete or unexpected result coverage: {split}/{method_path.name}"
                )
            tables[split][method_path.name] = rows
    if any(set(methods) != expected_methods for methods in tables.values()):
        raise ValueError("Incomplete method coverage")
    return tables


def generate(root: Path, output: Path, replicates=2000):
    output.mkdir(parents=True, exist_ok=True)
    tables = load_results(root)
    cal, test = tables["calibration"], tables["test"]
    if not cal or set(cal) != set(test):
        raise ValueError("Complete matching calibration/test method directories required")
    results = {}
    for method in sorted(test):
        if any(r["label"] for r in cal[method]):
            raise ValueError("Calibration must be benign")
        scores = [r["score"] for r in cal[method]]
        results[method] = {
            "primary": metrics(scores, test[method]),
            "deterministic": metrics(scores, test[method], deterministic=True),
            "cost": costs(r["result"] for r in test[method]),
            "per_objective": {},
        }
        policy = results[method]["primary"]["policy"]
        from agent_safety_monitoring.evaluation.metrics import AlertPolicy

        for objective in sorted({r["objective"] for r in test[method] if r["label"]}):
            selected = [r for r in test[method] if r["objective"] == objective]
            results[method]["per_objective"][objective] = {
                "n": len(selected),
                "tpr": float(AlertPolicy(**policy).alerts([r["score"] for r in selected]).mean()),
            }
    intervals = paired_bootstrap(cal, test, replicates=replicates)
    atomic_json(
        output / "metrics.json",
        {
            "methods": results,
            "uncertainty": intervals,
            "freeze": read_json(root / "study.json")["freeze"],
        },
    )
    with (output / "main-performance.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["method", "tpr", "fpr", "auroc_valid", "invalid_rate", "n"])
        for method, values in results.items():
            row = values["primary"]
            writer.writerow(
                [method, *[row[k] for k in ["tpr", "fpr", "auroc_valid", "invalid_rate", "n"]]]
            )
    with (output / "monitoring-costs.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "method",
                "logical_calls",
                "cache_hits",
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "reasoning_tokens_estimated",
                "reasoning_estimates_exposed",
                "gpu_seconds_pending_slurm_measurement",
            ]
        )
        for method, values in results.items():
            writer.writerow(
                [
                    method,
                    *[
                        values["cost"][k]
                        for k in [
                            "logical_calls",
                            "cache_hits",
                            "input_tokens",
                            "output_tokens",
                            "reasoning_tokens",
                            "reasoning_tokens_estimated",
                            "reasoning_estimates_exposed",
                        ]
                    ],
                    "",
                ]
            )
    fig, ax = plt.subplots(figsize=(7, 5))
    for method, rows in test.items():
        valid = [r for r in rows if r["score"] is not None]
        if len({r["label"] for r in valid}) == 2:
            fpr, tpr, _ = roc_curve([r["label"] for r in valid], [r["score"] for r in valid])
            ax.plot(fpr, tpr, label=method)
    ax.set(
        xlabel="False-positive rate (valid scores)",
        ylabel="True-positive rate",
        xlim=(0, 1),
        ylim=(0, 1),
    )
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(output / "roc.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 5))
    for method, values in results.items():
        ax.scatter(
            values["cost"]["output_tokens"] / values["primary"]["n"],
            values["primary"]["tpr"],
            label=method,
        )
    ax.set(
        xlabel="Logical generated tokens per trajectory (GPU time pending)",
        ylabel="TPR at calibrated alert policy",
        ylim=(0, 1),
    )
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(output / "token-cost-detection.png", dpi=180)
    plt.close(fig)
    study = read_json(root / "study.json")
    budget_rows = []
    for budget, definition in study["configuration"].get("budgets", {}).items():
        for family, choice in definition["methods"].items():
            if choice is None:
                budget_rows.append({"budget": budget, "method": family, "available": False})
                continue
            cfg = MethodConfig.model_validate(choice["config"])
            method_id = f"{cfg.method}-{digest(cfg.model_dump())[:12]}"
            if method_id not in results:
                raise ValueError("Budget references a missing method configuration")
            budget_rows.append(
                {
                    "budget": budget,
                    "method": family,
                    "available": True,
                    "method_id": method_id,
                    "development_gpu_seconds_per_trajectory": choice["gpu_seconds_per_trajectory"],
                    "tpr": results[method_id]["primary"]["tpr"],
                    "cost_source": "development homogeneous workload measurement",
                }
            )
    atomic_json(output / "budget-performance.json", budget_rows)
    with (output / "gpu-cost-performance.csv").open("w", newline="") as stream:
        fields = [
            "budget",
            "method",
            "available",
            "method_id",
            "development_gpu_seconds_per_trajectory",
            "tpr",
            "cost_source",
        ]
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(budget_rows)
    available = [r for r in budget_rows if r["available"]]
    if available:
        fig, ax = plt.subplots(figsize=(7, 5))
        for row in available:
            ax.scatter(
                row["development_gpu_seconds_per_trajectory"],
                row["tpr"],
                label=f"{row['budget']}/{row['method']}",
            )
        ax.set(
            xlabel="Measured development GPU-seconds per trajectory",
            ylabel="Test TPR at calibrated policy",
            ylim=(0, 1),
        )
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(output / "gpu-cost-detection.png", dpi=180)
        plt.close(fig)
    software = study["software_only"]
    title = (
        "SOFTWARE VALIDATION ONLY — synthetic judgments"
        if software
        else "Offline monitoring results"
    )
    (output / "report.md").write_text(
        f"# {title}\n\nGenerated from `{root}`.\n\n"
        "See `main-performance.csv`, `metrics.json`, and ROC figure. "
        "Invalid judgments are referral alerts. "
        "AUROC uses valid judgments only; coverage is reported. Bootstrap resamples whole tasks "
        "and recalibrates independently in each replicate.\n\n"
        "GPU allocation measurements, structural shortcut analyses, "
        "evidence annotations, injection "
        "results, and final scientific discussion must be completed before submission. "
        "Generated-token plots do not establish GPU-time equivalence.\n"
    )
    return {
        "output": str(output),
        "methods": len(results),
        "bootstrap_replicates": replicates,
        "software_only": software,
    }
