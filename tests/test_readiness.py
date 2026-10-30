"""Recovery and evidence invariants; these fixtures establish no GPU/scientific claims."""

import asyncio
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from agent_safety_monitoring.experiments.runner import run_sync
from agent_safety_monitoring.experiments.telemetry import Telemetry
from agent_safety_monitoring.inference.backend import Backend, ModelConfig, Tokenizer
from agent_safety_monitoring.io import FileLock, atomic_json, read_json
from agent_safety_monitoring.monitors.core import (
    Monitor,
    extraction_payload,
    passage_table,
    resolve_passages,
    selection_schema,
)
from agent_safety_monitoring.schema import CanonicalTrajectory, Segment


def dataset(root, n=3):
    records = []
    for i in range(n):
        uid = str(i)
        trajectory = CanonicalTrajectory(
            id=uid,
            task="Authorized task",
            segments=[
                Segment(
                    id="s0",
                    role="tool",
                    kind="tool_result",
                    text="evidence " * 70,
                    source_message=9,
                    source_end=630,
                    interaction=0,
                )
            ],
        )
        atomic_json(root / "trajectories" / f"{uid}.json", trajectory.model_dump())
        records.append(
            {
                "trajectory_id": uid,
                "split": "development",
                "exclusion": None,
                "assignment": "benign",
                "outcome": "not_applicable",
            }
        )
    atomic_json(root / "manifest.json", {"records": records})
    return root, {"model": {"backend": "mock"}, "methods": [{"method": "eae"}]}


def test_passages_resolve_exact_text_and_enforce_cost(tmp_path):
    data, _ = dataset(tmp_path)
    trajectory = CanonicalTrajectory.model_validate(read_json(data / "trajectories/0.json"))
    tokens = Tokenizer(ModelConfig())
    table = passage_table(trajectory, tokens)
    schema = selection_schema(len(table))
    assert "".join(q.text for q in table) == trajectory.segments[0].text
    selection = schema(passage_ids=[1])
    resolved = resolve_passages(selection, table, trajectory, tokens, 1000)
    assert resolved.quotes[0].start == 400
    with pytest.raises(ValueError, match="selected .*limit"):
        resolve_passages(selection, table, trajectory, tokens, 1)
    with pytest.raises(ValueError):
        schema(passage_ids=[2])
    with pytest.raises(ValueError, match="Duplicate"):
        resolve_passages(schema(passage_ids=[0, 0]), table, trajectory, tokens, 1000)
    payload = extraction_payload(trajectory, 1000, tokens)
    assert payload["segments"][0]["text"][0].startswith(f"0/{tokens.count(table[0].text)}: ")
    assert "source_message" not in json.dumps(payload)


@pytest.mark.parametrize("method, crash_stage", [("eae", "judge"), ("mrt", "leaf-0")])
def test_crash_after_completed_stage_reuses_cache(tmp_path, monkeypatch, method, crash_stage):
    data, config = dataset(tmp_path / "data", 1)
    config["methods"] = [{"method": method}]
    original = Backend.generate

    async def crash(self, messages, schema, stage, *args, **kwargs):
        if stage == crash_stage:
            raise RuntimeError("controlled crash")
        return await original(self, messages, schema, stage, *args, **kwargs)

    monkeypatch.setattr(Backend, "generate", crash)
    with pytest.raises(RuntimeError, match="controlled"):
        run_sync(data, tmp_path / "runs", config)
    monkeypatch.setattr(Backend, "generate", original)
    result = run_sync(data, tmp_path / "runs", config)
    saved = read_json(next(Path(result["run_root"]).glob("development/*/*.json")))
    assert saved["result"]["calls"][0]["cached"]
    assert not saved["result"]["calls"][-1]["cached"]
    assert len(list(Path(result["run_root"]).glob("attempts/*/summary.json"))) == 2


def test_signal_stops_new_trajectories_and_resume_completes(tmp_path, monkeypatch):
    data, config = dataset(tmp_path / "data")
    original = Monitor.run
    sent = False

    async def interrupt(self, *args):
        nonlocal sent
        result = await original(self, *args)
        if not sent:
            sent = True
            os.kill(os.getpid(), signal.SIGUSR1)
            await asyncio.sleep(0.01)
        return result

    monkeypatch.setattr(Monitor, "run", interrupt)
    first = run_sync(data, tmp_path / "runs", config)
    assert first["state"] == "interrupted" and first["completed"] == 1
    monkeypatch.setattr(Monitor, "run", original)
    second = run_sync(data, tmp_path / "runs", config)
    assert second["completed"] == 3 and second["resumed"] == 1
    status = read_json(Path(second["run_root"]) / "development-shard-0-status.json")
    assert status["state"] == "complete"
    row = next(iter(status["methods"].values()))
    assert row["remaining"] == 0 and row["percent"] == 100


