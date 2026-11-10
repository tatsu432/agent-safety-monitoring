import asyncio
from types import SimpleNamespace

from test_core import trajectory

from agent_safety_monitoring.experiments.followup import FollowupConfig, run_followup
from agent_safety_monitoring.experiments.followup_timing import benchmark
from agent_safety_monitoring.inference.backend import ModelConfig
from agent_safety_monitoring.io import atomic_json, digest, file_hash, read_json


def test_physical_timing_identity_matches_runner_without_added_defaults(tmp_path, monkeypatch):
    """Synthetic wiring test only; no real GPU compatibility claim."""
    import agent_safety_monitoring.experiments.followup as followup
    import agent_safety_monitoring.experiments.followup_timing as timing

    class FakeBackend:
        def __init__(self, *args):
            self.on_call = None

        async def close(self):
            pass

    class FakeMonitor:
        def __init__(self, backend):
            pass

        async def run(self, *args):
            return SimpleNamespace(
                status="valid", model_dump=lambda: {"status": "valid", "score": 1, "calls": []}
            )

    async def fine(*args):
        return {"status": "valid", "score": 0, "calls": []}

    for module in (followup, timing):
        monkeypatch.setattr(module, "Backend", FakeBackend)
        monkeypatch.setattr(module, "Monitor", FakeMonitor)
        monkeypatch.setattr(module, "fine_review", fine)
    monkeypatch.setenv("ASM_TRACKING_MODE", "disabled")
    monkeypatch.setenv("SLURM_GPUS_ON_NODE", "1")
    monkeypatch.setenv("SLURM_JOB_ID", "123")
    data = tmp_path / "data"
    records, hashes = [], {}
    for i in range(40):
        t = trajectory().model_copy(update={"id": digest(i)})
        path = data / "trajectories" / f"{t.id}.json"
        atomic_json(path, t.model_dump())
        hashes[t.id] = file_hash(path)
        records.append(
            {
                "trajectory_id": t.id,
                "task_id": str(i),
                "split": "development",
                "assignment": "benign",
                "outcome": "not_applicable",
                "exclusion": None,
            }
        )
    manifest = {"records": records}
    atomic_json(data / "manifest.json", manifest)
    model = ModelConfig(backend="vllm").model_dump()
    model.pop("timeout_seconds")  # Existing freeze omits this supported default.
    body = {
        "software_only": False,
        "config": {"model": model},
        "dataset_manifest": digest(manifest),
        "trajectory_hashes": hashes,
    }
    frozen = tmp_path / "original.json"
    atomic_json(frozen, {"body": body, "hash": digest(body)})
    config, ids = tmp_path / "config.json", tmp_path / "ids.json"
    atomic_json(config, FollowupConfig().model_dump())
    atomic_json(ids, [r["trajectory_id"] for r in records])
    asyncio.run(benchmark(data, frozen, config, tmp_path / "timing", ids, 1))
    asyncio.run(run_followup(data, frozen, config, tmp_path / "development"))
    assert read_json(tmp_path / "timing/identity.json") == read_json(
        tmp_path / "development/identity.json"
    )
