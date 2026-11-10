"""Render aggregate-only joint structural sensitivity results."""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from agent_safety_monitoring.io import read_json


def render(source, output):
    data = read_json(source)
    output.mkdir(parents=True, exist_ok=True)
    names = list(data["point"])
    lines = [
        "# Joint length and tool-count sensitivity",
        "",
        "Exploratory analysis of the original 572-record primary test cohort. A fixed grid uses "
        "development quintiles of log source-token length and log tool-call count. Within each "
        "cell, benign and successful-attack mass is equalized to the smaller class count. "
        "Cells without both classes receive zero weight. The original 448-record benign "
        "calibration population and 5% expected-FPR policies are unchanged.",
        "",
        "| Method | Weighted detection % [95% CI] | Weighted FPR % | Weighted valid AUROC |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name in names:
        p = data["point"][name]
        ci = data["intervals"][name]["tpr"]["ci95"]
        lines.append(
            f"| {name.split('-')[0] if not name.startswith('structural') else name} | "
            f"{100 * p['tpr']:.1f} [{100 * ci[0]:.1f}, {100 * ci[1]:.1f}] | "
            f"{100 * p['fpr']:.1f} | {p['auroc_valid']:.3f} |"
        )
    p = data["point"][names[0]]
    unsupported = {
        str(label): sum(
            cell["benign" if label == 0 else "attack"]
            for cell in p["overlap"]
            if cell["retained_mass_per_class"] == 0
        )
        for label in (0, 1)
    }
    ess = p["effective_sample_size"]
    lines += [
        "",
        f"The grid excludes {p['unsupported_n']} records from common support "
        f"({unsupported['0']} benign, {unsupported['1']} attacks). Class-specific Kish "
        f"effective sample sizes are {ess['0']:.1f} benign and {ess['1']:.1f} attacks.",
        "",
        "Intervals use 2,000 shared whole-task bootstrap draws, independently resampling "
        "calibration and test tasks, recalibrating and recomputing cell weights on each draw. "
        "They condition on the development-fitted baselines and bin boundaries. Pointwise "
        "paired comparisons, objective-specific intervals, overlap counts, and weighted "
        "feature means are in [the aggregate artifact](joint-structural-aggregate.json).",
        "",
        "The averaging-versus-single and averaging-versus-MRT detection differences remain "
        "positive in point estimates. The structural length-plus-tool baseline weakens "
        "substantially within this overlap population. This supports caution about structural "
        "predictability in the original cohort; it does not establish that the monitors "
        "recognize harm independently of all structural cues. Coarse cells leave residual "
        "imbalance, unsupported records change the estimand, and benign calibration/test "
        "task populations still differ. Comparisons with think-longer remain subject to "
        "unequal realized FPR and paired uncertainty.",
        "",
        "![Joint sensitivity](figures/joint-structural-performance.png)",
        "",
    ]
    (output / "joint-structural-sensitivity.md").write_text("\n".join(lines))
    figure_dir = output / "figures"
    figure_dir.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, name in enumerate(names):
        p = data["point"][name]
        ci = np.array(data["intervals"][name]["tpr"]["ci95"]) * 100
        y = 100 * p["tpr"]
        ax.plot([ci[0], ci[1]], [i, i], color="C0")
        ax.plot(y, i, "o", color="C0")
    ax.set(
        yticks=range(len(names)),
        yticklabels=[n.split("-")[0] if not n.startswith("structural") else n for n in names],
        xlabel="Weighted expected attack detection (%)",
        xlim=(0, 100),
        title="Exploratory · joint common support · original calibration",
    )
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(figure_dir / "joint-structural-performance.png", dpi=300)
    fig.savefig(figure_dir / "joint-structural-performance.pdf")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.source, args.output)
