"""Publish only fixed, numeric evidence-diagnostic aggregates to W&B."""

import argparse
import math
import uuid
from pathlib import Path

from agent_safety_monitoring.experiments.telemetry import Telemetry
from agent_safety_monitoring.io import read_json


def publish(retention_file, replacement_file, mode="online"):
    retention, replacement = read_json(retention_file), read_json(replacement_file)
    if retention["freeze"] != replacement["freeze"]:
        raise ValueError("Evidence aggregate identities differ")
    eae = next(v for k, v in retention["methods"].items() if k.startswith("eae-"))
    values = {
        "evidence/model_proposals": retention["model_proposals"],
        "evidence/model_supported_records": retention["model_supported_records"],
        "evidence/reference_passages": eae["references"],
        "evidence/fully_retained": eae["full"],
        "evidence/partly_retained": eae["partial"],
        "evidence/no_overlap": eae["missing"],
        "replacement/eligible_records": replacement["eligible_records"],
        "replacement/task_groups": replacement["task_groups"],
        "replacement/original_expected_alert_rate": replacement["original_expected_alert_rate"],
        "replacement/new_expected_alert_rate": replacement["replacement_expected_alert_rate"],
        "replacement/mean_alert_change": replacement["mean_expected_alert_change"],
    }
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values.values()):
        raise ValueError("Evidence metrics must be finite numbers")
    directory = Path("runs/analysis-tracking")
    directory.mkdir(parents=True, exist_ok=True)
    tracker = Telemetry(
        {"mode": mode},
        identity=retention["freeze"],
        split="evidence-diagnostic",
        attempt=uuid.uuid4().hex,
        directory=directory,
    )
    submitted = False
    try:
        if tracker.run is not None:
            tracker.run.log(values)
            submitted = mode == "online"
    except Exception:
        submitted = False
    finally:
        tracker.close()
    return {
        "online_metrics_submitted": submitted,
        "tracking_mode": tracker.mode,
        "tracking_failure_type": tracker.failure_type,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retention", type=Path, required=True)
    parser.add_argument("--replacement", type=Path, required=True)
    parser.add_argument("--mode", default="online", choices=["online", "offline", "disabled"])
    args = parser.parse_args()
    print(publish(args.retention, args.replacement, args.mode))


if __name__ == "__main__":
    main()
