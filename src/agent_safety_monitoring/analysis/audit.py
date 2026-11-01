"""Read-only reconciliation, independent of the running checkout's source hashes."""

import hashlib
import subprocess
from collections import Counter
from pathlib import Path

from agent_safety_monitoring.io import atomic_json, digest, file_hash, read_json
from agent_safety_monitoring.monitors.core import MethodConfig
from agent_safety_monitoring.reporting.report import load_results


def method_ids(frozen):
    return {
        f"{m.method}-{digest(m.model_dump())[:12]}": m.method
        for m in (MethodConfig.model_validate(c) for c in frozen["body"]["config"]["methods"])
    }


def verify_manifest(frozen):
    if digest(frozen["body"]) != frozen["hash"]:
        raise ValueError("Freeze content hash mismatch")
    if frozen["body"]["software_only"]:
        raise ValueError("Synthetic freeze cannot establish scientific results")


def audit(freeze: Path, repository: Path, data: Path, output: Path, run_root: Path | None = None):
    frozen = read_json(freeze)
    verify_manifest(frozen)
    body = frozen["body"]
    source_failures = []
    for name, expected in body["sources"].items():
        p = subprocess.run(
            ["git", "show", f"{body['git_commit']}:{name}"],
            cwd=repository,
            capture_output=True,
            check=False,
        )
        if p.returncode or hashlib.sha256(p.stdout).hexdigest() != expected:
            source_failures.append(name)
    manifest = read_json(data / "manifest.json")
    manifest_matches = digest(manifest) == body["dataset_manifest"]
    missing, mismatched = 0, 0
    for uid, expected in body["trajectory_hashes"].items():
        path = data / "trajectories" / f"{uid}.json"
        if not path.exists():
            missing += 1
        elif file_hash(path) != expected:
            mismatched += 1
    groups = {}
    for row in manifest["records"]:
        if not row["exclusion"]:
            groups.setdefault(row["split"], set()).add(row["task_id"])
    leakage = any(
        groups[a] & groups[b] for i, a in enumerate(sorted(groups)) for b in sorted(groups)[:i]
    )
    counts = Counter((r["split"], r["assignment"], r["outcome"]) for r in manifest["records"])
    proof_status = {}
    for name in ["cohort_audit", "pilot_measurement"]:
        proof = body["config"].get(name)
        if proof:
            candidates = [
                repository / proof["path"],
                freeze.parent / Path(proof["path"]).name,
                data / Path(proof["path"]).name,
            ]
            available = next((p for p in candidates if p.exists()), None)
            proof_status[name] = (
                ("verified" if file_hash(available) == proof["sha256"] else "mismatch")
                if available
                else "missing"
            )
    result = {
        "freeze": frozen["hash"],
        "source_commit": body["git_commit"],
        "source_files_checked": len(body["sources"]),
        "source_failures": source_failures,
        "dataset_manifest_matches": manifest_matches,
        "canonical_files_expected": len(body["trajectory_hashes"]),
        "canonical_files_missing": missing,
        "canonical_files_mismatched": mismatched,
        "task_leakage": leakage,
        "counts": {"/".join(k): v for k, v in sorted(counts.items())},
        "record_coverage": "unavailable",
        "cluster_accounting": "not_checked",
        "prerequisite_proofs": proof_status,
    }
    if run_root is not None:
        study = read_json(run_root / "study.json")
        if study["freeze"] != frozen["hash"] or study["software_only"]:
            raise ValueError("Run identity does not match real freeze")
        if study["configuration"] != body["config"]:
            raise ValueError("Run configuration differs from freeze")
        tables = load_results(run_root)
        validate_pairs(tables)
        # Compare every saved evaluation record against the independent frozen manifest.
        by_id = {r["trajectory_id"]: r for r in manifest["records"]}
        for split in ("calibration", "test"):
            expected = {
                r["trajectory_id"]
                for r in manifest["records"]
                if r["split"] == split and not r["exclusion"]
            }
            if set(study["expected"][split]) != expected:
                raise ValueError("Run coverage differs from frozen dataset")
            for path in (run_root / split).glob("*/*.json"):
                saved = read_json(path)
                if saved["evaluation"] != by_id[saved["evaluation"]["trajectory_id"]]:
                    raise ValueError("Evaluation metadata differs from frozen dataset")
        result["record_coverage"] = {
            split: {name: len(rows) for name, rows in methods.items()}
            for split, methods in tables.items()
        }
    result["integrity_passed"] = not (
        source_failures
        or not manifest_matches
        or missing
        or mismatched
        or leakage
        or "mismatch" in proof_status.values()
    )
    atomic_json(output, result)
    return result


def validate_pairs(tables):
    """Stronger analysis checks without changing frozen runtime code."""
    if set(tables["calibration"]) != set(tables["test"]) or not tables["test"]:
        raise ValueError("Method coverage differs")
    tasks = {}
    for split, methods in tables.items():
        expected = None
        for rows in methods.values():
            mapping = {
                r["trajectory_id"]: (r["task_id"], r["label"], r.get("objective")) for r in rows
            }
            if len(mapping) != len(rows) or not rows:
                raise ValueError("Empty or duplicate coverage")
            if expected is not None and mapping != expected:
                raise ValueError("Paired metadata differs")
            expected = mapping
            if split == "calibration" and any(r["label"] for r in rows):
                raise ValueError("Calibration must be benign")
        tasks[split] = {r["task_id"] for r in next(iter(methods.values()))}
    if tasks["calibration"] & tasks["test"]:
        raise ValueError("Calibration/test task leakage")
