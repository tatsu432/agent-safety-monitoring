from pathlib import Path

import pytest

from agent_safety_monitoring.experiments.selection import select
from agent_safety_monitoring.io import atomic_json, read_json


def test_budget_selection_uses_only_development_and_marks_expensive_methods(tmp_path: Path):
    trials = []
    for index, method in enumerate(["single", "think", "average", "eae", "mrt"], 1):
        root = tmp_path / method
        for label in [0, 1]:
            atomic_json(
                root / "development" / method / f"{label}.json",
                {
                    "evaluation": {
                        "split": "development",
                        "assignment": "attack" if label else "benign",
                        "outcome": "success" if label else "not_applicable",
                    },
                    "result": {"score": 1 + label},
                },
            )
        trials.append(
            {
                "method": {"method": method},
                "gpu_seconds_per_trajectory": float(index),
                "run_root": str(root),
            }
        )
    measurement = tmp_path / "measurements.json"
    base = tmp_path / "base.json"
    output = tmp_path / "selection.json"
    atomic_json(measurement, {"trials": trials})
    atomic_json(base, {"model": {"backend": "mock"}, "methods": []})
    result = select(measurement, base, output)
    assert result["large_budget_all_methods_available"]
    assert result["budgets"]["small"]["gpu_seconds_limit"] == 2
    assert result["budgets"]["small"]["methods"]["eae"] is None
    assert result["budgets"]["large"]["methods"]["eae"] is not None
    changed = tmp_path / "mrt" / "development" / "mrt" / "1.json"
    obj = read_json(changed)
    obj["evaluation"]["split"] = "test"
    atomic_json(changed, obj)
    with pytest.raises(ValueError, match="Only development"):
        select(measurement, base, output)
