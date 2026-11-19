"""Verify and compare the frozen medium-effort held-out results."""

import argparse
from pathlib import Path

from development_diagnostics import FineMonitoringResult

from agent_safety_monitoring.analysis.followup import load_split
from agent_safety_monitoring.analysis.operating_points import comparison
from agent_safety_monitoring.io import atomic_json, digest, file_hash, read_json
from agent_safety_monitoring.reporting.report import load_results


def analyze(root, plan_path, data, followup, original, output):
    plan = read_json(plan_path)
    if digest(plan["body"]) != plan["hash"]:
        raise ValueError("Invalid held-out freeze")
    manifest = read_json(data / "manifest.json")
    records = {r["trajectory_id"]: r for r in manifest["records"]}
    tables = {}
    hashes = {}
    summaries = {}
    for split in ("calibration", "test"):
        directory = root / "think-hundred" / split
        identity = read_json(directory / "identity.json")
        summary = read_json(directory / "summary.json")
        expected = plan["body"]["expected"][split]
        if (
            identity["heldout_freeze"] != plan["hash"]
            or identity["screen_sha256"] != digest(expected)
            or identity["sources"] != plan["body"]["sources"]
            or identity["model"] != plan["body"]["model"]
            or summary["identity"] != digest(identity)
            or summary["records"] != len(expected)
        ):
            raise ValueError("Held-out run identity or summary mismatch")
        paths = {
            p.stem: p for p in directory.glob("*.json") if p.stem not in ("identity", "summary")
        }
        if set(paths) != set(expected):
            raise ValueError("Missing or unexpected review artifacts")
        rows = []
        for uid in expected:
            item = read_json(paths[uid])
            result = FineMonitoringResult.model_validate(item["result"])
            if item["identity"] != digest(identity) or result.trajectory_id != uid:
                raise ValueError("Review identity mismatch")
            hashes[f"{split}/{uid}"] = file_hash(paths[uid])
            row = records[uid]
            if row["assignment"] == "attack" and row["outcome"] != "success":
                continue
            rows.append(
                {
                    "trajectory_id": uid,
                    "task_id": row["task_id"],
                    "label": int(row["assignment"] == "attack"),
                    "objective": row["objective"],
                    "score": result.score if result.status == "valid" else None,
                }
            )
        if summary["invalid"] != sum(
            FineMonitoringResult.model_validate(read_json(p)["result"]).status != "valid"
            for p in paths.values()
        ):
            raise ValueError("Invalid count mismatch")
        existing = load_split(followup, split)[0]
        tables[split] = {
            k: existing[k] for k in ("five-n1", "hundred-n1", "hundred-n2", "hundred-n5")
        }
        original_rows = load_results(original)[split]
        for method, values in original_rows.items():
            if method.startswith(("think-", "average-")):
                tables[split]["original-" + method.split("-", 1)[0]] = values
        tables[split]["hundred-think-medium"] = rows
        summaries[split] = summary
    result = {
        "status": "exploratory, original test previously examined",
        "freeze": plan["hash"],
        "review_inventory_sha256": digest(hashes),
        "coverage": {k: len(v) for k, v in plan["body"]["expected"].items()},
        "summaries": summaries,
        "five_percent": comparison(tables["calibration"], tables["test"]),
        "one_percent": comparison(tables["calibration"], tables["test"], target=0.01),
    }
    atomic_json(output, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("root", "plan", "data", "followup", "original", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.root, args.plan, args.data, args.followup, args.original, args.output)
