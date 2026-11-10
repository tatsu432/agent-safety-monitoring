import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_core import trajectory

from agent_safety_monitoring.experiments.followup import (
    FINE_SYSTEM,
    FineJudgment,
    FollowupConfig,
    coarsen_hundred,
    freeze_followup,
    nested_scores,
    protocol_identity,
    run_followup,
)
from agent_safety_monitoring.inference.backend import ModelConfig
from agent_safety_monitoring.io import atomic_json, digest, read_json
from agent_safety_monitoring.monitors.core import MethodConfig
from agent_safety_monitoring.schema import Judgment


def test_fine_schema_is_strict_and_legacy_remains_unchanged():
    for s in [0, 50, 100]:
        assert FineJudgment(score=s, explanation="x", citations=[]).score == s
    for s in [-1, 101, True, "50", 50.5]:
        with pytest.raises(ValidationError):
            FineJudgment(score=s, explanation="x", citations=[])
    with pytest.raises(ValidationError):
        Judgment(score=100, explanation="x", citations=[])
    assert "not a probability" in FINE_SYSTEM
    assert "integer 0–100" in FINE_SYSTEM and "integer 1–5" not in FINE_SYSTEM
    # Original normalization / configuration identity stays identical.
    assert digest(MethodConfig(method="single").model_dump()).startswith("419328b0dd6f")
    assert protocol_identity(FollowupConfig()) != protocol_identity(FollowupConfig(seed=2))


def test_nested_invalidity_and_bin_edges():
    reviews = [dict(status="valid", score=s) for s in [0, 100, 50, 25, 75]]
    assert nested_scores(reviews) == {"1": 0, "2": 50, "3": 50, "5": 50}
    reviews[2] = dict(status="invalid", score=None)
    assert nested_scores(reviews) == {"1": 0, "2": 50, "3": None, "5": None}
    assert [coarsen_hundred(s) for s in [0, 19, 20, 40, 60, 80, 100, None]] == [
        1,
        1,
        2,
        3,
        4,
        5,
        5,
        None,
    ]


def test_resume_identity_and_heldout_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("ASM_TRACKING_MODE", "disabled")
    data, output = tmp_path / "data", tmp_path / "out"
    t = trajectory()
    record = dict(
        trajectory_id=t.id,
        task_id="task",
        split="development",
        assignment="benign",
        outcome="not_applicable",
        exclusion=None,
    )
    manifest = {"records": [record]}
    atomic_json(data / "manifest.json", manifest)
    atomic_json(data / "trajectories" / f"{t.id}.json", t.model_dump())
    from agent_safety_monitoring.io import file_hash

    body = {
        "software_only": False,
        "dataset_manifest": digest(manifest),
        "trajectory_hashes": {t.id: file_hash(data / "trajectories" / f"{t.id}.json")},
        "config": {"model": ModelConfig().model_dump()},
    }
    freeze, config = tmp_path / "original.json", tmp_path / "config.json"
    atomic_json(freeze, {"body": body, "hash": digest(body)})
    atomic_json(config, FollowupConfig().model_dump())

    async def check():
        first = await run_followup(data, freeze, config, output)
        assert first["completed"] == 10 and first["invalid"] == 0 and first["software_only"]
        files = {p.name: p.read_bytes() for p in (output / "development").glob("*.json")}
        assert (await run_followup(data, freeze, config, output)) == first
        assert files == {p.name: p.read_bytes() for p in (output / "development").glob("*.json")}
        with pytest.raises(ValueError, match="requires|requires|require"):
            await run_followup(data, freeze, config, output, split="test")
        atomic_json(config, FollowupConfig(seed=12).model_dump())
        with pytest.raises(ValueError, match="identity"):
            await run_followup(data, freeze, config, output)

    asyncio.run(check())
    with pytest.raises((ValueError, FileNotFoundError)):
        freeze_followup(
            output, Path("missing"), Path("missing"), Path("missing"), tmp_path / "freeze"
        )
    assert read_json(output / "development-0-summary.json")["software_only"]


def test_followup_report_requires_full_coverage_and_valid_scores(tmp_path):
    from agent_safety_monitoring.experiments.followup import followup_report

    identity = {
        "config": FollowupConfig().model_dump(),
        "expected": {"calibration": ["c1", "c2"], "test": ["b", "a"]},
    }
    atomic_json(tmp_path / "identity.json", identity)
    for split, records in [
        ("calibration", [("c1", "c1", "benign"), ("c2", "c2", "benign")]),
        ("test", [("b", "t", "benign"), ("a", "t", "attack")]),
    ]:
        atomic_json(
            tmp_path / f"{split}-0-geometry.json",
            {"shard": 0, "shards": 1, "expected_ids": [r[0] for r in records]},
        )
        for uid, task, assignment in records:
            row = dict(
                trajectory_id=uid,
                task_id=task,
                assignment=assignment,
                outcome="success" if assignment == "attack" else "not_applicable",
                split=split,
            )
            for scale in ["five", "hundred"]:
                for i in range(5):
                    score = (5 if scale == "five" else 100) if assignment == "attack" else 1
                    atomic_json(
                        tmp_path / split / f"{uid}-{scale}-{i}.json",
                        {
                            "key": {
                                "trajectory_id": uid,
                                "scale": scale,
                                "sample": i,
                                "seed": 20261028 + i * 100,
                                "identity": digest(identity),
                                "evaluation": row,
                            },
                            "review": {"status": "valid", "score": score},
                        },
                    )
    assert followup_report(tmp_path, tmp_path / "report.json", 5)["methods"] == 16
    from agent_safety_monitoring.analysis.followup import load_split

    for i, score in enumerate([19, 21, 50, 75, 100]):
        path = tmp_path / f"test/a-hundred-{i}.json"
        sample = read_json(path)
        sample["review"]["score"] = score
        atomic_json(path, sample)
    tables, _, _, _, _ = load_split(tmp_path, "test")
    assert next(r["score"] for r in tables["hundred-binned-n2"] if r["label"]) == 2
    assert next(r["score"] for r in tables["hundred-bin-first-n2"] if r["label"]) == 1.5
    invalid = tmp_path / "test/a-hundred-1.json"
    sample = read_json(invalid)
    sample["review"] = {"status": "invalid", "score": None}
    atomic_json(invalid, sample)
    tables, _, _, _, _ = load_split(tmp_path, "test")
    assert next(r["score"] for r in tables["hundred-bin-first-n2"] if r["label"]) is None
    target = tmp_path / "test/a-hundred-4.json"
    saved = read_json(target)
    saved["review"]["score"] = 101
    atomic_json(target, saved)
    with pytest.raises(ValueError, match="ordinal"):
        followup_report(tmp_path, tmp_path / "report.json", 5)
    target.unlink()
    with pytest.raises(ValueError, match="coverage"):
        followup_report(tmp_path, tmp_path / "report.json", 5)
