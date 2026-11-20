"""Render the extension cost comparison from aggregate-only inputs."""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from agent_safety_monitoring.io import read_json

LABELS = {
    "fixed-1": "Fixed 1",
    "fixed-2": "Fixed 2",
    "fixed-3": "Fixed 3",
    "fixed-5": "Fixed 5",
    "gate-2": "Gate to 2",
    "gate-3": "Gate to 3",
    "gate-5": "Gate to 5",
    "sequential-5": "Sequential cap 5",
}
OFFSETS = {
    "fixed-1": (4, 5),
    "fixed-2": (4, 5),
    "fixed-3": (4, 5),
    "fixed-5": (-50, 5),
    "gate-2": (-40, -13),
    "gate-3": (5, 5),
    "gate-5": (5, 5),
    "sequential-5": (-28, -13),
}


def render(source, output):
    data = read_json(source)
    metrics = data["operating_points"]
    cost = data["test_cost"]
    fixed = [f"fixed-{n}" for n in (1, 2, 3, 5)]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4), constrained_layout=True)
    for ax, key, y_label in zip(
        axes,
        ("pauc_00_10", "tpr"),
        ("Valid-score pAUC over FPR 0–10%", "Expected detection at 5% calibration target"),
        strict=True,
    ):
        ax.plot(
            [cost[n]["estimated_gpu_seconds"]["mean"] for n in fixed],
            [metrics["point"][n][key] for n in fixed],
            color="#2B5980",
            alpha=0.32,
            zorder=1,
        )
        for name, item in cost.items():
            y = metrics["point"][name][key]
            lo, hi = metrics["intervals"][name][key]["ci95"]
            x = item["estimated_gpu_seconds"]["mean"]
            anchor = name == data["selection"]["primary"]
            color = "#9F4A19" if anchor else "#476F69" if name not in fixed else "#2B5980"
            ax.vlines(x, lo, hi, colors=color, alpha=0.5, linewidth=1.3)
            ax.scatter(x, y, color=color, s=32 if anchor else 23, zorder=3)
            offset = OFFSETS[name]
            if key == "tpr" and name == "gate-3":
                offset = (7, 5)
            ax.annotate(
                LABELS[name],
                (x, y),
                xytext=offset,
                textcoords="offset points",
                fontsize=8,
                color=color,
            )
        ax.set_xlabel("Estimated H200 seconds per trajectory")
        ax.set_ylabel(y_label)
        ax.grid(axis="y", linewidth=0.6, alpha=0.35)
        ax.spines[["top", "right"]].set_visible(False)
    axes[1].set_ylim(bottom=0, top=1)
    fig.suptitle(
        "Adaptive and fixed repeated review on the shared exploratory test cohort",
        x=0.05,
        ha="left",
        fontsize=13,
        fontweight="bold",
    )
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / "adaptive-cost.png", dpi=180)
    fig.savefig(output / "adaptive-cost.pdf", metadata={"CreationDate": None})
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.source, args.output)
