"""Send allowlisted scalar study results to the existing W&B project."""

import argparse
import math
import uuid
from pathlib import Path

from agent_safety_monitoring.experiments.telemetry import Telemetry
from agent_safety_monitoring.io import read_json

METHODS = (
    "fixed-1",
    "fixed-2",
    "fixed-3",
    "fixed-5",
    "gate-2",
    "gate-3",
    "gate-5",
    "sequential-5",
)
METRICS = ("tpr", "fpr", "auroc_valid", "pauc_00_10")


def publish(source, directory):
    data = read_json(source)
    directory.mkdir(parents=True, exist_ok=True)
    values = {}
    for name in METHODS:
        point = data["operating_points"]["point"].get(name)
        if point is None:
            continue
        for key in METRICS:
            values[f"target05/{name}/{key}"] = point[key]
        for key in ("reviews", "escalated", "estimated_gpu_seconds"):
            values[f"cost/{name}/{key}"] = data["test_cost"][name][key]["mean"]
    if not all(type(v) in {int, float} and math.isfinite(v) for v in values.values()):
        raise ValueError("Tracking accepts only finite aggregate metrics")
    tracker = Telemetry(
        {"mode": "online"},
        identity=data["archive_freeze"],
        split="extension-adaptive",
        attempt=uuid.uuid4().hex,
        directory=directory,
    )
    try:
        if tracker.run is None:
            return {"published": False, "failure": tracker.failure_type}
        tracker.run.log(values)
        return {"published": tracker.mode == "online", "run_url": tracker.run.url}
    finally:
        tracker.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    print(publish(args.source, args.directory))
