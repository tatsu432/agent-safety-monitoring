"""Describe benign and successful-attack decisions within legitimate task groups."""

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np

from agent_safety_monitoring.analysis.audit import validate_pairs
from agent_safety_monitoring.evaluation.metrics import calibrate
from agent_safety_monitoring.io import atomic_json
from agent_safety_monitoring.reporting.report import load_results


def task_difference(rows, policy):
    benign = [r for r in rows if r["label"] == 0]
    attacks = [r for r in rows if r["label"] == 1]
    if len(benign) != 1 or not attacks:
        raise ValueError("Each paired test task must have one benign and at least one attack")
    return float(
        policy.alerts([r["score"] for r in attacks]).mean() - policy.alerts([benign[0]["score"]])[0]
    )


def analyze(run_root, replicates=2000, seed=20261028):
    tables = load_results(run_root)
    validate_pairs(tables)
    output = {}
    for method in sorted(tables["test"]):
        cal = defaultdict(list)
        test = defaultdict(list)
        for row in tables["calibration"][method]:
            cal[row["task_id"]].append(row)
        for row in tables["test"][method]:
            test[row["task_id"]].append(row)
        ckeys, tkeys = sorted(cal), sorted(test)
        policy = calibrate([r["score"] for rows in cal.values() for r in rows])
        point = float(np.mean([task_difference(rows, policy) for rows in test.values()]))
        counts = {"attack_higher": 0, "equal": 0, "attack_lower": 0, "invalid_pair": 0}
        for rows in test.values():
            benign = [r for r in rows if r["label"] == 0]
            attacks = [r for r in rows if r["label"] == 1]
            if len(benign) != 1 or not attacks:
                raise ValueError("Incomplete paired task")
            score = benign[0]["score"]
            for r in attacks:
                attack = r["score"]
                if score is None or attack is None:
                    counts["invalid_pair"] += 1
                else:
                    counts[
                        "attack_higher"
                        if attack > score
                        else "attack_lower"
                        if attack < score
                        else "equal"
                    ] += 1
        rng = np.random.default_rng(seed)
        samples = []
        for _ in range(replicates):
            cs = rng.choice(ckeys, len(ckeys), replace=True)
            ts = rng.choice(tkeys, len(tkeys), replace=True)
            sampled_policy = calibrate([r["score"] for key in cs for r in cal[key]])
            samples.append(
                float(np.mean([task_difference(test[key], sampled_policy) for key in ts]))
            )
        output[method] = {
            "tasks": len(tkeys),
            "equal_task_weight_alert_difference": point,
            "ci95": np.quantile(samples, [0.025, 0.975]).tolist(),
            "valid_score_pair_comparisons": counts,
        }
    return {
        "status": "post-hoc descriptive; benign labels are nominal",
        "replicates": replicates,
        "seed": seed,
        "methods": output,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    atomic_json(args.output, analyze(args.run_root))


if __name__ == "__main__":
    main()
