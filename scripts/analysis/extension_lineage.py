"""Compare release overlay text to the upstream exports without retaining any text."""

import argparse
from collections import Counter
from pathlib import Path

from inspect_ai.log import read_eval_log_samples

from agent_safety_monitoring.io import digest, file_hash, immutable_json

SOURCES = {
    "honest.eval": "92e62b8bcb2700bd654d48770e0ec92d",
    "attack.eval": "ed64e4e857de9f578fca148b3c18ef11",
}


def collect(path):
    rows, counts = {}, Counter()
    for sample in read_eval_log_samples(path, resolve_attachments=False):
        actions = sample.metadata.get("control_tower_overlay", {}).get("actions", [])
        present = [a for a in actions if a.get("extended_thinking")]
        key = tuple(a["tool_call_id"] for a in present)
        if key:
            if key in rows:
                raise ValueError("Duplicate nonempty overlay call sequence")
            rows[key] = digest([a["extended_thinking"] for a in present])
        reasoning = sum(
            b.type == "reasoning"
            for e in sample.events or []
            if e.event == "model"
            for c in e.output.choices
            if isinstance(c.message.content, list)
            for b in c.message.content
        )
        counts.update(
            samples=1,
            nonempty_overlay_actions=len(present),
            independent_model_reasoning_blocks=reasoning,
        )
    return rows, counts


def compare(release, upstream):
    results = {}
    for name, run in SOURCES.items():
        frozen, old = release / name, upstream / name
        old_data, old_count = collect(old)
        new_data, new_count = collect(frozen)
        overlap = old_data.keys() & new_data.keys()
        results[name] = {
            "upstream_run": run,
            "upstream_sha256": file_hash(old),
            "release_sha256": file_hash(frozen),
            "upstream_counts": dict(old_count),
            "release_counts": dict(new_count),
            "shared_nonempty_sequences": len(overlap),
            "identical_overlay_content_sequences": sum(old_data[k] == new_data[k] for k in overlap),
        }
    return {
        "version": 1,
        "matches_establish_export_lineage": True,
        "independent_evidence_of_authorship": False,
        "archives": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    immutable_json(args.output, compare(args.release, args.upstream))
