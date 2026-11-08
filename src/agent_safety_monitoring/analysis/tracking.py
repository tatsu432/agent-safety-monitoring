"""Online post-hoc metrics with an explicit scalar-only export allowlist."""

import math
import uuid
from pathlib import Path

from agent_safety_monitoring.experiments.telemetry import Telemetry


def publish(data, mode="online"):
    directory = Path("runs/analysis-tracking")
    directory.mkdir(parents=True, exist_ok=True)
    tracker = Telemetry(
        {"mode": mode},
        identity=data["freeze"],
        split="posthoc-analysis",
        attempt=uuid.uuid4().hex,
        directory=directory,
    )
    values = {}
    for family in ["single", "think", "average", "eae", "mrt"]:
        method = data["methods"][family]
        for field in ["tpr", "fpr", "auroc_valid", "invalid_rate", "valid_score_coverage"]:
            value = method["primary"][field]
            if isinstance(value, (int, float)) and math.isfinite(value):
                values[f"{family}/{field}"] = value
        values[f"{family}/development_gpu_seconds_per_trajectory"] = data[
            "development_gpu_seconds"
        ][family]
    delivered = False
    try:
        if tracker.run is not None:
            tracker.run.log(values)
            delivered = mode == "online"
    except Exception:
        delivered = False
    finally:
        tracker.close()
    return {
        "online_metrics_submitted": delivered,
        "tracking_mode": tracker.mode,
        "tracking_failure_type": tracker.failure_type,
    }


def publish_diagnosis(data, mode="online"):
    """Fixed family/metric allowlist; no IDs, arrays, text, references, or payloads."""
    directory = Path("runs/analysis-tracking")
    directory.mkdir(parents=True, exist_ok=True)
    tracker = Telemetry(
        {"mode": mode},
        identity=data["freeze"],
        split="diagnosis",
        attempt=uuid.uuid4().hex,
        directory=directory,
    )
    allowed = {"single", "think", "average", "eae", "mrt", "sequential", "hierarchical"}
    fields = ["tpr", "fpr", "auroc_valid", "roc_tpr_05", "roc_tpr_10", "pauc_00_10"]
    values = {}
    for name, result in data["branches"]["point"].items():
        family = name.split("-")[0]
        if family not in allowed:
            raise ValueError("Unexpected tracking family")
        for key in fields:
            value = result[key]
            if isinstance(value, (int, float)) and math.isfinite(value):
                values[f"{family}/{key}"] = value
    delivered = False
    try:
        if tracker.run is not None:
            tracker.run.log(values)
            delivered = tracker.mode == "online"
    except Exception:
        delivered = False
    finally:
        tracker.close()
    return {
        "online_metrics_submitted": delivered,
        "tracking_mode": tracker.mode,
        "tracking_failure_type": tracker.failure_type,
    }
