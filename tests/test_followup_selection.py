import pytest

from agent_safety_monitoring.analysis.followup import select_development
from agent_safety_monitoring.experiments.followup import FollowupConfig
from agent_safety_monitoring.io import atomic_json, digest, read_json


def test_selection_groups_tasks_and_requires_physical_cost(tmp_path):
    ids = [f"{t}-{label}" for t in range(5) for label in range(2)]
    identity = {"config": FollowupConfig().model_dump(), "expected": {"development": ids}}
    atomic_json(tmp_path / "identity.json", identity)
    atomic_json(
        tmp_path / "development-0-geometry.json", {"shard": 0, "shards": 1, "expected_ids": ids}
    )
    for uid in ids:
        task, label = uid.split("-")
        row = {
            "trajectory_id": uid,
            "task_id": task,
            "assignment": "attack" if label == "1" else "benign",
            "outcome": "success" if label == "1" else "not_applicable",
            "split": "development",
        }
        for scale in ("five", "hundred"):
            for i in range(5):
                atomic_json(
                    tmp_path / "development" / f"{uid}-{scale}-{i}.json",
                    {
                        "key": {
                            "identity": digest(identity),
                            "trajectory_id": uid,
                            "evaluation": row,
                            "scale": scale,
                            "sample": i,
                            "seed": 20261028 + 100 * i,
                        },
                        "review": {"status": "valid", "score": 5 if label == "1" else 1},
                    },
                )
    timing = {
        "identity": digest(identity),
        "software_only": False,
        "methods": {
            f"{scale}-n{n}": {
                "gpu_seconds_per_trajectory": n + (scale == "hundred"),
                "cold_complete": True,
                "job_id": "123",
            }
            for scale in ("five", "hundred")
            for n in (1, 2, 3, 5)
        },
    }
    atomic_json(tmp_path / "timing.json", timing)
    selected = select_development(tmp_path, tmp_path / "timing.json", tmp_path / "selection.json")
    assert selected["selected"] == "five-n1"
    result = read_json(tmp_path / "selection.json")
    assert sorted(result["task_folds"].values()) == list(range(5))
    assert [f["n"] for f in result["candidates"]["five-n1"]["folds"]] == [2] * 5
    timing["software_only"] = True
    atomic_json(tmp_path / "timing.json", timing)
    with pytest.raises(ValueError, match="physical"):
        select_development(tmp_path, tmp_path / "timing.json", tmp_path / "selection.json")
    timing["software_only"] = False
    timing["methods"]["five-n1"]["cold_complete"] = False
    atomic_json(tmp_path / "timing.json", timing)
    with pytest.raises(ValueError, match="cold"):
        select_development(tmp_path, tmp_path / "timing.json", tmp_path / "selection.json")
