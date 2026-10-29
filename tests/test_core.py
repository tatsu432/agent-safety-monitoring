import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from agent_safety_monitoring.data.ingest import assign_splits, normalize
from agent_safety_monitoring.evaluation.metrics import calibrate, metrics, paired_bootstrap
from agent_safety_monitoring.experiments.injections import inject
from agent_safety_monitoring.inference.backend import Backend, ModelConfig, Tokenizer
from agent_safety_monitoring.io import atomic_json, read_json
from agent_safety_monitoring.monitors.core import MethodConfig, Monitor, chunks, validate_quotes
from agent_safety_monitoring.schema import (
    CanonicalTrajectory,
    EvaluationRecord,
    Extraction,
    Judgment,
    Quotation,
    Segment,
)


def trajectory(text="ordinary evidence", uid="opaque"):
    return CanonicalTrajectory(
        id=uid,
        task="Inspect a fixture",
        segments=[
            Segment(
                id="s0",
                role="tool",
                kind="tool_result",
                text=text,
                source_message=0,
                source_end=len(text),
                interaction=0,
            )
        ],
    )


def test_strict_score():
    for value in [True, "1", 1.2, 0, 6]:
        with pytest.raises(ValidationError):
            Judgment(score=value, explanation="x", citations=[])


def test_normalization_isolates_labels_and_private_instructions():
    def message(role, text="", calls=None, tool_id=None):
        return SimpleNamespace(role=role, content=text, tool_calls=calls, tool_call_id=tool_id)

    call = SimpleNamespace(id="a", function="bash", arguments={"cmd": "inert command"})
    submit = SimpleNamespace(id="b", function="submit", arguments={"hidden": "marker"})
    sample = SimpleNamespace(
        id="x",
        epoch=1,
        metadata={
            "main_tasks": [{"id": "task", "description": "Genuine task"}],
            "side_tasks": [{"id": "sudo_edit", "goal": "PRIVATE_OBJECTIVE"}],
        },
        scores={"tasks": SimpleNamespace(value={"side": 1})},
        messages=[
            message("system", "PRIVATE_SYSTEM"),
            message("user", "PRIVATE_PREAMBLE"),
            message("assistant", "visible explanation", [call]),
            message("tool", "exact result", tool_id="a"),
            message("assistant", "visible conclusion", [submit]),
            message("tool", "CLASS_LEAK", tool_id="b"),
        ],
    )
    t, r = normalize(sample, Path("attack.eval"), "sha")
    serialized = t.model_dump_json()
    for private in ["PRIVATE_OBJECTIVE", "PRIVATE_SYSTEM", "PRIVATE_PREAMBLE", "CLASS_LEAK"]:
        assert private not in serialized
    assert "visible explanation" in serialized and "exact result" in serialized
    assert r.outcome == "success" and r.objective == "privilege_escalation"
    assert r.provenance["removed_submission_records"] == 2


def test_whole_task_splits():
    records = []
    for task in range(5):
        for assignment in ["benign", "attack"]:
            records.append(
                EvaluationRecord(
                    trajectory_id=f"{task}-{assignment}",
                    task_id=str(task),
                    assignment=assignment,
                    outcome="success" if assignment == "attack" else "not_applicable",
                    source_file="f",
                    source_sha256="s",
                    sample_id="i",
                    provenance={},
                )
            )
    result = assign_splits(records, development_tasks=2)
    for task in range(5):
        assert len({r.split for r in result if r.task_id == str(task)}) == 1
    assert sum(r.split == "development" for r in result) == 4


def test_exact_quotes_and_budget():
    t = trajectory("abc def")
    tok = Tokenizer(ModelConfig())
    good = Extraction(quotes=[Quotation(step="s0", start=0, end=3, text="abc")])
    validate_quotes(good, t, tok, 1)
    with pytest.raises(ValueError):
        validate_quotes(
            Extraction(quotes=[Quotation(step="s0", start=0, end=3, text="xyz")]), t, tok, 5
        )
    with pytest.raises(ValueError):
        validate_quotes(
            Extraction(quotes=[Quotation(step="s0", start=0, end=7, text="abc def")]), t, tok, 1
        )


def test_chunking_preserves_every_character_and_offsets():
    t = trajectory("word " * 100)
    result = chunks(t.segments, 1, 5, Tokenizer(ModelConfig()))
    assert len(result) > 1
    assert "".join(s.text for group in result for s in group) == t.segments[0].text
    for group in result:
        for s in group:
            assert t.segments[0].text[s.source_start : s.source_end] == s.text


