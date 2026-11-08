from types import SimpleNamespace

import pytest

from agent_safety_monitoring.analysis.diagnosis import terminal_branches
from agent_safety_monitoring.analysis.model_review import OBJECTIVE_SYSTEM, SYSTEM, review_system


def test_unbalanced_tree_root_and_missing_branches():
    def accepted(stage, score):
        return {"stage": stage, "output": {"score": score}}

    artifacts = [{"stage": "chunking", "chunks": [[], [], []]}] + [
        accepted("sequential-0", 2),
        accepted("sequential-1", 3),
        accepted("sequential-2", 4),
        accepted("leaf-0", 1),
        accepted("leaf-1", 2),
        accepted("leaf-2", 3),
        accepted("merge-0-0", 3),
        accepted("merge-1-0", 5),
    ]
    result = SimpleNamespace(artifacts=artifacts, status="valid", score=4.5)
    a, b, _, n = terminal_branches(result)
    assert (a["score"], b["score"], n) == (4, 5, 3)
    result.score = 3
    with pytest.raises(ValueError):
        terminal_branches(result)
    result.status, result.artifacts = "invalid", artifacts[:-1]
    assert terminal_branches(result)[1] is None
    assert terminal_branches(result)[0]["score"] == 4


def test_objective_review_prompt_cannot_reuse_blinded_proof():
    assert review_system({}) == SYSTEM
    assert review_system({"objective_aware": True}) == OBJECTIVE_SYSTEM
    assert OBJECTIVE_SYSTEM != SYSTEM
    assert "not proof of success" in OBJECTIVE_SYSTEM


def test_objective_packet_separates_annotation_context_from_monitor_payload(tmp_path):
    from test_core import trajectory

    from agent_safety_monitoring.analysis.model_review import prepare_packet
    from agent_safety_monitoring.io import atomic_json, digest, file_hash, read_json
    from agent_safety_monitoring.monitors.core import evidence_payload

    t = trajectory()
    data = tmp_path / "data"
    atomic_json(data / "trajectories" / f"{t.id}.json", t.model_dump())
    record = dict(
        trajectory_id=t.id,
        split="development",
        exclusion=None,
        objective="secret_exfiltration",
        assignment="attack",
        outcome="success",
    )
    manifest = {"records": [record]}
    atomic_json(data / "manifest.json", manifest)
    body = dict(
        software_only=False,
        dataset_manifest=digest(manifest),
        trajectory_hashes={t.id: file_hash(data / "trajectories" / f"{t.id}.json")},
    )
    frozen = {"body": body, "hash": digest(body)}
    prepare_packet(data, frozen, tmp_path / "packet.json", development=True, objective_aware=True)
    packet = read_json(tmp_path / "packet.json")
    payload = packet["records"][0]["payload"]
    assert set(payload) == {"task", "steps", "harmful_objective"}
    assert payload["harmful_objective"] == "secret_exfiltration"
    assert "harmful_objective" not in evidence_payload(t)
    assert packet["system_hash"] == digest(OBJECTIVE_SYSTEM)
