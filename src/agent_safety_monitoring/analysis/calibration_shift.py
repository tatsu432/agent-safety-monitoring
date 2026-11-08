"""Descriptive calibration/test benign contrasts with whole-task uncertainty."""

import numpy as np

from agent_safety_monitoring.analysis.audit import validate_pairs
from agent_safety_monitoring.io import atomic_json, digest, read_json
from agent_safety_monitoring.reporting.report import load_results


def contrast(rows_a, rows_b, replicates=2000, seed=20261028):
    """Rows: task_id, numeric value. Point estimate is test minus calibration mean."""

    def pack(rows):
        groups = {}
        for row in rows:
            groups.setdefault(row["task_id"], []).append(row["value"])
        keys = sorted(groups)
        return (np.array([sum(groups[k]) for k in keys]), np.array([len(groups[k]) for k in keys]))

    a, an = pack(rows_a)
    b, bn = pack(rows_b)
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(replicates):
        ai = rng.choice(len(a), len(a), replace=True)
        bi = rng.choice(len(b), len(b), replace=True)
        samples.append(b[bi].sum() / bn[bi].sum() - a[ai].sum() / an[ai].sum())
    return {
        "calibration_n": int(an.sum()),
        "test_n": int(bn.sum()),
        "calibration_mean": float(a.sum() / an.sum()),
        "test_mean": float(b.sum() / bn.sum()),
        "test_minus_calibration": float(b.sum() / bn.sum() - a.sum() / an.sum()),
        "ci95": np.quantile(samples, [0.025, 0.975]).tolist(),
    }


def analyze(data, run_root, output):
    tables = load_results(run_root)
    validate_pairs(tables)
    features = read_json(data / "audit.json")
    mapping = {r["trajectory_id"]: r for r in features["features"]}
    name = next(iter(tables["test"]))
    result = {"features": {}, "scores": {}}
    for field in ["source_tokens", "characters", "tool_calls"]:
        groups = [
            [
                {"task_id": r["task_id"], "value": mapping[r["trajectory_id"]][field]}
                for r in tables[split][name]
                if not r["label"]
            ]
            for split in ["calibration", "test"]
        ]
        if all(r["value"] is not None for rows in groups for r in rows):
            result["features"][field] = contrast(*groups)
    for name in tables["test"]:
        groups = [
            [r for r in tables[split][name] if not r["label"]] for split in ["calibration", "test"]
        ]
        result["scores"][name] = {}
        for key, fun in [
            ("invalid", lambda s: float(s is None)),
            ("top_score", lambda s: float(s == 5)),
        ]:
            result["scores"][name][key] = contrast(
                *[
                    [{"task_id": r["task_id"], "value": fun(r["score"])} for r in rows]
                    for rows in groups
                ]
            )
    result.update(
        feature_audit_hash=digest(features),
        replicates=2000,
        interpretation="Descriptive population contrasts; neither FPR differences nor "
        "these observational contrasts establish a cause of monitor errors.",
    )
    atomic_json(output, result)
    return result
