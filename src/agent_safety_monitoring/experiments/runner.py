"""Immutable freeze manifests, idempotent shards, and explicit run coverage."""

import asyncio
import subprocess
import time
from pathlib import Path

from agent_safety_monitoring.inference.backend import Backend, ModelConfig
from agent_safety_monitoring.io import atomic_json, digest, file_hash, now, read_json
from agent_safety_monitoring.monitors.core import MethodConfig, Monitor, costs, prompt_identity
from agent_safety_monitoring.schema import CanonicalTrajectory, MonitoringResult


def source_identity():
    paths = sorted(Path("src").rglob("*.py"))
    if not paths:
        raise ValueError("Run from the project checkout root")
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
        included = {r["trajectory_id"] for r in manifest["records"] if not r["exclusion"]}
        fitting = {r["trajectory_id"] for r in cohort["records"] if r["fits"]}
        if not included <= fitting:
            raise ValueError("Primary cohort contains records failing complete-prompt preflight")
        for key in ["model", "revision", "tokenizer_revision", "max_tokens", "context_limit"]:
            if cohort["model"][key] != getattr(model, key):
                raise ValueError("Cohort audit uses different model/token limits")
        if not proofs["pilot_measurement"].get("backend_validated"):
            raise ValueError("Physical backend pilot has not been accepted")
        budget = configuration.get("budget_approval", {})
        if budget.get("approved_by") != "user" or budget.get("gpu_hours", 0) <= 0:
            raise ValueError("Missing user-approved full-study GPU-hour cap")
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

    body = {
        "version": 1,
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
            "trajectory_ids": select_injection_ids(manifest["records"]),
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
    if shards < 1 or not 0 <= shard < shards:
        raise ValueError("Invalid shard")
    if split != "development":
        if not frozen:
            raise ValueError("Calibration/test inference requires a frozen study")
        validate_freeze(frozen, data)
        if configuration != frozen["body"]["config"]:
            raise ValueError("Configuration differs from frozen study")
    model = ModelConfig.model_validate(configuration["model"])
    backend = Backend(model, output / "cache" / f"shard-{shard}")
    monitor = Monitor(backend)
    from agent_safety_monitoring.experiments.telemetry import Telemetry

    telemetry = Telemetry(configuration.get("logging", {}))
    manifest = read_json(data / "manifest.json")
    selected = [r for r in manifest["records"] if r["split"] == split and not r["exclusion"]]
    selected = sorted(selected, key=lambda r: r["trajectory_id"])[shard::shards]
    if limit is not None:
        if split != "development":
            raise ValueError(
                "Partial held-out cohorts must be specified in the freeze, not --limit"
            )
        selected = selected[:limit]
    identity = digest(
        {
            "config": configuration,
            "dataset": digest(manifest),
            "freeze": frozen["hash"] if frozen else None,
            "code": source_identity(),
        }
    )
    run_root = output / identity
    study = {
        "identity": identity,
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
    study_path = run_root / "study.json"
    if study_path.exists() and read_json(study_path) != study:
        raise ValueError("Existing study manifest differs")
    atomic_json(study_path, study)
    start, clock = now(), time.perf_counter()
    results, resumed = [], 0
    try:
        for raw in configuration["methods"]:
            config = MethodConfig.model_validate(raw)
            method_id = f"{config.method}-{digest(config.model_dump())[:12]}"

            async def process(record, config=config, method_id=method_id):
                nonlocal resumed
                path = run_root / split / method_id / f"{record['trajectory_id']}.json"
                if path.exists():
                    saved = read_json(path)
                    if saved["run_identity"] != identity:
                        raise ValueError("Incompatible saved result")
                    results.append(MonitoringResult.model_validate(saved["result"]))
                    resumed += 1
                    return
                t = CanonicalTrajectory.model_validate(
                    read_json(data / "trajectories" / f"{record['trajectory_id']}.json")
                )
                result = await monitor.run(t, config)
                atomic_json(
                    path,
                    {"run_identity": identity, "evaluation": record, "result": result.model_dump()},
                )
                results.append(result)
                usage = costs(results)
                telemetry.log(
                    completed=len(results),
                    invalid=sum(r.status != "valid" for r in results),
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    logical_calls=usage["logical_calls"],
                )

            concurrency = int(configuration.get("execution", {}).get("trajectory_concurrency", 1))
            if not 1 <= concurrency <= 64:
                raise ValueError("trajectory_concurrency must be in [1,64]")
            queue = asyncio.Queue()
            for record in selected:
                queue.put_nowait(record)

            async def worker(queue=queue, process=process):
                while not queue.empty():
                    record = queue.get_nowait()
                    await process(record)

            outcomes = await asyncio.gather(
                *[worker() for _ in range(concurrency)], return_exceptions=True
            )
            for outcome in outcomes:
                if isinstance(outcome, BaseException):
                    raise outcome
    finally:
        await backend.close()
        telemetry.close()
        atomic_json(
            run_root / f"{split}-shard-{shard}-summary.json",
            {
                "run_identity": identity,
                "started": start,
                "completed": now(),
                "wall_seconds": time.perf_counter() - clock,
                "backend": model.backend,
                "expected": len(selected) * len(configuration["methods"]),
                "completed_results": len(results),
                "resumed_results": resumed,
                "invalid": sum(r.status != "valid" for r in results),
                "costs": costs(results),
                "gpu_seconds": None,
                "gpu_accounting": "Requires Slurm allocation ledger, not latency",
            },
        )
    return {
        "run_root": str(run_root),
        "completed": len(results),
        "resumed": resumed,
        "invalid": sum(r.status != "valid" for r in results),
    }


def run_sync(*args, **kwargs):
    return asyncio.run(run(*args, **kwargs))
