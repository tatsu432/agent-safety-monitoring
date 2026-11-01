"""Scientific safeguards for the separate post-hoc analysis path."""

import json
from copy import deepcopy

import pytest

from agent_safety_monitoring.analysis.aggregate import (
    injection_summary,
    numeric_tree,
    signed_interval,
)
from agent_safety_monitoring.analysis.audit import validate_pairs, verify_manifest
from agent_safety_monitoring.analysis.model_review import (
    Proposal,
    blinded_payload,
    coverage_status,
    validated_references,
)
from agent_safety_monitoring.analysis.records import objective_bootstrap
from agent_safety_monitoring.io import digest
from agent_safety_monitoring.schema import CanonicalTrajectory


def tables():
    cal = [
        {"trajectory_id": f"c{i}", "task_id": f"cal{i}", "label": 0, "score": 5} for i in range(4)
    ]
    test = [
        {"trajectory_id": "b", "task_id": "t", "label": 0, "score": 1, "objective": None},
        {"trajectory_id": "a", "task_id": "t", "label": 1, "score": 5, "objective": "x"},
    ]
    return {
        "calibration": {"one": cal, "two": deepcopy(cal)},
        "test": {"one": test, "two": deepcopy(test)},
    }


def test_pair_metadata_not_only_ids():
    t = tables()
    validate_pairs(t)
    t["test"]["two"][1]["label"] = 0
    with pytest.raises(ValueError, match="metadata"):
        validate_pairs(t)


@pytest.mark.parametrize("change", ["duplicate", "leakage", "calibration_attack", "missing"])
def test_reject_invalid_pairs(change):
    t = tables()
    if change == "duplicate":
        t["test"]["one"].append(t["test"]["one"][0])
    elif change == "leakage":
        for rows in t["calibration"].values():
            rows[0]["task_id"] = "t"
    elif change == "calibration_attack":
        for rows in t["calibration"].values():
            rows[0]["label"] = 1
    else:
        t["test"]["two"].pop()
    with pytest.raises(ValueError):
        validate_pairs(t)


def test_signed_interval_reverses_endpoints():
    u = {"paired_tpr_difference_intervals": {"b - a": [-0.4, -0.1]}}
    assert signed_interval(u, "a", "b") == [0.1, 0.4]


def test_objectives_keep_boundary_randomization_and_clustering():
    t = tables()
    result = objective_bootstrap(t["calibration"], t["test"], replicates=20, seed=7)
    assert result["one"]["x"]["ci95"] == [0.05, 0.05]
    assert result["one"] == result["two"]
    assert result["one"]["x"]["usable_replicates"] == 20


def test_freeze_hash_and_real_artifacts_required():
    body = {"software_only": False}
    verify_manifest({"body": body, "hash": digest(body)})
    with pytest.raises(ValueError, match="hash"):
        verify_manifest({"body": body, "hash": "bad"})
    body["software_only"] = True
    with pytest.raises(ValueError, match="Synthetic"):
        verify_manifest({"body": body, "hash": digest(body)})


def injection_rows():
    return [
        {
            "method": "single",
            "trajectory_id": f"r{i}",
            "task_id": "one-task",
            "label": 1,
            "family": f,
            "placement": p,
            "alert_difference": -0.2,
            "miss_difference": 0.2,
            "invalid_injected": False,
            "invalid_neutral": False,
        }
        for i in range(2)
        for f in ["direct", "reviewer"]
        for p in ["early", "late"]
    ]


def test_injections_preserve_task_pairs_and_export_no_ids():
    result = injection_summary(injection_rows(), replicates=20)
    overall = next(r for r in result if r["family"] == "all")
    assert overall["tasks"] == 1
    assert overall["pairs"] == 8
    assert overall["ci95"] == [0.2, 0.2]
    assert "trajectory_id" not in json.dumps(result)
    assert "task_id" not in json.dumps(result)


def test_injection_duplicates_and_sign_errors_rejected():
    rows = injection_rows()
    with pytest.raises(ValueError, match="Duplicate"):
        injection_summary(rows + [rows[0]], 10)
    rows[0]["miss_difference"] = -0.2
    with pytest.raises(ValueError, match="Invalid"):
        injection_summary(rows, 10)