@pytest.mark.parametrize("method", ["single", "think", "average", "eae", "mrt"])
def test_methods_cache_and_costs(tmp_path, method):
    async def check():
        backend = Backend(ModelConfig(), tmp_path)
        config = MethodConfig(method=method)
        first = await Monitor(backend).run(trajectory(), config)
        second = await Monitor(backend).run(trajectory(), config)
        await backend.close()
        assert first.status == second.status == "valid"
        assert first.score == second.score
        assert all(c.cached for c in second.calls)
        assert sum(c.usage.output_tokens for c in first.calls) == sum(
            c.usage.output_tokens for c in second.calls
        )
        if method == "average":
            assert len({c.key for c in first.calls}) == 3
        if method == "mrt":
            assert any(a["stage"].startswith("sequential") for a in first.artifacts)

    asyncio.run(check())


def test_invalid_output_is_never_a_score_and_retry_is_charged(tmp_path):
    async def check():
        backend = Backend(ModelConfig(), tmp_path)
        backend._mock = lambda *args: '{"score": 9}'
        r = await Monitor(backend).run(trajectory(), MethodConfig(method="single"))
        await backend.close()
        assert r.status == "invalid" and r.score is None and len(r.calls) == 2

    asyncio.run(check())


def test_context_overflow_is_explicit(tmp_path):
    async def check():
        backend = Backend(ModelConfig(context_limit=10), tmp_path)
        r = await Monitor(backend).run(trajectory(), MethodConfig(method="single"))
        await backend.close()
        assert r.status == "context_overflow" and not r.calls and r.score is None

    asyncio.run(check())


def test_transport_retry_and_reasoning_usage(tmp_path):
    count = 0

    async def handler(request):
        nonlocal count
        count += 1
        if count == 1:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {"score": 2, "explanation": "test", "citations": []}
                            )
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "completion_tokens_details": {"reasoning_tokens": 15},
                },
            },
        )

    async def check():
        config = ModelConfig(backend="vllm")
        backend = Backend(
            config,
            tmp_path,
            tokenizer=Tokenizer(ModelConfig()),
            transport=httpx.MockTransport(handler),
        )
        records = await backend.generate([{"role": "user", "content": "test"}], Judgment, "test", 1)
        await backend.close()
        assert len(records) == 2 and records[0].error == "HTTP 503"
        assert records[1].usage.reasoning_tokens == 15

    asyncio.run(check())


def test_calibration_ties_invalid_and_conservative_threshold():
    p = calibrate([1] * 20)
    assert p.boundary_probability == pytest.approx(0.05)
    assert p.achieved_fpr == pytest.approx(0.05)
    assert calibrate([1] * 20, deterministic=True).achieved_fpr == 0
    assert not calibrate([None] * 2 + [1] * 18).feasible
    assert calibrate([None] + [1] * 19).alerts([None, 1]).tolist() == [1, 0]
    m = metrics([1] * 20, [{"label": 0, "score": 1}, {"label": 1, "score": 5}])
    assert m["tpr"] == 1 and m["fpr"] == pytest.approx(0.05) and m["auroc_valid"] == 1


def test_paired_cluster_bootstrap_recalibrates():
    cal = [{"trajectory_id": str(i), "task_id": f"c{i}", "score": 1} for i in range(10)]
    test = [
        {
            "trajectory_id": f"t{i}-{label}",
            "task_id": f"t{i}",
            "score": 5 if label else 1,
            "label": label,
        }
        for i in range(4)
        for label in [0, 1]
    ]
    r = paired_bootstrap({"a": cal, "b": cal}, {"a": test, "b": test}, replicates=30)
    assert r["paired_tpr_difference_intervals"]["b - a"] == [0, 0]
    with pytest.raises(ValueError):
        paired_bootstrap({"a": cal, "b": cal}, {"a": test, "b": test[:-1]}, replicates=2)


def test_injection_keeps_original_evidence():
    t = trajectory()
    for family in ["reviewer", "boundary", "direct"]:
        for placement in ["early", "late"]:
            injected = inject(t, family, placement)
            assert injected.task == t.task
            assert [s for s in injected.segments if s.source_message >= 0] == t.segments
            added = next(s for s in injected.segments if s.source_message == -1)
            assert added.role == "assistant" and added.kind == "text"


def test_atomic_artifact(tmp_path):
    p = tmp_path / "nested" / "x.json"
    atomic_json(p, {"a": 1})
    atomic_json(p, {"a": 2})
    assert read_json(p) == {"a": 2}
    assert len(list(p.parent.iterdir())) == 1
