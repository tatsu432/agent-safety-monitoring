from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_safety_monitoring.cli import app
from agent_safety_monitoring.experiments.demo import demo
from agent_safety_monitoring.experiments.injection_runner import run_injections_sync
from agent_safety_monitoring.experiments.injections import PAYLOADS, matched_control
from agent_safety_monitoring.experiments.runner import create_freeze, run_sync, validate_freeze
from agent_safety_monitoring.inference.backend import ModelConfig, Tokenizer
from agent_safety_monitoring.io import atomic_json, read_json
from agent_safety_monitoring.monitors.core import evidence_payload
from agent_safety_monitoring.reporting.report import generate
from agent_safety_monitoring.schema import CanonicalTrajectory


def test_full_workflow_freeze_resume_injections_and_coverage(tmp_path):
    result = demo(tmp_path)
    assert result["software_only"] and result["last_run"]["invalid"] == 0
    data = tmp_path / "data"
    frozen = read_json(tmp_path / "freeze.json")
    config = frozen["body"]["config"]
    assert create_freeze(data, config, tmp_path / "freeze.json") == frozen
    resumed = run_sync(data, tmp_path / "results", config, "test", frozen)
    assert resumed["resumed"] == resumed["completed"] == 60
    injected = run_injections_sync(
        data, tmp_path / "secondary", frozen, tmp_path / "report" / "metrics.json"
    )
    assert injected["comparisons"] == 12 * 2 * 3 * 2
    # Never tune/reconfigure the held-out run without a new freeze.
    with pytest.raises(ValueError, match="Configuration differs"):
        run_sync(
            data,
            tmp_path / "results",
            {**config, "methods": [{"method": "single"}]},
            "test",
            frozen,
        )
    # Missing results must be a visible report error, even if the remaining outputs parse.
    root = Path(resumed["run_root"])
    missing = next((root / "test").glob("*/*.json"))
    missing.unlink()
    with pytest.raises(ValueError, match="coverage"):
        generate(root, tmp_path / "incomplete", replicates=2)
    # Mutating even monitor-facing text after freeze is rejected.
    trajectory = next((data / "trajectories").glob("*.json"))
    payload = read_json(trajectory)
    payload["task"] = "modified after freeze"
    atomic_json(trajectory, payload)
    with pytest.raises(ValueError, match="trajectory changed"):
        validate_freeze(frozen, data)


def test_cli_help_and_held_out_guard(tmp_path):
    runner = CliRunner()
    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert runner.invoke(app, ["experiment", "freeze", "--help"]).exit_code == 0
    config = tmp_path / "config.json"
    atomic_json(config, {"model": {"backend": "mock"}, "methods": [{"method": "single"}]})
    response = runner.invoke(app, ["experiment", "run", "--config", str(config), "--split", "test"])
    assert response.exit_code != 0
    assert "requires a frozen" in str(response.exception)


def test_neutral_controls_match_tokens():
    tokens = Tokenizer(ModelConfig())
    for family, payload in PAYLOADS.items():
        assert tokens.count(matched_control(family, tokens)) == tokens.count(payload)


def test_payload_never_exposes_original_message_indices(tmp_path):
    demo(tmp_path)
    path = next((tmp_path / "data" / "trajectories").glob("*.json"))
    t = CanonicalTrajectory.model_validate(read_json(path))
    payload = evidence_payload(t)
    assert "source_message" not in payload["segments"][0]


def test_freeze_requires_real_readiness(tmp_path):
    data = tmp_path / "data"
    atomic_json(data / "manifest.json", {"records": [], "rejected": []})
    with pytest.raises(ValueError, match="pinned"):
        create_freeze(
            data,
            {"model": {"backend": "vllm"}, "methods": [{"method": "single"}]},
            tmp_path / "freeze.json",
        )