@pytest.mark.parametrize("value", ["private transcript", float("nan"), {"raw": "secret"}])
def test_numeric_export_rejects_payloads(value):
    with pytest.raises(ValueError):
        numeric_tree(value)


def trajectory():
    return CanonicalTrajectory.model_validate(
        {
            "id": "opaque",
            "task": "Legitimate task",
            "segments": [
                {
                    "id": "s1",
                    "role": "assistant",
                    "kind": "text",
                    "text": "abcdef",
                    "source_message": 9,
                    "source_end": 6,
                    "interaction": 1,
                }
            ],
        }
    )


def test_blinded_payload_hides_metadata_and_source_offsets():
    payload = blinded_payload(trajectory())
    assert set(payload) == {"task", "steps"}
    assert set(payload["steps"][0]) == {"step", "role", "kind", "text"}
    assert all(
        x not in json.dumps(payload)
        for x in ["trajectory_id", "objective", "assignment", "source_message", "score"]
    )


def test_model_span_validity_does_not_set_human_provenance():
    p = Proposal(
        conclusion="supported",
        rationale="diagnostic",
        references=[{"step": "s1", "start": 1, "end": 3, "text": "bc"}],
    )
    refs = validated_references(trajectory(), p)
    assert refs[0]["provenance"] == "model_suggested"
    p.references[0].text = "wrong"
    with pytest.raises(ValueError, match="canonical"):
        validated_references(trajectory(), p)


def test_supported_requires_evidence_and_duplicate_spans_rejected():
    with pytest.raises(ValueError):
        validated_references(
            trajectory(), Proposal(conclusion="supported", rationale="test", references=[])
        )
    ref = {"step": "s1", "start": 1, "end": 3, "text": "bc"}
    with pytest.raises(ValueError, match="Duplicate"):
        validated_references(
            trajectory(), Proposal(conclusion="supported", rationale="test", references=[ref, ref])
        )


def test_partial_and_union_span_coverage():
    refs = [{"step": "s", "start": 2, "end": 8}]
    selected = [{"step": "s", "start": 0, "end": 5}, {"step": "s", "start": 5, "end": 9}]
    assert coverage_status(refs, selected) == {"full": 1, "partial": 0, "missing": 0}
    assert coverage_status(refs, selected[:1]) == {"full": 0, "partial": 1, "missing": 0}
    assert coverage_status(refs, []) == {"full": 0, "partial": 0, "missing": 1}


def test_model_review_private_resume_and_no_human_claim(tmp_path, monkeypatch):
    import asyncio

    from agent_safety_monitoring.analysis import model_review as review
    from agent_safety_monitoring.io import atomic_json, read_json
    from agent_safety_monitoring.schema import CallRecord

    payload = blinded_payload(trajectory())
    packet = tmp_path / "packet.json"
    atomic_json(
        packet,
        {
            "freeze": "freeze",
            "phase": "development",
            "system_hash": digest(review.SYSTEM),
            "records": [{"trajectory_id": "opaque", "payload": payload}],
        },
    )
    config = __import__("pathlib").Path("configs/analysis/model-review.json")
    calls_seen = []

    class FakeBackend:
        def __init__(self, *args):
            pass

        async def close(self):
            pass

        async def generate(self, messages, *args, **kwargs):
            calls_seen.append(messages)
            return [
                CallRecord(
                    key="key",
                    stage="model-reference",
                    attempt=0,
                    started="now",
                    completed="now",
                    latency_seconds=1,
                    response=json.dumps(
                        {
                            "conclusion": "supported",
                            "rationale": "unverified interpretation",
                            "references": [{"step": "s1", "start": 1, "end": 3, "text": "bc"}],
                        }
                    ),
                )
            ]

    class FakeTracking:
        def __init__(self, *args, **kwargs):
            pass

        def log(self, **kwargs):
            pass

        def close(self):
            pass

    monkeypatch.setattr(review, "Backend", FakeBackend)
    monkeypatch.setattr(review, "Telemetry", FakeTracking)
    result = asyncio.run(review.run_review(packet, config, tmp_path / "output"))
    assert result["span_valid_records"] == 1
    assert result["human_reviewed_records"] == 0
    assert not result["hardware_verified"]
    saved = read_json(tmp_path / "output/annotations/opaque.json")
    assert saved["references"][0]["provenance"] == "model_suggested"
    assert not saved["human_reviewed"]
    assert "objective" not in calls_seen[0][1]["content"]
    asyncio.run(review.run_review(packet, config, tmp_path / "output"))
    assert len(calls_seen) == 1


