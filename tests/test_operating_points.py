import numpy as np
import pytest

from agent_safety_monitoring.analysis.operating_points import (
    comparison,
    discrimination,
    evaluate_counts,
)
from agent_safety_monitoring.evaluation.metrics import metrics, paired_bootstrap


def row(i, score, label, task=None):
    return dict(trajectory_id=str(i), task_id=str(task or i), score=score, label=label)


def test_empirical_ties_and_partial_area():
    d = discrimination([1, 1], [1, 1])
    assert d["auroc_valid"] == 0.5
    assert d["roc_tpr_05"] == 0.05
    assert d["pauc_00_10"] == pytest.approx(0.005)
    d = discrimination([0, 2], [2, 0])
    assert d["auroc_valid"] == 1
    assert d["roc_tpr_05"] == 1
    assert d["pauc_00_10"] == 0.1
    assert discrimination([1], [0])["auroc_valid"] is None


def test_referral_floor_and_calibration_infeasibility():
    r = evaluate_counts([95, 5], [90, 10], [20, 80], [5])
    assert r["policy"]["feasible"]
    assert r["policy"]["cutoff"] is None
    assert r["fpr"] == 0.1 and r["tpr"] == 0.8
    assert r["referral_roc_tpr_05"] is None
    assert r["referral_roc_tpr_10"] == 0.8
    assert not evaluate_counts([94, 6], [90, 10], [20, 80], [5])["policy"]["feasible"]


def test_independent_counts_match_original_metrics_and_bootstrap():
    cal = [row(f"c{i}", s, 0) for i, s in enumerate([5, 4, 3, 2, 1] * 8)]
    test = [
        row(i, s, int(i % 3 != 0), f"t{i // 3}") for i, s in enumerate([5, 5, 3, 2, None, 1] * 4)
    ]
    old = metrics([r["score"] for r in cal], test)
    result = comparison({"a": cal, "b": cal}, {"a": test, "b": test}, 40)
    new = result["point"]["a"]
    for key in ["tpr", "fpr", "auroc_valid", "policy"]:
        assert new[key] == old[key]
    frozen = paired_bootstrap({"a": cal, "b": cal}, {"a": test, "b": test}, 40)
    assert result["intervals"]["a"]["tpr"]["ci95"] == pytest.approx(frozen["tpr_intervals"]["a"])
    for item in result["paired_differences"]["a - b"].values():
        assert item["ci95"] == [0, 0]


def test_invalid_pairing_and_nonfinite_scores_rejected():
    cal = [row("c", 1, 0)]
    test = [row("t1", np.inf, 0), row("t2", 2, 1)]
    with pytest.raises(ValueError):
        comparison({"a": cal}, {"a": test}, 2)
    with pytest.raises(ValueError):
        comparison({"a": cal, "b": cal}, {"a": test, "b": test[:-1]}, 2)
