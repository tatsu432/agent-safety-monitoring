"""Reconcile paired evidence-replacement outcomes without exporting individual records."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from agent_safety_monitoring.evaluation.metrics import calibrate
from agent_safety_monitoring.io import atomic_json, read_json
from agent_safety_monitoring.reporting.report import load_results


def summarize(run_root, replacement_root, replicates=2000, seed=20261028):
    tables = load_results(run_root)
    name = next(k for k in tables["test"] if k.startswith("eae-"))
    policy = calibrate([r["score"] for r in tables["calibration"][name]])
    by_id = {r["trajectory_id"]: r for r in tables["test"][name]}
    identity = read_json(replacement_root / "identity.json")
    if identity["freeze"] != read_json(run_root / "study.json")["freeze"]:
        raise ValueError("Replacement freeze differs from original run")
    counts, groups, original, revised = Counter(), defaultdict(list), [], []
    seen = set()
    for path in sorted((replacement_root / "results").glob("*.json")):
        d = read_json(path)
        uid = d["trajectory_id"]
        if uid in seen or d["identity"] != identity or uid not in by_id or by_id[uid]["label"] != 1:
            raise ValueError("Duplicate, mismatched or ineligible replacement record")
        seen.add(uid)
        counts[d["status"]] += 1
        if d["status"] not in {"valid", "invalid"}:
            continue
        if (d["status"] == "valid" and d["score"] not in (1, 2, 3, 4, 5)) or (
            d["status"] == "invalid" and d["score"] is not None
        ):
            raise ValueError("Replacement validity and score disagree")
        a, b = policy.alerts([by_id[uid]["score"], d["score"]])
        original.append(float(a))
        revised.append(float(b))
        groups[by_id[uid]["task_id"]].append(float(b - a))
    keys = sorted(groups)
    rng = np.random.default_rng(seed)
    samples = (
        [
            np.mean([v for task in rng.choice(keys, len(keys), replace=True) for v in groups[task]])
            for _ in range(replicates)
        ]
        if keys
        else []
    )
    return {
        "freeze": identity["freeze"],
        "provenance": "model_suggested",
        "status": "post-hoc exploratory selected sample",
        "counts": dict(counts),
        "eligible_records": len(original),
        "task_groups": len(groups),
        "original_expected_alert_rate": float(np.mean(original)) if original else None,
        "replacement_expected_alert_rate": float(np.mean(revised)) if revised else None,
        "mean_expected_alert_change": float(np.mean(np.array(revised) - original))
        if original
        else None,
        "ci95": np.quantile(samples, [0.025, 0.975]).tolist() if samples else None,
        "bootstrap_replicates": replicates,
        "seed": seed,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--replacement-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    atomic_json(args.output, summarize(args.run_root, args.replacement_root))


if __name__ == "__main__":
    main()
