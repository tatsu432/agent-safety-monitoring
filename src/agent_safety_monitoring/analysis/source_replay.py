"""Replay the audited importer against local Inspect logs; never execute source actions."""

from collections import defaultdict

from agent_safety_monitoring.data.ingest import normalize
from agent_safety_monitoring.io import atomic_json, file_hash, read_json


def replay(repository, data, output):
    from inspect_ai.log import read_eval_log

    manifest = read_json(data / "manifest.json")
    records = {r["trajectory_id"]: r for r in manifest["records"]}
    seen, mismatches, tasks = set(), [], defaultdict(set)
    for source, expected in manifest["sources"].items():
        paths = list((repository / "data/raw").rglob(source))
        if len(paths) != 1 or file_hash(paths[0]) != expected:
            raise ValueError("Raw source identity unavailable or mismatched")
        log = read_eval_log(str(paths[0]))
        for sample in log.samples:
            trajectory, record = normalize(sample, paths[0], expected)
            uid = trajectory.id
            if uid in seen or uid not in records:
                raise ValueError("Duplicate or unknown source sample")
            seen.add(uid)
            original = records[uid]
            for field in [
                "task_id",
                "assignment",
                "outcome",
                "objective",
                "source_sha256",
                "sample_id",
            ]:
                if getattr(record, field) != original[field]:
                    mismatches.append(field)
            canonical = read_json(data / "trajectories" / f"{uid}.json")
            if trajectory.model_dump() != canonical:
                mismatches.append("canonical_payload")
            # Check source annotations directly, independently of label lookup in predictions.
            sides = sample.metadata.get("side_tasks", [])
            grade = sample.scores["tasks"].value.get("side")
            if bool(sides) != (original["assignment"] == "attack"):
                mismatches.append("raw_assignment")
            if (
                sides
                and {"success": 1, "failure": 0, "ungraded": None}[original["outcome"]] != grade
            ):
                mismatches.append("raw_grade")
            tasks[original["task_id"]].add(trajectory.task)
    result = {
        "samples_replayed": len(seen),
        "complete": seen == set(records),
        "mismatch_count": len(mismatches),
        "mismatch_fields": sorted(set(mismatches)),
        "tasks_with_inconsistent_genuine_description": sum(len(v) != 1 for v in tasks.values()),
        "interpretation": "Exact replay of audited normalization plus direct raw-label checks; "
        "not a semantic guarantee of harmlessness or absence of visible prompt injection.",
    }
    atomic_json(output, result)
    return result
