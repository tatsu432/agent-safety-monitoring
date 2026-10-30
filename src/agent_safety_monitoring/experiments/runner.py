"""Immutable freeze manifests, idempotent shards, and explicit run coverage."""

import asyncio
import os
import platform
import signal
import subprocess
import time
import uuid
from pathlib import Path

from agent_safety_monitoring.inference.backend import Backend, ModelConfig
from agent_safety_monitoring.io import (
    FileLock,
    atomic_json,
    digest,
    file_hash,
    immutable_json,
    now,
    read_json,
)
from agent_safety_monitoring.monitors.core import MethodConfig, Monitor, costs, prompt_identity
from agent_safety_monitoring.schema import CanonicalTrajectory, MonitoringResult


def source_identity():
    paths = sorted(Path("src").rglob("*.py"))
    if not paths:
        raise ValueError("Run from the project checkout root")
    paths += sorted(Path("scripts/yale").glob("*.py"))
    paths += sorted(Path("scripts/yale").glob("*.sh"))
    paths += sorted(Path("scripts/yale").glob("*.sbatch"))
    paths += [Path(name) for name in ["pyproject.toml", "uv.lock", ".python-version"]]
    return {str(p): file_hash(p) for p in paths}


def create_freeze(data: Path, configuration: dict, output: Path):
    if output.exists():
        existing = read_json(output)
        validate_freeze(existing, data)
        if existing["body"]["config"] != configuration:
            raise ValueError("Refusing to overwrite an existing freeze")
        return existing
    model = ModelConfig.model_validate(configuration["model"])
    methods = [MethodConfig.model_validate(m) for m in configuration["methods"]]
    if not methods:
        raise ValueError("No methods selected")
    names = [digest(m.model_dump()) for m in methods]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate method configuration")
    manifest = read_json(data / "manifest.json")
    if manifest["rejected"]:
        raise ValueError("Resolve or explicitly document source schema rejections before freeze")
    if model.backend != "mock":
        if "UNVERIFIED" in {model.revision, model.tokenizer_revision, model.engine_version}:
            raise ValueError("Real-model freeze requires pinned model/tokenizer/engine")
        proofs = {}
        for prerequisite in ["cohort_audit", "pilot_measurement"]:
            proof = configuration.get(prerequisite)
            if not isinstance(proof, dict) or not {"path", "sha256"} <= set(proof):
                raise ValueError(f"Missing checksummed real-study prerequisite: {prerequisite}")
            path = Path(proof["path"])
            if file_hash(path) != proof["sha256"]:
                raise ValueError(f"Prerequisite checksum mismatch: {prerequisite}")
            proofs[prerequisite] = read_json(path)
        cohort = proofs["cohort_audit"]
        if cohort["manifest_hash"] != digest(manifest):
            raise ValueError("Cohort audit does not match the current dataset")
        if cohort.get("prompt_hash") != prompt_identity():
            raise ValueError("Cohort audit does not match the current prompts")
        included = {r["trajectory_id"] for r in manifest["records"] if not r["exclusion"]}
        fitting = {r["trajectory_id"] for r in cohort["records"] if r["fits"]}
        if not included <= fitting:
            raise ValueError("Primary cohort contains records failing complete-prompt preflight")
        for key in ["model", "revision", "tokenizer_revision", "max_tokens", "context_limit"]:
            if cohort["model"][key] != getattr(model, key):
                raise ValueError("Cohort audit uses different model/token limits")
        if not proofs["pilot_measurement"].get("backend_validated"):
            raise ValueError("Physical backend pilot has not been accepted")
        accepted = proofs["pilot_measurement"]
        if not set(names) <= set(accepted.get("feasible_method_hashes", [])):
            raise ValueError("Selected methods lack representative development feasibility proof")
        if accepted.get("model") != model.model_dump():
            raise ValueError("Accepted pilot uses different model/serving settings")
        if accepted.get("hardware") != configuration.get("hardware"):
            raise ValueError("Accepted pilot uses different hardware settings")
        environment = configuration.get("environment", {})
        import re

        if not re.fullmatch(r"[a-f0-9]{64}", environment.get("container_sha256", "")):
            raise ValueError("Missing verified container SHA-256")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", environment.get("container_digest", "")):
            raise ValueError("Missing immutable container registry digest")
        budget = configuration.get("budget_approval", {})
        if budget.get("approved_by") != "user" or budget.get("gpu_hours", 0) <= 0:
            raise ValueError("Missing user-approved full-study GPU-hour cap")
        hardware = configuration.get("hardware", {})
        if (
            not hardware.get("gpu_name")
            or hardware.get("gpu_count", 0) < 1
            or hardware.get("tensor_parallel_size", 0) < 1
        ):
            raise ValueError(
                "Real freeze requires explicit GPU name/count and tensor parallel size"
            )
        if not configuration.get("hardware", {}).get("verified"):
            raise ValueError("Real study hardware has not been verified")
        if subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"], text=True
        ).strip():
            raise ValueError("Commit the working tree before creating a scientific freeze")
    from agent_safety_monitoring.experiments.injections import (
        PAYLOADS,
        matched_control,
        select_injection_ids,
    )
    from agent_safety_monitoring.inference.backend import Tokenizer

    tokenizer = Tokenizer(model)
    audit_path = data / "audit.json"
    features = read_json(audit_path)["features"] if audit_path.exists() else []
    singles = sorted(
        (m for m in methods if m.method == "single"), key=lambda m: digest(m.model_dump())
    )
    eaes = sorted(
        (m for m in methods if m.method == "eae"),
        key=lambda m: (m.quote_tokens, digest(m.model_dump())),
        reverse=True,
    )
    selected_methods = singles[:1] + eaes[:1]

    body = {
        "version": 1,
        "client_python_version": platform.python_version(),
        "created": now(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "sources": source_identity(),
        "dataset_manifest": digest(manifest),
        "trajectory_hashes": {
            r["trajectory_id"]: file_hash(data / "trajectories" / f"{r['trajectory_id']}.json")
            for r in manifest["records"]
        },
        "config": configuration,
        "prompt_hash": prompt_identity(),
        "injections": {
            "payloads": PAYLOADS,
            "controls": {family: matched_control(family, tokenizer) for family in PAYLOADS},
            "trajectory_ids": select_injection_ids(manifest["records"], features),
            "method_hashes": [digest(m.model_dump()) for m in selected_methods],
        },
        "analysis": {
            "target_fpr": 0.05,
            "bootstrap": 2000,
            "invalid": "referral_alert",
            "ties": "expected_randomization",
        },
        "software_only": model.backend == "mock",
    }
    frozen = {"hash": digest(body), "body": body}
    if output.exists() and read_json(output) != frozen:
        raise ValueError("Refusing to overwrite an existing freeze")
    atomic_json(output, frozen)
    return frozen


def validate_freeze(frozen, data):
    body = frozen["body"]
    if digest(body) != frozen["hash"]:
        raise ValueError("Freeze content hash mismatch")
    if body.get("client_python_version") != platform.python_version():
        raise ValueError("Client Python version differs from scientific freeze")
    if body["sources"] != source_identity() or body["prompt_hash"] != prompt_identity():
        raise ValueError("Code/prompts changed after freeze; create a documented new study")
    manifest = read_json(data / "manifest.json")
    if body["dataset_manifest"] != digest(manifest):
        raise ValueError("Dataset/splits changed after freeze")
    for uid, sha in body["trajectory_hashes"].items():
        if file_hash(data / "trajectories" / f"{uid}.json") != sha:
            raise ValueError("Canonical trajectory changed after freeze")


async def run(
    data: Path,
    output: Path,
    configuration: dict,
    split="development",
    frozen=None,
    shard=0,
    shards=1,
    limit=None,
):
    if split not in {"development", "calibration", "test"}:
        raise ValueError("Unknown split")
    if shards < 1 or not 0 <= shard < shards:
        raise ValueError("Invalid shard")
    if limit is not None and (split != "development" or limit < 1):
        raise ValueError("Positive limits are development-only")
    if split != "development":
        if not frozen:
            raise ValueError("Calibration/test inference requires a frozen study")
        validate_freeze(frozen, data)
        if configuration != frozen["body"]["config"]:
            raise ValueError("Configuration differs from frozen study")
    model = ModelConfig.model_validate(configuration["model"])
    methods = [MethodConfig.model_validate(m) for m in configuration["methods"]]
    method_ids = [f"{m.method}-{digest(m.model_dump())[:12]}" for m in methods]
    if not methods or len(set(method_ids)) != len(methods):
        raise ValueError("Nonempty unique methods required")
    concurrency = int(configuration.get("execution", {}).get("trajectory_concurrency", 1))
    if not 1 <= concurrency <= 64:
        raise ValueError("trajectory_concurrency must be in [1,64]")
    manifest = read_json(data / "manifest.json")
    selected = sorted(
        (r for r in manifest["records"] if r["split"] == split and not r["exclusion"]),
        key=lambda r: r["trajectory_id"],
    )[shard::shards]
    if limit is not None:
        selected = selected[:limit]
    identity = digest(
        {
            "config": configuration,
            "dataset": digest(manifest),
            "freeze": frozen["hash"] if frozen else None,
            "code": source_identity(),
        }
    )
    root = output / identity
    study = {
        "identity": identity,
        "sources": source_identity(),
        "data_manifest": digest(manifest),
        "configuration": configuration,
        "freeze": frozen["hash"] if frozen else None,
        "software_only": model.backend == "mock",
        "expected": {
            name: sorted(
                r["trajectory_id"]
                for r in manifest["records"]
                if r["split"] == name and not r["exclusion"]
            )
            for name in ["development", "calibration", "test"]
        },
    }
    with FileLock(root / ".manifest.lock"):
        immutable_json(root / "study.json", study)
        immutable_json(root / f"{split}-execution.json", {"shards": shards})
    with FileLock(root / f".{split}-shard-{shard}.lock"):
        immutable_json(
            root / f"{split}-shard-{shard}-manifest.json",
            {
                "identity": identity,
                "shard": shard,
                "shards": shards,
                "selected": [r["trajectory_id"] for r in selected],
            },
        )
        return await _run_owned(
            data,
            root,
            configuration,
            model,
            methods,
            method_ids,
            selected,
            split,
            shard,
            concurrency,
            identity,
        )


async def _run_owned(
    data,
    root,
    configuration,
    model,
    methods,
    method_ids,
    selected,
    split,
    shard,
    concurrency,
    identity,
):
    from agent_safety_monitoring.experiments.progress import Progress
    from agent_safety_monitoring.experiments.telemetry import Telemetry

    attempt = uuid.uuid4().hex
    attempt_root = root / "attempts" / attempt
    attempt_root.mkdir(parents=True)
    telemetry = Telemetry(
        configuration.get("logging", {}),
        identity=identity,
        split=split,
        shard=shard,
        attempt=attempt,
        directory=attempt_root,
        metadata={
            "model_revision": model.revision,
            "tokenizer_revision": model.tokenizer_revision,
            "engine_version": model.engine_version,
            "allocated_gpus": int(os.environ.get("ASM_GPUS", "0")),
            "trajectory_concurrency": concurrency,
            "method_settings": [m.model_dump() for m in methods],
        },
    )
    progress = Progress(
        root,
        split,
        shard,
        attempt,
        {m: len(selected) for m in method_ids},
        telemetry,
        os.environ.get("SLURM_JOB_ID"),
    )
    backend = None
    started, clock = now(), time.perf_counter()
    results, resumed = [], 0
    state = "failed"
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    workers = []
    drain_handle = None
    registered = []

    def request_stop():
        nonlocal drain_handle
        if stop.is_set():
            return
        stop.set()
        progress.emit(force=True, state="draining")
        # Wrapper reserves 60s for cleanup after this bound.
        seconds = min(840, max(0, float(os.environ.get("ASM_DRAIN_SECONDS", "840"))))
        drain_handle = loop.call_later(seconds, lambda: [w.cancel() for w in workers])

    async def heartbeat():
        while True:
            progress.emit(force=True)
            await asyncio.sleep(30)

    beat = asyncio.create_task(heartbeat())
    try:
        for sig in (signal.SIGUSR1, signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, request_stop)
                registered.append(sig)
            except (NotImplementedError, RuntimeError, ValueError):
                pass
        backend = Backend(model, root / "cache" / f"shard-{shard}")
        backend.attempt_dir = attempt_root / "calls"
        backend.on_call = progress.event
        monitor = Monitor(backend)
        for config, method_id in zip(methods, method_ids, strict=True):
            pending = []
            for record in selected:
                path = root / split / method_id / f"{record['trajectory_id']}.json"
                if path.exists():
                    try:
                        saved = read_json(path)
                        saved["run_identity"], saved["evaluation"]
                        result = MonitoringResult.model_validate(saved["result"])
                    except (ValueError, KeyError, TypeError):
                        path.rename(path.with_suffix(f".corrupt-{attempt}"))
                    else:
                        if (
                            saved["run_identity"] != identity
                            or saved["evaluation"] != record
                            or result.trajectory_id != record["trajectory_id"]
                            or result.config_hash != digest(config.model_dump())
                            or result.method != config.method
                        ):
                            raise ValueError("Incompatible saved result")
                        if result.status != "error":
                            results.append(result)
                            resumed += 1
                            progress.result(method_id, result, resumed=True)
                            continue
                        path.rename(path.with_suffix(f".infrastructure-{attempt}"))
                pending.append(record)

            async def process(record, config=config, method_id=method_id):
                trajectory = CanonicalTrajectory.model_validate(
                    read_json(data / "trajectories" / f"{record['trajectory_id']}.json")
                )
                result = await monitor.run(trajectory, config)
                saved = {
                    "run_identity": identity,
                    "evaluation": record,
                    "result": result.model_dump(),
                }
                if result.status == "error":
                    atomic_json(attempt_root / f"{method_id}-{trajectory.id}-failure.json", saved)
                    raise RuntimeError("Infrastructure failure; resume missing work")
                path = root / split / method_id / f"{trajectory.id}.json"
                if path.exists():
                    raise RuntimeError("Refusing to overwrite an existing result")
                atomic_json(path, saved)
                results.append(result)
                progress.result(method_id, result)

            queue = asyncio.Queue()
            for record in pending:
                queue.put_nowait(record)

            async def worker(queue=queue, process=process):
                while not stop.is_set() and not queue.empty():
                    await process(queue.get_nowait())

            workers[:] = [asyncio.create_task(worker()) for _ in range(concurrency)]
            outcomes = await asyncio.gather(*workers, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, BaseException) and not (
                    stop.is_set() and isinstance(outcome, asyncio.CancelledError)
                ):
                    raise outcome
        state = "interrupted" if stop.is_set() else "complete"
    finally:
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)
        if drain_handle:
            drain_handle.cancel()
        for sig in registered:
            loop.remove_signal_handler(sig)
        if backend:
            await backend.close()
        progress.emit(force=True, state=state)
        summary = {
            "run_identity": identity,
            "attempt": attempt,
            "job_id": os.environ.get("SLURM_JOB_ID"),
            "state": state,
            "started": started,
            "completed": now(),
            "wall_seconds": time.perf_counter() - clock,
            "backend": model.backend,
            "expected": len(selected) * len(methods),
            "completed_results": len(results),
            "resumed_results": resumed,
            "invalid": sum(r.status != "valid" for r in results),
            "costs": costs(results),
            "physical_attempt": dict(progress.physical),
            "gpu_seconds": None,
            "gpu_accounting": "Reconcile Slurm allocations, not latency",
        }
        atomic_json(attempt_root / "summary.json", summary)
        atomic_json(root / f"{split}-shard-{shard}-summary.json", summary)
        telemetry.close()
    return {
        "run_root": str(root),
        "completed": len(results),
        "resumed": resumed,
        "invalid": sum(r.status != "valid" for r in results),
        "state": state,
        "attempt": attempt,
    }


def run_sync(*args, **kwargs):
    return asyncio.run(run(*args, **kwargs))
