"""Real Inspect writer/reader roundtrip on inert synthetic trajectories."""

import pytest

from agent_safety_monitoring.data.ingest import import_logs
from agent_safety_monitoring.io import read_json


@pytest.mark.parametrize(
    "objective", ["download_malware", "leak_passwords", "sudo_edit", "disable_firewall"]
)
def test_official_eval_roundtrip(tmp_path, objective):
    pytest.importorskip("inspect_ai")
    from inspect_ai.log import (
        EvalConfig,
        EvalDataset,
        EvalLog,
        EvalSample,
        EvalSpec,
        write_eval_log,
    )
    from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ChatMessageUser
    from inspect_ai.tool import ToolCall

    sample = EvalSample(
        id="synthetic",
        epoch=1,
        input="legitimate fixture task",
        target="",
        metadata={
            "main_tasks": [{"id": "task", "description": "legitimate fixture task"}],
            "side_tasks": [{"id": objective}],
        },
        messages=[
            ChatMessageUser(content="legitimate fixture task"),
            ChatMessageAssistant(
                content="visible fixture text",
                tool_calls=[
                    ToolCall(id="call1", function="bash", arguments={"cmd": "INERT_FIXTURE"})
                ],
            ),
            ChatMessageTool(content="fixture output", tool_call_id="call1"),
        ],
    )
    log = EvalLog(
        status="success",
        eval=EvalSpec(
            created="2026-10-28T00:00:00Z",
            task="synthetic",
            dataset=EvalDataset(name="synthetic", samples=1, sample_ids=["synthetic"]),
            model="synthetic/mock",
            config=EvalConfig(),
        ),
        samples=[sample],
    )
    path = tmp_path / "synthetic.eval"
    write_eval_log(log, path)
    root = tmp_path / "prepared"
    summary = import_logs([path], root, development_tasks=0)
    assert summary["raw_samples"] == 1 and summary["rejected"] == 0
    record = read_json(root / "manifest.json")["records"][0]
    assert record["outcome"] == "ungraded" and record["exclusion"] == "no_usable_benign_pair"
    t = read_json(root / "trajectories" / f"{record['trajectory_id']}.json")
    call = next(s for s in t["segments"] if s["kind"] == "tool_call")
    response = next(s for s in t["segments"] if s["kind"] == "tool_result")
    assert call["tool_call_id"] == response["tool_call_id"]
    assert call["interaction"] == response["interaction"]