def test_corrupt_result_preserved_and_geometry_rejected(tmp_path):
    data, config = dataset(tmp_path / "data")
    first = run_sync(data, tmp_path / "runs", config)
    root = Path(first["run_root"])
    path = next(root.glob("development/*/*.json"))
    path.write_text('{"partial":')
    result = run_sync(data, tmp_path / "runs", config)
    assert result["resumed"] == 2 and result["completed"] == 3
    assert list(path.parent.glob("*.corrupt-*"))
    with pytest.raises(ValueError, match="identity mismatch"):
        run_sync(data, tmp_path / "runs", config, shards=2)
    with pytest.raises(ValueError, match="identity mismatch"):
        run_sync(data, tmp_path / "runs", config, limit=1)
    obj = read_json(path)
    obj["result"]["config_hash"] = "changed"
    atomic_json(path, obj)
    with pytest.raises(ValueError, match="Incompatible"):
        run_sync(data, tmp_path / "runs", config)


def test_cross_process_exclusive_shard_lock(tmp_path):
    path = tmp_path / "shard.lock"
    with FileLock(path):
        code = (
            f"from agent_safety_monitoring.io import FileLock; FileLock({str(path)!r}).__enter__()"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert result.returncode != 0 and "Already owned" in result.stderr
    with FileLock(path):
        pass


def test_tracking_scalar_boundary_and_failure_fallback(monkeypatch):
    class Run:
        def log(self, values):
            assert values == {"completed": 2}
            raise RuntimeError("tracking unavailable")

        def finish(self):
            pass

    tracker = Telemetry({"mode": "disabled"})
    tracker.run = Run()
    with pytest.warns(UserWarning, match="Tracking delivery failed"):
        tracker.log(completed=2, prompt="PRIVATE", quotes=["PRIVATE"], PRIVATE_KEY=9)
    assert tracker.run is None


def test_allocation_counts_failures_without_double_counting_tres():
    from agent_safety_monitoring.experiments.resources import allocation_usage

    usage = allocation_usage(
        "JobID|State|ElapsedRaw|AllocTRES\n"
        "1|FAILED|60|gres/gpu=2,gres/gpu:h200=2\n"
        "2|COMPLETED|10|cpu=4\n"
    )
    assert usage["allocated_gpu_seconds"] == 120


def test_benchmark_resume_is_not_an_independent_cold_timing(tmp_path, monkeypatch):
    from agent_safety_monitoring.experiments import benchmark as module

    data, config = dataset(tmp_path / "data", 1)
    config["model"]["backend"] = "vllm"
    monkeypatch.setenv("SLURM_JOB_ID", "fake")
    monkeypatch.setenv("SLURM_GPUS_ON_NODE", "1")
    calls = 0

    def run_fake(data, output, trial, limit):
        nonlocal calls
        calls += 1
        root = output / "identity"
        state = "interrupted" if calls == 1 else "complete"
        atomic_json(
            root / "development-shard-0-summary.json",
            {"costs": {}, "physical_attempt": {"cache_hits": calls - 1}},
        )
        return {
            "run_root": str(root),
            "state": state,
            "completed": calls - 1,
            "invalid": 0,
            "resumed": calls - 1,
        }

    monkeypatch.setattr(module, "run_sync", run_fake)
    first = module.benchmark(data, tmp_path / "runs", config, 1, 1, "trial")
    assert first["state"] == "incomplete"
    second = module.benchmark(data, tmp_path / "runs", config, 1, 1, "trial")
    trial = read_json(Path(second["output"]))["trials"][0]
    assert len(trial["executions"]) == 2 and not trial["independent_cold"]
    module.benchmark(data, tmp_path / "runs", config, 1, 1, "trial")
    assert calls == 2  # a completed measurement is not run again
    with pytest.raises(ValueError, match="GPU count"):
        module.benchmark(data, tmp_path / "runs", config, 2, 1, "trial")


def test_infrastructure_failure_is_retried_on_resume(tmp_path, monkeypatch):
    from agent_safety_monitoring.schema import CallRecord

    data, config = dataset(tmp_path / "data", 1)
    original = Backend.generate

    async def unavailable(self, messages, schema, stage, *args, **kwargs):
        return [
            CallRecord(
                key="failed",
                stage=stage,
                attempt=0,
                started="now",
                completed="now",
                latency_seconds=0,
                error="HTTP 503",
            )
        ]

    monkeypatch.setattr(Backend, "generate", unavailable)
    with pytest.raises(RuntimeError, match="Infrastructure"):
        run_sync(data, tmp_path / "runs", config)
    assert not list((tmp_path / "runs").glob("*/development/*/*.json"))
    assert list((tmp_path / "runs").glob("*/attempts/*/*-failure.json"))
    monkeypatch.setattr(Backend, "generate", original)
    assert run_sync(data, tmp_path / "runs", config)["completed"] == 1


def test_corrupt_request_cache_is_preserved(tmp_path):
    from agent_safety_monitoring.schema import Judgment

    async def check():
        backend = Backend(ModelConfig(), tmp_path)
        messages = [{"role": "user", "content": '{"segments":[]}'}]
        first = await backend.generate(messages, Judgment, "review", 1)
        cache = tmp_path / f"{first[-1].key}.json"
        cache.write_text("partial")
        second = await backend.generate(messages, Judgment, "review", 1)
        assert not second[-1].cached and list(tmp_path.glob("*.corrupt-*"))
        await backend.close()

    asyncio.run(check())


def test_no_completed_work_still_emits_heartbeat(tmp_path):
    from agent_safety_monitoring.experiments.progress import Progress

    progress = Progress(
        tmp_path, "development", 0, "attempt", {"eae-config": 40}, Telemetry({"mode": "disabled"})
    )
    snapshot = progress.emit(force=True)
    row = snapshot["methods"]["eae-config"]
    assert row["completed"] == 0 and row["remaining"] == 40
    assert snapshot["remaining_seconds_estimate"] is None
    assert read_json(progress.path)["updated"]


def test_budget_report_uses_measured_cost_not_tokens(tmp_path):
    from agent_safety_monitoring.experiments.demo import demo
    from agent_safety_monitoring.monitors.core import MethodConfig
    from agent_safety_monitoring.reporting.report import generate

    result = demo(tmp_path)
    root = Path(result["last_run"]["run_root"])
    study = read_json(root / "study.json")
    config = next(m for m in study["configuration"]["methods"] if m["method"] == "single")
    study["configuration"]["budgets"] = {
        "large": {
            "methods": {
                "single": {
                    "config": MethodConfig.model_validate(config).model_dump(),
                    "gpu_seconds_per_trajectory": 12.5,
                },
                "eae": None,
            }
        }
    }
    atomic_json(root / "study.json", study)
    generate(root, tmp_path / "budget-report", replicates=2)
    rows = read_json(tmp_path / "budget-report/budget-performance.json")
    by_method = {row["method"]: row for row in rows}
    assert by_method["single"]["development_gpu_seconds_per_trajectory"] == 12.5
    assert by_method["eae"]["available"] is False
    assert (tmp_path / "budget-report/gpu-cost-detection.png").exists()


def test_signal_inside_eae_drains_then_reuses_extraction(tmp_path, monkeypatch):
    data, config = dataset(tmp_path / "data", 1)
    monkeypatch.setenv("ASM_DRAIN_SECONDS", "0")
    original = Backend.generate

    async def interrupted(self, messages, schema, stage, *args, **kwargs):
        if stage == "judge":
            os.kill(os.getpid(), signal.SIGUSR1)
            await asyncio.sleep(0.1)
        return await original(self, messages, schema, stage, *args, **kwargs)

    monkeypatch.setattr(Backend, "generate", interrupted)
    first = run_sync(data, tmp_path / "runs", config)
    assert first["state"] == "interrupted" and first["completed"] == 0
    monkeypatch.setattr(Backend, "generate", original)
    second = run_sync(data, tmp_path / "runs", config)
    saved = read_json(next(Path(second["run_root"]).glob("development/*/*.json")))
    assert saved["result"]["calls"][0]["cached"] and second["completed"] == 1


def test_incremental_gpu_csv_metrics(tmp_path, monkeypatch):
    from agent_safety_monitoring.experiments.progress import Progress

    path = tmp_path / "gpu.csv"
    path.write_text(
        "timestamp, uuid, utilization.gpu [%], memory.used [MiB]\nnow, GPU-a, 80 %, 120000 MiB\n"
    )
    monkeypatch.setenv("ASM_GPU_METRICS", str(path))
    progress = Progress(
        tmp_path, "development", 0, "attempt", {"eae-config": 1}, Telemetry({"mode": "disabled"})
    )
    assert progress.emit(force=True)["gpu"]["gpu_utilization_percent"] == 80
    with path.open("a") as stream:
        stream.write("later, GPU-a, 25 %, 100000 MiB\n")
    gpu = progress.emit(force=True)["gpu"]
    assert gpu["gpu_memory_mib"] == 100000 and gpu["gpu_peak_memory_mib"] == 120000


def test_submission_ledger_rejects_duplicate_and_unknown_intent(tmp_path, monkeypatch):
    import runpy

    namespace = runpy.run_path("scripts/yale/submit.py", run_name="submit_test")
    ledger = tmp_path / "submissions.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "submit.py",
            "--ledger",
            str(ledger),
            "--identity",
            "trial",
            "--gpus",
            "1",
            "--minutes",
            "20",
            "--cap-hours",
            "4",
            "--",
            "scripts/yale/benchmark.sbatch",
        ],
    )
    submitted = []
    queued = False

    def command(args, **kwargs):
        if args[0] == "sacct":
            return "JobID|State|ElapsedRaw|AllocTRES|Comment\n"
        if args[0] == "squeue":
            token = read_json(ledger)["submissions"][-1]["token"] if ledger.exists() else ""
            return f"123|{token}\n" if queued else ""
        if args[0] == "sbatch":
            submitted.append(args)
            return "123\n"
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "check_output", command)
    namespace["main"]()
    assert len(submitted) == 1
    queued = True
    with pytest.raises(SystemExit, match="Matching job"):
        namespace["main"]()
    queued = False
    saved = read_json(ledger)
    saved["submissions"][-1]["state"] = "submitting"
    atomic_json(ledger, saved)
    with pytest.raises(SystemExit, match="Ambiguous"):
        namespace["main"]()
    assert len(submitted) == 1


