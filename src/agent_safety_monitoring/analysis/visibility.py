"""Aggregate-only audit of reasoning-bearing fields in the original Inspect release."""

import re
from collections import Counter
from zipfile import ZipFile

from agent_safety_monitoring.io import atomic_json, file_hash, read_json

REASONING = {"reasoning", "thinking", "redacted_thinking", "chain_of_thought", "scratchpad"}
TAG = re.compile(
    r"<(?:redacted_thinking|hidden_thinking|visible_thinking|think(?:ing)?|reasoning|analysis)\b",
    re.IGNORECASE,
)


def metadata_fields(value, path=()):
    """Match field names only, without opening references or recording values."""
    if isinstance(value, dict):
        for key, item in value.items():
            field = key.lower().replace("-", "_")
            if field in REASONING or field.endswith(("_reasoning", "_thinking", "_cot")):
                yield ".".join((*path, field))
            yield from metadata_fields(item, (*path, "object"))
    elif isinstance(value, list):
        for item in value:
            yield from metadata_fields(item, (*path, "array"))


def content_shape(messages):
    forms, flags = Counter(), set()
    for message in messages:
        if message.role != "assistant":
            continue
        content = message.content
        if isinstance(content, str):
            forms["string"] += 1
            if content.strip():
                flags.add("visible_assistant_text")
            if TAG.search(content):
                flags.add("explicit_reasoning_like_tag")
            continue
        for value in content or []:
            block = value.model_dump(exclude_none=True)
            kind = block["type"]
            forms[f"{kind} ({','.join(sorted(block))})"] += 1
            if kind in REASONING:
                flags.add("explicit_reasoning_block")
            if kind == "text" and block.get("text", "").strip():
                flags.add("visible_assistant_text")
    return forms, flags


def audit_visibility(raw, output):
    from inspect_ai.log import read_eval_log_samples

    source = read_json(raw / "sources.json")
    results = {}
    for label, entry in source["files"].items():
        path = raw / entry["path"]
        sha256 = file_hash(path)
        if sha256 != entry["sha256"]:
            raise ValueError("Raw archive differs from recorded source identity")
        counts, message_forms, choice_forms, provider_fields = (
            Counter(),
            Counter(),
            Counter(),
            Counter(),
        )
        overlay_counts = Counter()
        with ZipFile(path) as archive:
            members = Counter(p.partition("/")[0] for p in archive.namelist())
        for sample in read_eval_log_samples(path, resolve_attachments=False):
            forms, flags = content_shape(sample.messages)
            message_forms.update(forms)
            counts["samples"] += 1
            counts.update(flags)
            if "visible_assistant_text" not in flags and "explicit_reasoning_block" not in flags:
                counts["no_assistant_prose_or_explicit_reasoning"] += 1
            metadata = sample.metadata or {}
            fields = set(metadata_fields(metadata, ("sample_metadata",)))
            actions = (metadata.get("control_tower_overlay") or {}).get("actions", [])
            visible = {
                m.content.strip()
                for m in sample.messages
                if m.role == "assistant" and isinstance(m.content, str) and m.content.strip()
            }
            for field in ("agent_reasoning", "extended_thinking"):
                values = [a.get(field) for a in actions]
                nonempty = [v.strip() for v in values if isinstance(v, str) and v.strip()]
                overlay_counts[f"{field}_samples_nonempty"] += bool(nonempty)
                overlay_counts[f"{field}_actions_nonempty"] += len(nonempty)
                overlay_counts[f"{field}_actions_exact_visible_match"] += sum(
                    value in visible for value in nonempty
                )
                overlay_counts[f"{field}_actions_null"] += sum(v is None for v in values)
                overlay_counts[f"{field}_actions_other_type"] += sum(
                    v is not None and not isinstance(v, str) for v in values
                )
            overlay_counts["actions"] += len(actions)
            has_reasoning_choice = False
            for message in sample.messages:
                fields.update(metadata_fields(getattr(message, "metadata", None), ("message",)))
            for event in sample.events or []:
                if event.event != "model":
                    continue
                model = event.output
                choices = [choice.message for choice in model.choices]
                forms, flags = content_shape(choices)
                choice_forms.update(forms)
                has_reasoning_choice |= "explicit_reasoning_block" in flags
                fields.update(metadata_fields(getattr(model, "metadata", None), ("model",)))
                for message in choices:
                    fields.update(metadata_fields(getattr(message, "metadata", None), ("choice",)))
            counts["samples_with_reasoning_choice_blocks"] += has_reasoning_choice
            provider_fields.update(fields)
        results[label] = {
            "source_sha256": sha256,
            "archive_members_by_prefix": dict(members),
            "counts": dict(counts),
            "assistant_content_shapes": dict(message_forms),
            "model_event_choice_shapes": dict(choice_forms),
            "reasoning_like_metadata_fields": dict(provider_fields),
            "control_tower_action_overlay": dict(overlay_counts),
        }
    result = {
        "schema_version": 1,
        "release": source["dataset"],
        "source_catalog": source["source_page"],
        "attachment_payloads_resolved": False,
        "archives": results,
    }
    atomic_json(output, result)
    return result
