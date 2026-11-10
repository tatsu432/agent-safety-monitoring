import importlib.util
from pathlib import Path

import pytest


def controller():
    spec = importlib.util.spec_from_file_location(
        "followup_controller", Path("scripts/analysis/followup-controller.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase_order_preserves_calibration_before_test_and_diagnostics_last():
    module = controller()
    phase = "pilot"
    observed = []
    while phase != "analysis":
        observed.append(phase)
        phase = module.next_phase(phase)
    assert observed.index("development") < observed.index("calibration-0")
    assert observed.index("calibration-7") < observed.index("test-0")
    assert observed.index("test-7") < observed.index("review-dev")
    assert len(observed) == len(set(observed)) == 24
    with pytest.raises(ValueError):
        module.next_phase("unknown")


def test_failed_allocation_cannot_submit_a_successor(tmp_path, monkeypatch):
    module = controller()
    monkeypatch.chdir(tmp_path)
    calls = []

    def fake_command(*args, **kwargs):
        calls.append(args)
        assert args[0] == "sacct"
        return "JobID|State|ElapsedRaw|AllocTRES\n123|FAILED|30|gres/gpu=1"

    monkeypatch.setattr(module, "command", fake_command)
    with pytest.raises(ValueError, match="allocation failed"):
        module.main("pilot", "123")
    assert len(calls) == 1
    assert not (tmp_path / "runs/extra-check/continuation.json").exists()


def test_reconciled_phase_cannot_be_submitted_twice(tmp_path, monkeypatch):
    from agent_safety_monitoring.io import atomic_json

    module = controller()
    monkeypatch.chdir(tmp_path)
    atomic_json(
        tmp_path / "runs/extra-check/continuation.json",
        {"completed": {"pilot": {"job_id": "123"}}, "cap_hours": 90},
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("No Slurm query/submission allowed for a reconciled phase")

    monkeypatch.setattr(module, "command", forbidden)
    with pytest.raises(ValueError, match="already reconciled"):
        module.main("pilot", "123")