def test_shell_wait_preserves_fast_child_failure():
    script = Path("scripts/yale/inference.sbatch").read_text()
    function = script[script.index("wait_client() {") : script.index("trap forward_signal")]
    result = subprocess.run(
        ["bash", "-c", function + "\n(exit 7) &\nclient_pid=$!\nsleep 0.05\nwait_client\n"],
        capture_output=True,
    )
    assert result.returncode == 7


def test_tracking_metadata_validates_methods_before_upload(tmp_path, monkeypatch):
    from types import SimpleNamespace

    captured = []
    fake = SimpleNamespace(
        Settings=lambda **kwargs: kwargs,
        init=lambda **kwargs: captured.append(kwargs) or SimpleNamespace(),
    )
    monkeypatch.setitem(sys.modules, "wandb", fake)
    tracker = Telemetry(
        {"mode": "offline"},
        directory=tmp_path,
        metadata={
            "method_settings": [{"method": "eae", "quote_tokens": 3000}],
            "private_prompt": "PRIVATE",
        },
    )
    assert tracker.run is not None and "eae-q3000" in captured[0]["name"]
    assert "PRIVATE" not in json.dumps(captured)
    with pytest.warns(UserWarning, match="initialization failed"):
        Telemetry(
            {"mode": "offline"},
            metadata={"method_settings": [{"method": "eae", "private_prompt": "PRIVATE"}]},
        )
    assert len(captured) == 1