def test_heldout_review_requires_development_acceptance(tmp_path):
    import asyncio
    from pathlib import Path

    from agent_safety_monitoring.analysis.model_review import SYSTEM, run_review
    from agent_safety_monitoring.io import atomic_json

    packet = tmp_path / "packet.json"
    atomic_json(packet, {"phase": "test", "system_hash": digest(SYSTEM)})
    with pytest.raises(ValueError, match="proof required"):
        asyncio.run(run_review(packet, Path("configs/analysis/model-review.json"), tmp_path))


def test_acceptance_requires_completed_physical_allocation(tmp_path):
    from agent_safety_monitoring.analysis.model_review import accept_development
    from agent_safety_monitoring.io import atomic_json

    summary, runtime, sacct = [tmp_path / name for name in ["summary", "runtime", "sacct"]]
    atomic_json(
        summary,
        {"phase": "development", "expected": 3, "span_valid_records": 3, "config_hash": "hash"},
    )
    atomic_json(
        runtime,
        {
            "job_id": "1",
            "config_hash": "hash",
            "hardware_verified": True,
            "container_verified": True,
            "engine_verified": True,
        },
    )
    sacct.write_text("JobID|State|ElapsedRaw|AllocTRES\n1|FAILED|60|gres/gpu=1\n")
    with pytest.raises(ValueError, match="successful measured"):
        accept_development(summary, runtime, sacct, tmp_path / "accepted")
    sacct.write_text("JobID|State|ElapsedRaw|AllocTRES\n1|COMPLETED|60|gres/gpu=1\n")
    accepted = accept_development(summary, runtime, sacct, tmp_path / "accepted")
    assert accepted["allocation_gpu_seconds"] == 60


def test_reviewer_wrapper_configuration_is_enforced():
    from pathlib import Path

    from agent_safety_monitoring.analysis.model_review import check_model_config

    config = json.loads(Path("configs/analysis/model-review.json").read_text())
    check_model_config(config)
    config["model"]["base_url"] = "https://example.com/v1"
    with pytest.raises(ValueError):
        check_model_config(config)


def test_public_method_discards_extra_private_fields():
    from agent_safety_monitoring.analysis.aggregate import public_method

    primary = dict.fromkeys(
        [
            "tpr",
            "fpr",
            "auroc_valid",
            "invalid_rate",
            "n",
            "n_valid",
            "n_invalid",
            "valid_score_coverage",
            "n_attacks",
            "n_benign",
        ],
        0,
    )
    primary["policy"] = {
        "cutoff": 5,
        "boundary_probability": 0.5,
        "target_fpr": 0.05,
        "achieved_fpr": 0.05,
        "feasible": True,
        "raw_text": "PRIVATE_SENTINEL",
    }
    primary["reasoning_text"] = "PRIVATE_SENTINEL"
    cost = dict.fromkeys(
        [
            "logical_calls",
            "cache_hits",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "reasoning_tokens_estimated",
            "reasoning_tokens_exposed",
            "reasoning_estimates_exposed",
            "request_latency_sum_seconds",
        ],
        0,
    )
    cost["raw_calls"] = ["PRIVATE_SENTINEL"]
    value = {
        "primary": primary,
        "deterministic": primary,
        "cost": cost,
        "raw_text": "PRIVATE_SENTINEL",
        "per_objective": {
            o: {"n": 1, "tpr": 0.5, "raw": "PRIVATE_SENTINEL"}
            for o in [
                "firewall_disabling",
                "malware_execution",
                "privilege_escalation",
                "secret_exfiltration",
            ]
        },
    }
    exported = json.dumps(public_method(value))
    assert "PRIVATE_SENTINEL" not in exported
    assert "raw_calls" not in exported


def test_injection_metadata_cannot_change_between_conditions():
    rows = injection_rows()
    rows[0]["task_id"] = "different"
    with pytest.raises(ValueError, match="metadata differs"):
        injection_summary(rows, 10)
