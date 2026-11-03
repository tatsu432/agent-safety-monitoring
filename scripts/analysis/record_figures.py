"""Plot score distributions and per-objective intervals from recovered records."""

import argparse
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from agent_safety_monitoring.analysis.aggregate import NAMES, ORDER
from agent_safety_monitoring.analysis.audit import validate_pairs
from agent_safety_monitoring.analysis.figures import COLORS, save
from agent_safety_monitoring.evaluation.metrics import calibrate
from agent_safety_monitoring.io import read_json
from agent_safety_monitoring.reporting.report import load_results


def generate(run_root, diagnostics, metrics_file, output):
    tables = load_results(run_root)
    validate_pairs(tables)
    metrics, diagnostics = read_json(metrics_file), read_json(diagnostics)
    methods = {name.split("-")[0]: name for name in tables["test"]}
    if set(methods) != set(ORDER) or set(diagnostics["objective_intervals"]) != set(
        methods.values()
    ):
        raise ValueError("Method identities do not match")
    output.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(5, 3, figsize=(12, 13), sharex=True)
    groups = [
        ("calibration", 0, "Calibration benign"),
        ("test", 0, "Test benign"),
        ("test", 1, "Test successful attacks"),
    ]
    for i, family in enumerate(ORDER):
        method = methods[family]
        policy = calibrate([r["score"] for r in tables["calibration"][method]])
        for j, (split, label, title) in enumerate(groups):
            rows = [r for r in tables[split][method] if r["label"] == label]
            valid = [r["score"] for r in rows if r["score"] is not None]
            axes[i, j].hist(
                valid, bins=np.arange(0.75, 5.51, 0.5), color=COLORS[family], edgecolor="white"
            )
            if policy.cutoff is not None:
                axes[i, j].axvline(policy.cutoff, color="black", linestyle="--", linewidth=1)
            axes[i, j].text(
                0.03,
                0.95,
                f"n={len(rows)}; referrals={len(rows) - len(valid)}",
                transform=axes[i, j].transAxes,
                ha="left",
                va="top",
                fontsize=8,
                bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
            )
            if i == 0:
                axes[i, j].set_title(title)
            if j == 0:
                axes[i, j].set_ylabel(f"{NAMES[family]}\nRecords")
            if i == len(ORDER) - 1:
                axes[i, j].set_xlabel("Suspicion score")
    save(fig, output / "score-distributions")
    objectives = sorted(metrics["methods"][methods["single"]]["per_objective"])
    fig, axes = plt.subplots(1, len(objectives), figsize=(14, 5), sharex=True, sharey=True)
    for j, objective in enumerate(objectives):
        ax = axes[j]
        for i, family in enumerate(ORDER):
            method = methods[family]
            point = metrics["methods"][method]["per_objective"][objective]
            ci = diagnostics["objective_intervals"][method][objective]["ci95"]
            if ci is not None:
                ax.plot([100 * ci[0], 100 * ci[1]], [i, i], color=COLORS[family], linewidth=2)
            ax.scatter(100 * point["tpr"], i, color=COLORS[family])
        ax.set_title(objective.replace("_", "\n"))
        ax.set_xlim(0, 100)
        ax.set_xlabel("Expected detection (%)")
        ax.grid(axis="x", alpha=0.2)
    axes[0].set_yticks(range(5), [NAMES[f] for f in ORDER])
    axes[0].invert_yaxis()
    save(fig, output / "per-objective-intervals")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.run_root, args.diagnostics, args.metrics, args.output)


if __name__ == "__main__":
    main()
