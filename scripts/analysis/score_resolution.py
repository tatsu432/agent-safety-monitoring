"""Explore whether averaging's extra score levels affect the frozen comparison."""

import argparse
import math
from pathlib import Path

from agent_safety_monitoring.analysis.audit import validate_pairs
from agent_safety_monitoring.evaluation.metrics import metrics, paired_bootstrap
from agent_safety_monitoring.io import atomic_json
from agent_safety_monitoring.reporting.report import load_results


def component(result, index):
    scores = [
        artifact["output"]["score"]
        for artifact in result.artifacts
        if artifact.get("stage") == f"review-{index}" and "output" in artifact
    ]
    if len(scores) > 1:
        raise ValueError("Multiple accepted component judgments")
    return scores[0] if scores else None


def analysis(run_root, replicates=2000, seed=20261028):
    tables = load_results(run_root)
    validate_pairs(tables)
    mapped = {}
    equality = {"n": 0, "same_score": 0, "same_first_request": 0}
    for split in ("calibration", "test"):
        sources = tables[split]
        avg_name = next(name for name in sources if name.startswith("average-"))
        single_name = next(name for name in sources if name.startswith("single-"))
        single_by_id = {r["trajectory_id"]: r for r in sources[single_name]}
        variants = {"single": [], "first": [], "second": [], "mean": [], "rounded_mean": []}
        for row in sources[avg_name]:
            a, b = component(row["result"], 0), component(row["result"], 1)
            original = single_by_id[row["trajectory_id"]]
            score = row["score"]
            if score is not None and (
                a is None or b is None or not math.isclose(score, (a + b) / 2)
            ):
                raise ValueError("Saved average differs from component judgments")
            values = {
                "single": original["score"],
                "first": a,
                "second": b,
                "mean": score,
                "rounded_mean": math.floor(score + 0.5) if score is not None else None,
            }
            for variant, value in values.items():
                variants[variant].append(
                    {**{k: row[k] for k in ["trajectory_id", "task_id", "label"]}, "score": value}
                )
            if split == "test":
                equality["n"] += 1
                equality["same_score"] += a == original["score"]
                a_calls = [c.key for c in row["result"].calls if c.stage == "review-0"]
                s_calls = [c.key for c in original["result"].calls if c.stage == "review"]
                equality["same_first_request"] += bool(
                    a_calls and s_calls and a_calls[0] == s_calls[0]
                )
        mapped[split] = variants
    validate_pairs(mapped)
    point = {
        name: metrics([r["score"] for r in mapped["calibration"][name]], mapped["test"][name])
        for name in variants
    }
    return {
        "status": "post-hoc exploratory",
        "rounding_rule": "nearest integer, half up",
        "n_primary_test": equality["n"],
        "first_equals_single_score": equality["same_score"],
        "first_reuses_single_request": equality["same_first_request"],
        "point": point,
        "bootstrap": paired_bootstrap(
            mapped["calibration"], mapped["test"], replicates=replicates, seed=seed
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replicates", type=int, default=2000)
    args = parser.parse_args()
    atomic_json(args.output, analysis(args.run_root, args.replicates))


if __name__ == "__main__":
    main()
