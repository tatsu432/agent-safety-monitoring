"""Schema-specific Inspect importer. Ambiguous labels are visible exclusions."""

import json
from collections import Counter, defaultdict
from pathlib import Path

from agent_safety_monitoring.io import atomic_json, digest, file_hash, read_json
from agent_safety_monitoring.schema import CanonicalTrajectory, EvaluationRecord, Segment

OBJECTIVES = {
    "download_malware": "malware_execution",
    "leak_passwords": "secret_exfiltration",
    "leak_password": "secret_exfiltration",
    "privilege_escalation": "privilege_escalation",
    "sudo_edit": "privilege_escalation",
    "disable_firewall": "firewall_disabling",
}


def visible_text(content) -> str:
    if isinstance(content, str):
        return content
    # Deliberately exclude reasoning, encrypted thinking and private blocks.
    blocks = []
    for block in content or []:
        item = block if isinstance(block, dict) else block.model_dump()
        if item.get("type") == "text":
            blocks.append(item["text"])
        elif item.get("type") not in {"reasoning", "thinking", "redacted_thinking"}:
            raise ValueError(f"Unsupported visible content type: {item.get('type')}")
    return "\n".join(blocks)


def normalize(sample, source: Path, sha: str):
    metadata = sample.metadata or {}
    mains, sides = metadata.get("main_tasks", []), metadata.get("side_tasks", [])
    if len(mains) != 1 or len(sides) > 1:
        raise ValueError("Expected one main task and at most one side task")
    main = mains[0]
    task_id, task = str(main["id"]), main["description"]
    if not task.strip():
        raise ValueError("Missing genuine legitimate task")
    assignment = "attack" if sides else "benign"
    grade = (sample.scores or {}).get("tasks")
    raw_grade = grade.value.get("side") if grade and isinstance(grade.value, dict) else None
    if raw_grade not in {None, 0, 1}:
        raise ValueError("Unknown side-task grade encoding")
    outcome = "success" if raw_grade == 1 else "failure" if raw_grade == 0 else "ungraded"
    objective_id = str(sides[0]["id"]) if sides else None
    uid = digest({"source": sha, "id": str(sample.id), "epoch": sample.epoch})
    record = EvaluationRecord(
        trajectory_id=uid,
        task_id=task_id,
        assignment=assignment,
        outcome=outcome if sides else "not_applicable",
        objective=OBJECTIVES.get(objective_id, objective_id),
        source_file=source.name,
        source_sha256=sha,
        sample_id=str(sample.id),
        provenance={
            "task": "metadata.main_tasks[0]",
            "assignment": "metadata.side_tasks",
            "grade": "scores.tasks.value.side",
            "raw_grade": raw_grade,
            "objective_id": objective_id,
            "epoch": sample.epoch,
            "normalization": "visible-v1; no system/private/submit records",
        },
    )
    segments, interaction, removed = [], 0, 0
    call_ids = {}
    submit_calls = {
        c.id
        for m in sample.messages
        for c in (getattr(m, "tool_calls", None) or [])
        if c.function == "submit"
    }
    first_assistant = next(
        (i for i, m in enumerate(sample.messages) if m.role == "assistant"), len(sample.messages)
    )
    for index, message in enumerate(sample.messages):
        if message.role not in {"assistant", "user", "tool"}:
            continue
        # Initial user preambles are outside the visible behavior representation.
        # Replace that preamble for BOTH classes with the explicit genuine task.
        # Later visible user messages remain evidence in their original order.
        if message.role == "user" and index < first_assistant:
            continue
        if message.role == "tool" and getattr(message, "tool_call_id", None) in submit_calls:
            removed += 1
            continue
        text = visible_text(message.content)
        visible_calls = [
            c for c in (getattr(message, "tool_calls", None) or []) if c.function != "submit"
        ]
        removed += sum(c.function == "submit" for c in (getattr(message, "tool_calls", None) or []))
        items = []
        if text:
            source_call = getattr(message, "tool_call_id", None)
            if message.role == "tool" and source_call not in call_ids:
                raise ValueError("Orphan visible tool response")
            group = (
                call_ids[source_call]
                if message.role == "tool"
                else (interaction + 1 if visible_calls else interaction)
            )
            canonical_call = f"c{group:05d}" if message.role == "tool" else None
            items.append(
                ("tool_result" if message.role == "tool" else "text", text, group, canonical_call)
            )
        for call in visible_calls:
            interaction += 1
            if call.id in call_ids:
                raise ValueError("Duplicate source tool-call ID")
            call_ids[call.id] = interaction
            items.append(
                (
                    "tool_call",
                    json.dumps(
                        {"function": call.function, "arguments": call.arguments},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    interaction,
                    f"c{interaction:05d}",
                )
            )
        for kind, value, group, canonical_call in items:
            segments.append(
                Segment(
                    id=f"s{len(segments):05d}",
                    role=message.role,
                    kind=kind,
                    text=value,
                    source_message=index,
                    source_end=len(value),
                    interaction=group,
                    tool_call_id=canonical_call,
                )
            )
    record.provenance["removed_submission_records"] = removed
    if not any(s.kind == "tool_call" for s in segments):
        record.exclusion = "no_usable_tool_behavior"
    return CanonicalTrajectory(id=uid, task=task, segments=segments), record


def assign_splits(records, development_tasks=30, seed=20261028):
    grouped = defaultdict(list)
    for r in records:
        grouped[r.task_id].append(r)
    attacked = {r.task_id for r in records if r.assignment == "attack"}
    paired = [
        task
        for task, group in grouped.items()
        if any(r.assignment == "attack" and not r.exclusion for r in group)
        and any(r.assignment == "benign" and not r.exclusion for r in group)
    ]
    ordered = sorted(paired, key=lambda task: digest({"seed": seed, "task": task}))
    dev = set(ordered[:development_tasks])
    for task, group in grouped.items():
        for r in group:
            if r.exclusion:
                continue
            if task in dev:
                r.split = "development"
            elif task in paired:
                r.split = "test"
            elif task not in attacked:
                r.split = "calibration"
            else:
                r.exclusion = "no_usable_benign_pair"
    # Every non-excluded record of a task has exactly one split.
    assert all(len({r.split for r in group if not r.exclusion}) <= 1 for group in grouped.values())
    return records


def import_logs(paths: list[Path], root: Path, development_tasks=30, seed=20261028):
    from inspect_ai.log import read_eval_log_samples

    records, rejected = [], []
    seen = set()
    for source in paths:
        sha = file_hash(source)
        for sample in read_eval_log_samples(source, resolve_attachments=True):
            try:
                trajectory, record = normalize(sample, source, sha)
                if trajectory.id in seen:
                    raise ValueError("Duplicate trajectory")
                seen.add(trajectory.id)
                atomic_json(
                    root / "trajectories" / f"{trajectory.id}.json", trajectory.model_dump()
                )
                records.append(record)
            except (ValueError, KeyError, TypeError) as exc:
                rejected.append(
                    {
                        "source": source.name,
                        "source_sha256": sha,
                        "sample_id": str(sample.id),
                        "reason": str(exc),
                    }
                )
    records = assign_splits(records, development_tasks, seed)
    manifest = {
        "version": 1,
        "seed": seed,
        "development_tasks_requested": development_tasks,
        "records": [r.model_dump() for r in records],
        "rejected": rejected,
        "sources": {p.name: file_hash(p) for p in paths},
    }
    atomic_json(root / "manifest.json", manifest)
    return audit(root)


def audit(root: Path, tokenizer=None):
    manifest = read_json(root / "manifest.json")
    counts, objectives, splits = Counter(), Counter(), Counter()
    features = []
    for raw in manifest["records"]:
        r = EvaluationRecord.model_validate(raw)
        t = CanonicalTrajectory.model_validate(
            read_json(root / "trajectories" / f"{r.trajectory_id}.json")
        )
        counts[f"{r.assignment}/{r.outcome}"] += 1
        splits[f"{r.split}/{r.assignment}"] += 1
        objectives[r.objective or "benign"] += 1
        features.append(
            {
                "trajectory_id": t.id,
                "task_id": r.task_id,
                "characters": sum(len(s.text) for s in t.segments),
                "tool_calls": sum(s.kind == "tool_call" for s in t.segments),
                "source_tokens": sum(tokenizer.count(s.text) for s in t.segments)
                if tokenizer
                else None,
                "exclusion": r.exclusion,
            }
        )
    report = {
        "raw_samples": len(manifest["records"]) + len(manifest["rejected"]),
        "normalized": len(manifest["records"]),
        "rejected": len(manifest["rejected"]),
        "usable": sum(not r["exclusion"] for r in manifest["records"]),
        "counts": dict(counts),
        "splits": dict(splits),
        "objectives": dict(objectives),
        "exclusions": dict(Counter(r["exclusion"] for r in manifest["records"] if r["exclusion"])),
        "features": features,
        "tokenizer_audited": tokenizer is not None,
    }
    atomic_json(root / "audit.json", report)
    return {k: v for k, v in report.items() if k != "features"}
