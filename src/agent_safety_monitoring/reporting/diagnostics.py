"""Post-freeze structural diagnostics and saved matched-injection figures."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from agent_safety_monitoring.evaluation.metrics import calibrate, metrics, paired_bootstrap
from agent_safety_monitoring.evaluation.structural import (
    fit_baselines,
    length_bootstrap,
    length_weighted,
)
from agent_safety_monitoring.experiments.runner import validate_freeze
from agent_safety_monitoring.io import atomic_json, read_json
from agent_safety_monitoring.reporting.report import load_results


def structural_report(data: Path, root: Path, frozen: dict, output: Path, replicates=2000):
    validate_freeze(frozen, data)
    if read_json(root / "study.json")["freeze"] != frozen["hash"]:
        raise ValueError("Primary results belong to a different frozen study")
    manifest, audit = read_json(data / "manifest.json"), read_json(data / "audit.json")
    baselines = fit_baselines(manifest["records"], audit["features"])
    result = {"length_feature": baselines["length_feature"], "baselines": {}, "length_matched": {}}
    for name, splits in baselines["models"].items():
        result["baselines"][name] = {
            "metrics": metrics([r["score"] for r in splits["calibration"]], splits["test"]),
            "bootstrap": paired_bootstrap(
                {name: splits["calibration"]}, {name: splits["test"]}, replicates=replicates
            ),
        }
    tables = load_results(root)
    lengths = {r["trajectory_id"]: r[baselines["length_feature"]] for r in audit["features"]}
    for name, rows in tables["test"].items():
        calibration = tables["calibration"][name]
        result["length_matched"][name] = {
            "point": length_weighted(
                rows,
                lengths,
                baselines["development_length_edges"],
                calibrate([r["score"] for r in calibration]),
            ),
            "bootstrap": length_bootstrap(
                calibration, rows, lengths, baselines["development_length_edges"], replicates
            ),
        }
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / "structural-diagnostics.json", result)
    return {"output": str(output / "structural-diagnostics.json"), "baselines": 3}


def injection_figure(source: Path, output: Path):
    data = read_json(source)
    rows = data["rows"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for label, ax in enumerate(axes):
        names, values = [], []
        for method in sorted({r["method"] for r in rows}):
            for placement in ["early", "late"]:
                selected = [
                    r
                    for r in rows
                    if r["method"] == method and r["placement"] == placement and r["label"] == label
                ]
                if selected:
                    key = "miss_difference" if label else "alert_difference"
                    names.append(method.split("-")[0] + "/" + placement)
                    values.append(float(np.mean([r[key] for r in selected])))
        ax.bar(names, values)
        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_ylabel("Missed-attack increase" if label else "False-alarm increase")
        ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)
