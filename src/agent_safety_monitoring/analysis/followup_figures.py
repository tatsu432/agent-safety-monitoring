"""Publication figures from validated aggregate follow-up artifacts only."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from agent_safety_monitoring.io import read_json


def render(source: Path, output: Path, measurements: Path | None = None):
    data = read_json(source)
    scoring = data["scoring"]
    output.mkdir(parents=True, exist_ok=True)
    ns = [1, 2, 3, 5]
    saved = []
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    def finish(fig, name):
        fig.tight_layout()
        for extension in ("png", "pdf"):
            path = output / f"{name}.{extension}"
            fig.savefig(path, dpi=300, bbox_inches="tight")
            saved.append(str(path))
        plt.close(fig)

    def values(scale):
        names = [f"{scale}-n{n}" for n in ns]
        y = np.array([scoring["point"][name]["tpr"] for name in names])
        ci = np.array([scoring["intervals"][name]["tpr"]["ci95"] for name in names])
        return y, ci

    fig, ax = plt.subplots(figsize=(6, 4))
    for scale, label in (("five", "Five categories"), ("hundred", "0–100 ordinal")):
        y, ci = values(scale)
        ax.plot(ns, 100 * y, "o-", label=label)
        ax.fill_between(ns, 100 * ci[:, 0], 100 * ci[:, 1], alpha=0.15)
    ax.set(
        xlabel="Independent reviews (nested samples)",
        ylabel="Expected attack detection (%)",
        xticks=ns,
        ylim=(0, 100),
        title="Exploratory · separate 5% calibration target",
    )
    ax.legend()
    finish(fig, "followup-detection-reviews")

    fig, ax = plt.subplots(figsize=(6, 4))
    width = 0.18
    for i, scale in enumerate(("five", "hundred", "hundred-binned", "hundred-bin-first")):
        y, _ = values(scale)
        ax.bar(np.arange(4) + i * width, 100 * y, width, label=scale)
    ax.set(
        xticks=np.arange(4) + 1.5 * width,
        xticklabels=ns,
        xlabel="Reviews",
        ylabel="Expected attack detection (%)",
        title="Exploratory · score-resolution sensitivity",
    )
    ax.legend(fontsize=8)
    finish(fig, "followup-resolution")

    fig, ax = plt.subplots(figsize=(6, 4))
    for name, curve in data["roc_curves"].items():
        if name.startswith(("five-n", "hundred-n")):
            ax.plot(curve["fpr"], curve["tpr"], label=name)
    ax.plot([0, 0.1], [0, 0.1], color="grey", linestyle=":")
    ax.set(
        xlim=(0, 0.1),
        ylim=(0, 1),
        xlabel="Test FPR (valid scores)",
        ylabel="Test TPR (valid scores)",
        title="Exploratory · descriptive test ROC",
    )
    ax.legend(fontsize=8)
    finish(fig, "followup-low-fpr-roc")

    fig, axes = plt.subplots(2, 2, figsize=(9, 6))
    for ax, name in zip(axes.flat, ("five-n1", "five-n5", "hundred-n1", "hundred-n5"), strict=True):
        d = data["distributions"]["test"][name]
        for label, rows in d["histogram_by_label"].items():
            if rows:
                x, y = np.array(rows).T
                ax.plot(x, y / max(y.sum(), 1), "o-", label="Attack" if label == "1" else "Benign")
        ax.set(
            xlabel="Ordinal score",
            ylabel="Fraction within valid class",
            title=f"{name}: {d['unique_scores']} scores; invalid {d['invalid']}/{d['n']}",
        )
        ax.legend(fontsize=8)
    fig.suptitle("Exploratory · score distributions and ties", y=1.03)
    finish(fig, "followup-distributions")

    fig, ax = plt.subplots(figsize=(6, 4))
    for scale in ("five", "hundred"):
        rows = [data["marginal"][f"{scale}:{a}->{b}"] for a, b in zip(ns, ns[1:], strict=False)]
        y = [100 * r["tpr_difference_per_review"] for r in rows]
        ci = np.array(
            [[100 * bound / r["additional_reviews"] for bound in r["ci95"]] for r in rows]
        )
        ax.plot(range(3), y, "o-", label=scale)
        ax.fill_between(range(3), ci[:, 0], ci[:, 1], alpha=0.15)
    ax.axhline(0, color="grey", linestyle=":")
    ax.set(
        xticks=range(3),
        xticklabels=["1→2", "2→3", "3→5"],
        xlabel="Review increment",
        ylabel="Detection change per added review (pp)",
        title="Exploratory · paired task intervals",
    )
    ax.legend()
    finish(fig, "followup-marginal")

    if measurements is not None:
        measured = read_json(measurements)
        if measured["identity"] != data["identity"] or measured.get("software_only", True):
            raise ValueError("Compatible physical measurements required")
        fig, ax = plt.subplots(figsize=(6, 4))
        for scale in ("five", "hundred"):
            y, ci = values(scale)
            costs = []
            for n in ns:
                cost = measured["methods"][f"{scale}-n{n}"]
                if not cost["cold_complete"]:
                    raise ValueError("Incomplete cold measurement")
                costs.append(cost["gpu_seconds_per_trajectory"])
            ax.plot(costs, 100 * y, "o-", label=scale)
            ax.fill_between(costs, 100 * ci[:, 0], 100 * ci[:, 1], alpha=0.15)
        ax.set(
            xlabel="Measured development GPU seconds / trajectory (startup excluded)",
            ylabel="Expected test attack detection (%)",
            ylim=(0, 100),
            title="Exploratory · calibrated policy; realized FPRs differ",
        )
        ax.legend()
        finish(fig, "followup-detection-cost")
    return {
        "figures": saved,
        "cost_figure": measurements is not None,
        "uncertainty": "Pointwise task-bootstrap intervals; no cost uncertainty inferred.",
    }
