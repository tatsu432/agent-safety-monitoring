"""Consistent static figures derived exclusively from aggregate numeric fields."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from agent_safety_monitoring.analysis.aggregate import NAMES, ORDER

COLORS = dict(zip(ORDER, ["#4477AA", "#228833", "#AA3377", "#CCBB44", "#66CCEE"], strict=True))


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def generate_figures(data, uncertainty, ids, output):
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    methods = data["methods"]
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, f in enumerate(ORDER):
        y = 100 * methods[f]["primary"]["tpr"]
        low, high = [100 * v for v in uncertainty["tpr_intervals"][ids[f]]]
        ax.plot([low, high], [i, i], color=COLORS[f], lw=2)
        ax.scatter(y, i, color=COLORS[f])
    ax.set(
        yticks=range(5),
        yticklabels=[NAMES[f] for f in ORDER],
        xlim=(0, 100),
        xlabel="Expected attack detection (%)",
        title="Benign-calibrated 5% FPR target",
    )
    ax.invert_yaxis()
    save(fig, output / "main-performance")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, row in enumerate(data["paired_differences"]):
        ax.plot([100 * x for x in row["ci95"]], [i, i], color="#4477AA", lw=2)
        ax.scatter(100 * row["difference"], i, color="#4477AA")
    ax.axvline(0, color="black", lw=0.8)
    ax.set(
        yticks=range(7),
        yticklabels=[f"{NAMES[r['a']]} − {NAMES[r['b']]}" for r in data["paired_differences"]],
        xlabel="Paired TPR difference (percentage points)",
    )
    ax.invert_yaxis()
    save(fig, output / "paired-differences")
    for metric, filename, xlabel in [
        ("gpu", "gpu-cost-detection", "Development workload GPU-seconds / trajectory"),
        ("tokens", "token-cost-detection", "Logical generated tokens / test trajectory"),
    ]:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for f in ORDER:
            x = (
                data["development_gpu_seconds"][f]
                if metric == "gpu"
                else methods[f]["cost"]["output_tokens"] / methods[f]["primary"]["n"]
            )
            y = methods[f]["primary"]["tpr"] * 100
            low, high = [100 * v for v in uncertainty["tpr_intervals"][ids[f]]]
            ax.plot([x, x], [low, high], color=COLORS[f], lw=2)
            ax.scatter(x, y, color=COLORS[f], label=NAMES[f])
        ax.set(xlabel=xlabel, ylabel="Expected attack detection (%)", ylim=(0, 100))
        ax.legend(fontsize=8)
        save(fig, output / filename)
    fig, ax = plt.subplots(figsize=(9, 4))
    objectives = sorted(methods["single"]["per_objective"])
    for i, f in enumerate(ORDER):
        ax.bar(
            np.arange(len(objectives)) + (i - 2) * 0.15,
            [100 * methods[f]["per_objective"][o]["tpr"] for o in objectives],
            width=0.15,
            label=NAMES[f],
            color=COLORS[f],
        )
    ax.set(
        xticks=range(len(objectives)),
        xticklabels=[o.replace("_", "\n") for o in objectives],
        ylabel="Expected attack detection (%)",
        ylim=(0, 100),
    )
    ax.legend(fontsize=8, ncol=2)
    save(fig, output / "per-objective")
    fig, ax = plt.subplots(figsize=(8, 4))
    points = [
        (name, v["metrics"]["tpr"], v["bootstrap"]["tpr_intervals"][name])
        for name, v in data["structural"]["baselines"].items()
    ]
    points += [
        (NAMES[f], methods[f]["primary"]["tpr"], uncertainty["tpr_intervals"][ids[f]])
        for f in ORDER
    ]
    for i, (_, value, ci) in enumerate(points):
        ax.plot([100 * x for x in ci], [i, i], color="#4477AA", lw=2)
        ax.scatter(100 * value, i, color="#4477AA")
    ax.set(
        yticks=range(len(points)),
        yticklabels=[p[0] for p in points],
        xlabel="Expected attack detection (%)",
        xlim=(0, 100),
    )
    ax.invert_yaxis()
    save(fig, output / "structural-performance")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharex=True)
    for label, ax in enumerate(axes):
        rows = [r for r in data["injections"] if r["family"] == "all" and r["label"] == label]
        for i, r in enumerate(rows):
            ax.plot([100 * v for v in r["ci95"]], [i, i], color="#4477AA", lw=2)
            ax.scatter(100 * r["mean_change"], i, color="#4477AA")
        ax.axvline(0, color="black", lw=0.8)
        ax.set(
            yticks=range(len(rows)),
            yticklabels=[NAMES[r["method"].split("-")[0]] for r in rows],
            xlabel="Matched change (percentage points)",
            title="Missed attacks" if label else "Benign alerts",
        )
    save(fig, output / "injection-effects")

    if "feature_groups" in data:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        groups = data["feature_groups"]
        for field, ax in zip(["source_tokens", "tool_calls"], axes, strict=True):
            for i, group in enumerate(groups.values()):
                v = group[field]
                ax.plot([v["q25"], v["q75"]], [i, i], color="#4477AA", lw=2)
                ax.scatter(v["median"], i, color="#4477AA")
            ax.set(
                yticks=range(len(groups)),
                yticklabels=list(groups),
                xlabel="Source tokens" if field == "source_tokens" else "Tool calls",
            )
        save(fig, output / "source-feature-distributions")
