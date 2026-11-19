"""Development-frozen length strata and globally calibrated descriptive comparisons."""

from bisect import bisect_right
from collections import Counter

import numpy as np
from scipy.stats import spearmanr

from agent_safety_monitoring.analysis.audit import validate_pairs
from agent_safety_monitoring.analysis.operating_points import comparison


def development_edges(dev, lengths, minimum=5):
    edges = [16000, 32000, 64000]
    strategy = "prespecified"
    values = [lengths[row["trajectory_id"]] for row in dev]

    def counts():
        return Counter(
            (bisect_right(edges, length), row["label"])
            for row, length in zip(dev, values, strict=True)
        )

    used = counts()
    if any(used[i, label] < minimum for i in range(4) for label in (0, 1)):
        strategy = "development quartiles with sparse neighbors merged"
        edges = sorted({int(x) for x in np.quantile(values, (0.25, 0.50, 0.75))})
        while edges:
            used = counts()
            sparse = next(
                (i for i in range(len(edges) + 1) if min(used[i, 0], used[i, 1]) < minimum),
                None,
            )
            if sparse is None:
                break
            edges.pop(min(sparse, len(edges) - 1))
    used = counts()
    return edges, strategy, [[used[i, 0], used[i, 1]] for i in range(len(edges) + 1)]


def bucket_costs(rows):
    calls = []
    for row in rows:
        if "result" in row:
            calls.extend(c.model_dump() for c in row["result"].calls)
        else:
            calls.extend(row.get("calls", []))
    return {
        "trajectories": len(rows),
        "logical_calls": len(calls),
        "new_calls": sum(not c["cached"] for c in calls),
        "cached_calls": sum(c["cached"] for c in calls),
        "input_tokens": sum(c["usage"]["input_tokens"] for c in calls),
        "output_tokens": sum(c["usage"]["output_tokens"] for c in calls),
    }


def length_analysis(dev, calibration, test, features, replicates=2000):
    validate_pairs({"calibration": calibration, "test": test})
    lengths = {uid: f["source_tokens"] for uid, f in features.items()}
    edges, strategy, development_counts = development_edges(dev, lengths)
    rows = next(iter(test.values()))
    task_ids = {r["task_id"] for r in rows}
    bins, trends = [], {}
    for index in range(len(edges) + 1):
        selected = {
            r["trajectory_id"]
            for r in rows
            if bisect_right(edges, lengths[r["trajectory_id"]]) == index
        }
        tables = {
            name: [r for r in method if r["trajectory_id"] in selected]
            for name, method in test.items()
        }
        counts = Counter(r["label"] for r in next(iter(tables.values())))
        sparse = [
            name
            for name, method in tables.items()
            if any(
                sum(r["score"] is not None and r["label"] == c for r in method) < 10 for c in (0, 1)
            )
        ]
        metrics = (
            comparison(calibration, tables, replicates, test_tasks=task_ids)
            if counts[0] and counts[1]
            else None
        )
        bins.append(
            {
                "lower_inclusive": ([0] + edges)[index],
                "upper_exclusive": (edges + [None])[index],
                "test_benign": counts[0],
                "test_successful_attack": counts[1],
                "sparse_methods": sparse,
                "globally_calibrated": metrics,
                "costs": {name: bucket_costs(method) for name, method in tables.items()},
            }
        )
    for name, method in test.items():
        trends[name] = {}
        objectives = sorted({r["objective"] for r in method if r["label"] and r["objective"]})
        for group in ["benign", "successful_attack", *objectives]:
            valid = [
                r
                for r in method
                if r["score"] is not None
                and (
                    (not r["label"] if group == "benign" else bool(r["label"]))
                    if group in ("benign", "successful_attack")
                    else r["objective"] == group
                )
            ]
            scores = [r["score"] for r in valid]
            x = [lengths[r["trajectory_id"]] for r in valid]
            trends[name][group] = {
                "valid_n": len(valid),
                "spearman_score_vs_length": (
                    float(spearmanr(x, scores).statistic)
                    if len(set(x)) > 1 and len(set(scores)) > 1
                    else None
                ),
            }
    return {
        "length_definition": "canonical source_tokens from frozen tokenizer audit",
        "edge_strategy": strategy,
        "development_benign_and_successful_attack_counts": development_counts,
        "bins": bins,
        "descriptive_score_associations": trends,
    }
