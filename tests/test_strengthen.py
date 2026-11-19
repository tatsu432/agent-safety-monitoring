import asyncio
import runpy
from types import SimpleNamespace

import pytest

from agent_safety_monitoring.analysis.lengths import development_edges
from agent_safety_monitoring.analysis.operating_points import comparison
from agent_safety_monitoring.experiments.resources import allocation_usage, reconciled_accounting
from agent_safety_monitoring.monitors.core import MethodConfig, Monitor
from agent_safety_monitoring.schema import CanonicalTrajectory, Judgment, MonitoringResult


def test_direct_ledger_accounting_recovers_omitted_allocation():
    header = "JobID|State|ElapsedRaw|AllocTRES|Comment\n"
    seen = []

    def query(args):
        seen.append(args)
        first = "17|COMPLETED|120|gres/gpu:h200=2|asm-one\n"
        second = "18|FAILED|240|gres/gpu=1|asm-two\n"
        return header + (first + second if "-j" in args else first)

    records = reconciled_accounting(
        query,
        [{"job_id": "17"}, {"job_id": "18"}],
        user="owner",
        since="2026-10-28",
        account="course",
    )
    assert seen[0][-2:] == ["-A", "course"]
    assert seen[1][-2:] == ["-j", "17,18"]
    result = allocation_usage(records)
    assert result["allocated_gpu_seconds"] == 480
    assert len(result["jobs"]) == 2


def test_one_percent_referral_floor_and_paired_task_recalibration():
    def row(uid, score, label=0):
        return {"trajectory_id": uid, "task_id": uid, "label": label, "score": score}

    cal = [row(f"c{i}", None if i < 2 else i) for i in range(100)]
    test = [row("b", None), row("a", 100, 1)]
    result = comparison(
        {"first": cal, "second": cal},
        {"first": test, "second": test},
        replicates=50,
        target=0.01,
    )
    point = result["point"]["first"]
    assert point["policy"]["achieved_fpr"] == pytest.approx(0.02)
    assert point["policy"]["feasible"] is False
    assert point["tpr"] == 0
    assert point["fpr"] == 1
    assert result["paired_differences"]["first - second"]["tpr"]["ci95"] == [0.0, 0.0]


def test_development_edges_merge_sparse_neighbors():
    rows = [{"trajectory_id": str(i), "label": int(i % 2 == 0)} for i in range(16)]
    lengths = {str(i): 1000 + i for i in range(16)}
    edges, strategy, counts = development_edges(rows, lengths, minimum=3)
    assert "quartiles" in strategy
    assert len(edges) == 1
    assert all(min(c) >= 3 for c in counts)


def test_fine_monitor_persists_scores_above_legacy_range():
    ns = runpy.run_path("scripts/analysis/development_diagnostics.py")
    fine_judgment, fine_summary, fine_result = (
        ns["FineJudgment"],
        ns["FineSummary"],
        ns["FineMonitoringResult"],
    )
    source = CanonicalTrajectory(id="trajectory", task="Review an archived record", segments=[])

    class Backend:
        async def generate(self, messages, schema, name, seed, effort):
            assert schema is fine_judgment
            assert effort == "medium"
            assert "integer 0–100" in messages[0]["content"]
            return [
                SimpleNamespace(
                    error=None,
                    finish_reason="stop",
                    response='{"score": 93, "explanation": "Test", "citations": []}',
                )
            ]

    monitor = Monitor(
        Backend(), fine_judgment, fine_summary, ns["FINE_RUBRIC"], "integer 0–100", fine_result
    )
    result = asyncio.run(monitor.run(source, MethodConfig(method="think")))
    result.calls.clear()
    assert fine_result.model_validate(result.model_dump()).score == 93
    with pytest.raises(ValueError, match="score in"):
        MonitoringResult.model_validate(result.model_dump())
    for score in (True, 100.1, 101):
        with pytest.raises(ValueError):
            fine_judgment(score=score, explanation="test", citations=[])
    assert Judgment(score=5, explanation="test", citations=[]).score == 5
