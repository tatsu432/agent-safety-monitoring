"""Seed a private diagnostic cache from compatible fixed-screen cold results."""

import argparse
from collections import defaultdict
from pathlib import Path

from agent_safety_monitoring.analysis.audit import verify_manifest
from agent_safety_monitoring.inference.backend import ModelConfig
from agent_safety_monitoring.io import FileLock, atomic_json, digest, file_hash, read_json
from agent_safety_monitoring.monitors.core import MethodConfig
from agent_safety_monitoring.schema import MonitoringResult


def import_calls(trial, frozen, data, ids, output):
    verify_manifest(frozen)
    manifest = read_json(data / "manifest.json")
    if digest(manifest) != frozen["body"]["dataset_manifest"]:
        raise ValueError("Diagnostic manifest differs from the freeze")
    records = {r["trajectory_id"]: r for r in manifest["records"]}
    model = ModelConfig.model_validate(frozen["body"]["config"]["model"])
    methods = {
        c.method: c
        for v in frozen["body"]["config"]["methods"]
        if (c := MethodConfig.model_validate(v)).method in ("mrt", "eae")
    }
    accepted = {}
    with FileLock(output / "cache-import.lock"):
        for directory in sorted(trial.glob("method-*/*")):
            study_path = directory / "study.json"
            study = read_json(study_path)
            config = study["configuration"]
            method = MethodConfig.model_validate(config["methods"][0])
            if method.method not in methods:
                continue
            if (
                method != methods[method.method]
                or model != ModelConfig.model_validate(config["model"])
                or study["software_only"]
            ):
                raise ValueError("Cold screen does not match the frozen method")
            saved = {}
            for path in (directory / "development").glob("*/*.json"):
                artifact = read_json(path)
                result = MonitoringResult.model_validate(artifact["result"])
                uid = result.trajectory_id
                if (
                    uid in saved
                    or artifact["run_identity"] != study["identity"]
                    or records[uid] != artifact["evaluation"]
                    or result.config_hash != digest(method.model_dump())
                ):
                    raise ValueError("Cold screen result fails identity validation")
                saved[uid] = result
            if set(saved) != ids or method.method in accepted:
                raise ValueError("Cold screen geometry or method coverage differs")
            count = 0
            for result in saved.values():
                calls = defaultdict(list)
                for call in result.calls:
                    calls[call.key].append(call.model_dump())
                for key, attempts in calls.items():
                    target = output / "cache" / f"{key}.json"
                    if not target.exists() and not attempts[-1]["error"]:
                        atomic_json(target, {"calls": attempts})
                        count += 1
            accepted[method.method] = {
                "source_study_sha256": file_hash(study_path),
                "records": len(saved),
                "new_cache_entries": count,
            }
        if accepted.keys() != methods.keys():
            raise ValueError("Expected both EaE and MRT cold-screen baselines")
        atomic_json(output / "cache-import.json", accepted)
    return accepted


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("trial", "freeze", "data", "ids", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(
        import_calls(
            args.trial, read_json(args.freeze), args.data, set(read_json(args.ids)), args.output
        )
    )
