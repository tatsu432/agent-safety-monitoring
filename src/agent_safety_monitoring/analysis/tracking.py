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
