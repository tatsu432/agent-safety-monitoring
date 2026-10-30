import importlib.util
from pathlib import Path

import pytest

from agent_safety_monitoring.io import atomic_json

spec = importlib.util.spec_from_file_location(
    "study_controller", Path(__file__).parents[1] / "docs/reference/yale-study-controller.py"
)
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


def test_shard_order_and_coverage(tmp_path):
    assert controller.next_stage("calibration", 0) == ("calibration", 1)
    assert controller.next_stage("calibration", 7) == ("test", 0)
    assert controller.next_stage("test", 7) is None
    with pytest.raises(ValueError):
        controller.next_stage("test", 8)
    atomic_json(
        tmp_path / "study.json",
        {"identity": "id", "freeze": controller.FREEZE, "configuration": {"methods": [1, 2]}},
    )
    atomic_json(tmp_path / "calibration-execution.json", {"shards": 8})
    atomic_json(
        tmp_path / "calibration-shard-0-manifest.json",
        {"shards": 8, "shard": 0, "identity": "id", "selected": ["a", "b"]},
    )
    summary = {
        "run_identity": "id",
        "job_id": "42",
        "state": "complete",
        "expected": 4,
        "completed_results": 4,
    }
    atomic_json(tmp_path / "calibration-shard-0-summary.json", summary)
    assert controller.verify_shard(tmp_path, "calibration", 0, "42") == 4
    summary["completed_results"] = 3
    atomic_json(tmp_path / "calibration-shard-0-summary.json", summary)
    with pytest.raises(ValueError, match="incomplete"):
        controller.verify_shard(tmp_path, "calibration", 0, "42")


def test_submission_cap_and_duplicate_safety(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SLURM_JOB_ID", "700")
    atomic_json(tmp_path / "runs/submissions.json", {"submissions": []})
    calls = []
    usage = [89.5]

    def fake_output(*args, **kwargs):
        calls.append(args)
        if args[0] == "sacct":
            return (
                "JobID|State|ElapsedRaw|AllocTRES|Comment\n1|COMPLETED|"
                + str(int(usage[0] * 3600))
                + "|gres/gpu=1|"
            )
        if args[0] == "squeue":
            return "700|coordinator"
        if args[0] == "sbatch":
            return "900"
        raise AssertionError(args)

    monkeypatch.setattr(controller, "output", fake_output)
    with pytest.raises(RuntimeError, match="Insufficient"):
        controller.submit_next("calibration", 1)
    assert not any(c[0] == "sbatch" for c in calls)
    usage[0] = 6
    assert controller.submit_next("calibration", 1) == "900"
    assert any(c[0] == "sbatch" and "--time=480" in c for c in calls)
    with pytest.raises(RuntimeError, match="Prior or ambiguous"):
        controller.submit_next("calibration", 1)
