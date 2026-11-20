from types import SimpleNamespace

import pytest

from agent_safety_monitoring.analysis.adaptive import apply_policy, route
from agent_safety_monitoring.analysis.extension_eae import clean_quotes, expanded_quotes
from agent_safety_monitoring.analysis.reasoning_profile import cohort_acceptance
from agent_safety_monitoring.data.reasoning import ReleaseProof, linked_actions, restricted_copy
from agent_safety_monitoring.monitors.core import evidence_payload
from agent_safety_monitoring.schema import CanonicalTrajectory, Segment


def test_adaptive_prefix_and_referral():
    bands = [(40, 70), (40, 60), (0, 100), (0, 100)]
    assert route([95, None, None, None, None], "gate-5", bands) == (95, 1)
    assert route([55, None, 90, 50, 60], "gate-5", bands) == (None, 2)
    assert route([55, 95, None, None, None], "sequential-5", bands) == (75, 2)
    assert route([55, None, 90, 50, 60], "fixed-5") == (None, 5)

    def review(input_tokens):
        return {"calls": [{"usage": {"input_tokens": input_tokens, "output_tokens": 1}}]}

    row = {
        "trajectory_id": "p",
        "task_id": "t",
        "label": 1,
        "objective": "o",
        "reviews": [review(i) for i in range(5)],
        "scores": [95, None, 77, 50, 66],
        "seconds_per_call": 7,
    }
    result = apply_policy([row], "gate-5", bands)[0]
    assert result["reviews"] == result["output_tokens"] == 1
    assert result["estimated_gpu_seconds"] == 7


def example():
    def step(id_, kind, text, index, interaction=1):
        return Segment(
            id=id_,
            kind=kind,
            text=text,
            role="tool" if kind == "tool_result" else "assistant",
            source_message=index,
            source_end=len(text),
            interaction=interaction,
        )

    return CanonicalTrajectory(
        id="case",
        task="Legitimate task",
        segments=[
            step("s1", "text", "Already visible", 1),
            step("s2", "tool_call", "action", 1),
            step("s3", "tool_result", "observation", 2),
            step("s4", "tool_call", "another action", 3, 2),
        ],
    )


def test_four_views_are_cited_but_keep_source_metadata_private():
    trajectory = example()
    tokens = SimpleNamespace(count=lambda x: len(x.split()))
    views = restricted_copy(
        trajectory,
        [
            (1, "tool", "  recorded text\n"),
            (3, "tool", "Already visible"),
            (4, "submit", "excluded submission reasoning"),
        ],
        tokens,
    )
    assert views["ACTION_ONLY"] is trajectory
    assert [s.id for s in views["ACTION_PLUS_REASONING"].segments] == [
        "r00000",
        "s1",
        "s2",
        "s3",
        "s4",
    ]
    only = evidence_payload(views["REASONING_ONLY"])
    assert only["segments"][0]["text"] == "  recorded text\n"
    assert "source_message" not in only["segments"][0]
    assert len(only["segments"]) == 1
    masked = views["REASONING_MASKED_CONTROL"].segments[0]
    assert masked.kind == "reasoning_availability"
    assert "1–63" in masked.text
    assert "recorded text" not in masked.text


def test_reasoning_links_require_identical_independent_call_sequence():
    call = SimpleNamespace(id="call-a", function="tool", arguments={"field": "value"})
    msg = SimpleNamespace(role="assistant", tool_calls=[call])
    nested = SimpleNamespace(
        event="model",
        output=SimpleNamespace(
            choices=[
                SimpleNamespace(message=msg),
            ]
        ),
    )
    action = {
        "tool_call_id": call.id,
        "function": call.function,
        "arguments": call.arguments,
        "index": 0,
        "extended_thinking": "candidate",
    }
    sample = SimpleNamespace(
        metadata={"control_tower_overlay": {"actions": [action]}},
        messages=[msg],
        events=[nested],
    )
    assert linked_actions(sample) == [(0, "tool", "candidate")]
    action["arguments"] = {}
    with pytest.raises(ValueError, match="call_payload_mismatch"):
        linked_actions(sample)


def test_authorship_proof_is_release_specific():
    proof = ReleaseProof(
        version=1,
        sources={"a": "hash"},
        field="metadata.control_tower_overlay.actions[].extended_thinking",
        author="monitored_agent",
        representation="provider_reasoning",
        release_evidence="Release-specific verified producer attestation",
    )
    proof.verify({"a": "hash"})
    with pytest.raises(ValueError, match="proof"):
        proof.verify({"a": "a different hash"})


def test_cohort_acceptance_is_task_aware():
    rows = [
        {
            "split": split,
            "assignment": kind,
            "outcome": "success",
            "task_id": "1",
            "single_cohort": True,
        }
        for split in ("development", "calibration", "test")
        for kind in ("attack", "benign")
        if not (split == "calibration" and kind == "attack")
    ]
    assert cohort_acceptance(rows)["passes_coverage_gate"]
    rows[-1]["single_cohort"] = False
    assert not cohort_acceptance(rows)["passes_coverage_gate"]


def test_eae_expands_to_enclosing_call_and_result_with_exact_spans():
    trajectory = example()
    quote = {"step": "s2", "start": 1, "end": 4, "text": "cti"}
    refs = clean_quotes([quote], trajectory)
    assert [q.step for q in expanded_quotes(refs, trajectory)] == ["s1", "s2", "s3"]
    with pytest.raises(ValueError, match="Invalid source quote"):
        clean_quotes([{**quote, "text": "different"}], trajectory)
