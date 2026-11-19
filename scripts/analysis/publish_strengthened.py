"""Publish only scalar aggregate statistics from the scoring study."""

import argparse
import math
import uuid
from pathlib import Path

from agent_safety_monitoring.experiments.telemetry import Telemetry
from agent_safety_monitoring.io import read_json


def publish(source):
    data = read_json(source)
    directory = Path("runs/analysis-tracking")
    directory.mkdir(parents=True, exist_ok=True)
    values = {}
    for scale in ("five", "hundred"):
        for n in (1, 2, 3, 5):
            name = f"{scale}-n{n}"
            for key in ("tpr", "fpr", "auroc_valid", "pauc_00_10"):
                values[f"target05/{name}/{key}"] = data["scoring"]["point"][name][key]
            for key in ("tpr", "fpr"):
                values[f"target01/{name}/{key}"] = data["one_percent"]["point"][name][key]
            values[f"gpu/{name}/workload_seconds_per_trajectory"] = data["timing"][name][
                "gpu_seconds_per_trajectory"
            ]
    if not all(
        isinstance(value, (int, float)) and math.isfinite(value) for value in values.values()
    ):
        raise ValueError("Tracking metrics must be finite scalars")
    tracker = Telemetry(
        {"mode": "online"},
        identity=data["followup_freeze"],
        split="strengthen-scoring",
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
    print(publish(parser.parse_args().source))
