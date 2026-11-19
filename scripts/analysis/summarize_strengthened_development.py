"""Aggregate paired development diagnostics without exposing records or addresses."""

import argparse
from collections import Counter
from pathlib import Path

from development_diagnostics import FineMonitoringResult
from sklearn.metrics import roc_auc_score

from agent_safety_monitoring.analysis.diagnosis import terminal_branches
from agent_safety_monitoring.analysis.followup import load_split
from agent_safety_monitoring.io import atomic_json, digest, file_hash, read_json
from agent_safety_monitoring.schema import MonitoringResult


def discrimination(rows):
    counts = Counter(label for label, score in rows if score is not None)
    valid = [(label, score) for label, score in rows if score is not None]
    y, x = zip(*valid, strict=True) if valid else ([], [])
    return {
        "eligible_records": len(rows),
        "valid_benign": counts[0],
        "valid_attack": counts[1],
        "auroc": float(roc_auc_score(y, x)) if len(counts) == 2 else None,
    }


def summarize(followup, original_data, fine_think, mechanism_root, output):
    ids = set(read_json(followup / "screen-ids.json"))
    manifest = read_json(original_data / "manifest.json")
    labels = {
        r["trajectory_id"]: int(r["assignment"] == "attack")
        for r in manifest["records"]
        if r["trajectory_id"] in ids
        and r["split"] == "development"
        and (r["assignment"] == "benign" or r["outcome"] == "success")
    }
    replay = load_split(followup / "development", "development")[0]
    methods = {
        n: discrimination(
            [(r["label"], r["score"]) for r in replay[n] if r["trajectory_id"] in ids]
        )
        for n in ("hundred-n1", "hundred-n2", "hundred-n5", "five-n1", "five-n2")
    }
    missing = []
    evidence = mechanism_root / "evidence-intervention/summary.json"
    for directory in (
        fine_think,
        *(
            mechanism_root / name
            for name in (
                "eae-hundred",
                "mrt-five-5-512",
                "mrt-five-5-1024",
                "mrt-five-10-512",
                "mrt-hundred",
            )
        ),
    ):
        summary = directory / "summary.json"
        if not summary.exists():
            missing.append(directory.name)
            continue
        identity = read_json(directory / "identity.json")
        current = read_json(summary)
        if (
            identity["screen_sha256"] != digest(read_json(followup / "screen-ids.json"))
            or digest(identity) != current["identity"]
            or current["records"] != len(ids)
        ):
            raise ValueError("Development diagnostic identity or exact screen coverage differs")
        paths = {
            p.stem: p for p in directory.glob("*.json") if p.stem not in ("summary", "identity")
        }
        if set(paths) != ids:
            raise ValueError("Development diagnostic record coverage differs")
        rows, branches = [], {"sequential": [], "hierarchical": []}
        result_type = (
            FineMonitoringResult if identity["config"]["scale"] == "hundred" else MonitoringResult
        )
        for uid, path in paths.items():
            item = read_json(path)
            saved = result_type.model_validate(item["result"])
            if item["identity"] != current["identity"] or saved.trajectory_id != uid:
                raise ValueError("Saved diagnostic result identity differs")
            if uid not in labels:
                continue
            rows.append((labels[uid], saved.score))
            if identity["config"]["method"] == "mrt":
                seq, tree, _, _ = terminal_branches(saved)
                branches["sequential"].append((labels[uid], seq["score"] if seq else None))
                branches["hierarchical"].append((labels[uid], tree["score"] if tree else None))
        methods[directory.name] = {
            **discrimination(rows),
            "branches": {name: discrimination(rows) for name, rows in branches.items() if rows},
            "screen_records": current["records"],
            "screen_invalid": current["invalid"],
            "costs": current["costs"],
            "decision_latency_median": current["decision_latency_median"],
            "decision_latency_p95": current["decision_latency_p95"],
            "workload_seconds": current["invocation_workload_seconds"],
            "summary_sha256": file_hash(summary),
        }
    result = {
        "screen_records": len(ids),
        "status": "development discrimination and selected-case evidence interventions",
        "methods": methods,
        "missing_conditions": missing,
        "evidence_intervention": read_json(evidence) if evidence.exists() else None,
    }
    atomic_json(output, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("followup", "original-data", "fine-think", "mechanism-root", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    summarize(args.followup, args.original_data, args.fine_think, args.mechanism_root, args.output)
