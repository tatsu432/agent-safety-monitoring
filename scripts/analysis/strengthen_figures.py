"""Render result figures from public follow-up aggregates."""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from agent_safety_monitoring.io import read_json


def render(scoring, evidence, output):
    scoring, evidence = read_json(scoring), read_json(evidence)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    def save(figure, name):
        figure.tight_layout()
        for extension in ("png", "pdf"):
            figure.savefig(output / f"{name}.{extension}", dpi=240, bbox_inches="tight")
        plt.close(figure)

    bins = scoring["length"]["bins"]
    labels = []
    for row in bins:
        lo, hi = row["lower_inclusive"], row["upper_exclusive"]
        interval = f"{lo / 1000:.1f}–{hi / 1000:.1f}K" if hi else f"≥{lo / 1000:.1f}K"
        labels.append(f"{interval}\n{row['test_benign']} B / {row['test_successful_attack']} A")
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.0), sharex=True)
    methods = {
        "original-single": "Single",
        "original-think": "Think longer",
        "original-average": "Average ×2",
        "original-eae": "EaE",
        "original-mrt": "MRT",
        "hundred-n5": "Fine ×5",
    }
    x = np.arange(len(bins))
    for name, label in methods.items():
        for ax, metric in zip(axes, ("tpr", "auroc_valid"), strict=True):
            values = [
                row["globally_calibrated"]["point"][name][metric]
                if row["globally_calibrated"] and name not in row["sparse_methods"]
                else None
                for row in bins
            ]
            ax.plot(x, [100 * v if v is not None else np.nan for v in values], "o-", label=label)
    for ax, title, limit in (
        (axes[0], "Expected attack detection (%)", (0, 100)),
        (axes[1], "Valid-score AUROC (%)", (40, 100)),
    ):
        ax.set(xticks=x, xticklabels=labels, ylabel=title, ylim=limit)
        ax.grid(axis="y", alpha=0.25)
    axes[1].legend(fontsize=8, loc="lower right")
    fig.supxlabel("Canonical source tokens and benign / attack counts")
    save(fig, "followup-length")

    fig, axes = plt.subplots(1, 2, figsize=(9.7, 3.5))
    groups = ["benign", "attack"]
    for i, label in enumerate(groups):
        values = evidence["eae"][label]
        axes[0].bar(i, values["mean_quote_tokens_per_accepted_extraction"], color=f"C{i}")
        distribution = np.array(values["quotation_position_quartiles"])
        axes[1].plot(
            range(1, 5),
            100 * distribution / distribution.sum(),
            "o-",
            color=f"C{i}",
            label=label.title(),
        )
    axes[0].axhline(evidence["quote_budget_tokens"], color="0.4", ls="--", label="Budget")
    axes[0].set(xticks=[0, 1], xticklabels=["Benign", "Attack"], ylabel="Mean quote tokens")
    axes[0].legend(fontsize=8)
    axes[1].set(
        xticks=range(1, 5),
        xlabel="Transcript-position quartile",
        ylabel="Share of accepted quotations (%)",
    )
    axes[1].legend(fontsize=8)
    save(fig, "followup-eae-evidence")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("scoring", "evidence", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    render(args.scoring, args.evidence, args.output)
