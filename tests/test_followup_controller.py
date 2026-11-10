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