def test_freeze_records_and_validates_client_python(tmp_path):
    from agent_safety_monitoring.experiments.demo import demo
    from agent_safety_monitoring.experiments.runner import validate_freeze
    from agent_safety_monitoring.io import digest

    demo(tmp_path)
    freeze = read_json(tmp_path / "freeze.json")
    assert freeze["body"]["client_python_version"].startswith("3.12.")
    freeze["body"]["client_python_version"] = "3.12.0-different"
    freeze["hash"] = digest(freeze["body"])
    with pytest.raises(ValueError, match="Python version"):
        validate_freeze(freeze, tmp_path / "data")


def test_slurm_rejects_container_mismatch_before_server_start(tmp_path):
    script = Path("scripts/yale/inference.sbatch").read_text()
    start = script.index('python3 - "$output/jobs/$SLURM_JOB_ID-allocation.json"')
    block = script[start:].split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    freeze = tmp_path / "freeze.json"
    atomic_json(
        freeze,
        {
            "body": {
                "config": {
                    "model": {"revision": "revision", "context_limit": 131072, "concurrency": 1},
                    "hardware": {"gpu_count": 1, "tensor_parallel_size": 1},
                    "environment": {"container_sha256": "expected"},
                }
            }
        },
    )
    environment = {
        **os.environ,
        "ASM_FREEZE": str(freeze),
        "ASM_IMAGE_SHA256": "wrong",
        "ASM_MODEL_REVISION": "revision",
        "ASM_GPUS": "1",
        "ASM_TP": "1",
        "ASM_CONTEXT": "131072",
        "ASM_CONCURRENCY": "1",
    }
    result = subprocess.run(
        [sys.executable, "-c", block, str(tmp_path / "allocation.json")],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "Serving settings differ" in result.stderr
    assert not (tmp_path / "allocation.json").exists()
