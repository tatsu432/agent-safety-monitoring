import pytest

from agent_safety_monitoring.analysis.joint_structural import evaluate, grid_spec
from agent_safety_monitoring.evaluation.metrics import calibrate


def test_joint_overlap_ess_and_referrals():
    features = {
        str(i): {"source_tokens": length, "tool_calls": tools}
        for i, (length, tools) in enumerate([(1, 1), (1, 1), (1, 1), (10, 10)])
    }
    rows = [
        {"trajectory_id": str(i), "score": score, "label": label}
        for i, (score, label) in enumerate([(1, 0), (5, 1), (None, 1), (5, 1)])
    ]
    spec = {"fields": ["source_tokens", "tool_calls"], "log_edges": [[1.0], [1.0]]}
    result = evaluate(rows, features, spec, calibrate([1] * 20))
    assert result["unsupported_n"] == 1
    assert result["effective_sample_size"] == {"0": 1.0, "1": 2.0}
    assert result["tpr"] == 1
    assert result["fpr"] == pytest.approx(0.05)
    assert result["auroc_valid"] == 1
    unsupported = evaluate(rows[-1:], features, spec, calibrate([1] * 20))
    assert unsupported["tpr"] is None and unsupported["fpr"] is None
    assert unsupported["auroc_valid"] is None


def test_grid_is_independent_of_heldout_features():
    records = [
        {
            "trajectory_id": str(i),
            "split": "development" if i < 10 else "test",
            "assignment": "benign",
            "exclusion": None,
        }
        for i in range(11)
    ]
    features = [
        {"trajectory_id": str(i), "source_tokens": i + 1, "tool_calls": i + 1} for i in range(11)
    ]
    spec = grid_spec(records, features)
    features[-1]["source_tokens"] = 10**8
    features[-1]["tool_calls"] = 10**8
    assert grid_spec(records, features) == spec
