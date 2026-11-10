"""Development seed-repeat variability, distinct from task sampling uncertainty."""

from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

from agent_safety_monitoring.analysis.followup import load_split
from agent_safety_monitoring.experiments.followup import nested_scores, validate_review
from agent_safety_monitoring.io import atomic_json, digest, read_json


def analyze(base):
    selected = set(read_json(base / "screen-ids.json"))
    tables = load_split(base / "development", "development")[0]
    groups = {
        "original": {
            n: [r for r in rows if r["trajectory_id"] in selected]
            for n, rows in tables.items()
            if n.startswith(("five-n", "hundred-n"))
        }
    }
    for repeat in ("seed-1", "seed-2"):
        root = base / repeat
        identity = read_json(root / "identity.json")
        geometry = read_json(root / "development-0-geometry.json")
        if set(geometry["expected_ids"]) != selected or geometry["shards"] != 1:
            raise ValueError("Seed repeat must preserve the original fixed screen")
        saved = {}
        for path in (root / "development").glob("*.json"):
            obj = read_json(path)
            key = obj["key"]
            if (
                key["identity"] != digest(identity)
                or key["evaluation"]["split"] != "development"
                or key["seed"] != identity["config"]["seed"] + 100 * key["sample"]
            ):
                raise ValueError("Seed repeat identity mismatch")
            k = key["trajectory_id"], key["scale"], key["sample"]
            if k in saved:
                raise ValueError("Duplicate seed-repeat sample")
            validate_review(obj["review"], key["scale"])
            saved[k] = obj
        if set(saved) != {
            (uid, scale, i) for uid in selected for scale in ("five", "hundred") for i in range(5)
        }:
            raise ValueError("Incomplete seed-repeat coverage")
        methods = {}
        for uid in sorted(selected):
            for scale in ("five", "hundred"):
                samples = [saved[uid, scale, i] for i in range(5)]
                row = samples[0]["key"]["evaluation"]
                if any(s["key"]["evaluation"] != row for s in samples):
                    raise ValueError("Seed repeat metadata mismatch")
                if row["assignment"] == "attack" and row["outcome"] != "success":
                    continue
                for n, score in nested_scores([s["review"] for s in samples]).items():
                    methods.setdefault(f"{scale}-n{n}", []).append(
                        {
                            "trajectory_id": uid,
                            "task_id": row["task_id"],
                            "score": score,
                            "label": int(row["assignment"] == "attack"),
                        }
                    )
        groups[repeat] = methods
    result = {"status": "development-only descriptive inference-seed variability", "methods": {}}
    for name in groups["original"]:
        results = []
        expected = None
        for repeat, methods in groups.items():
            rows = methods[name]
            metadata = {r["trajectory_id"]: (r["task_id"], r["label"]) for r in rows}
            if expected is not None and expected != metadata:
                raise ValueError("Repeat task/label coverage mismatch")
            expected = metadata
            valid = [r for r in rows if r["score"] is not None]
            auc = (
                float(roc_auc_score([r["label"] for r in valid], [r["score"] for r in valid]))
                if len({r["label"] for r in valid}) == 2
                else None
            )
            results.append(
                {"repeat": repeat, "n": len(rows), "valid_n": len(valid), "auroc_valid": auc}
            )
        aucs = [r["auroc_valid"] for r in results if r["auroc_valid"] is not None]
        result["methods"][name] = {
            "repeats": results,
            "auroc_range": [min(aucs), max(aucs)] if aucs else None,
            "auroc_sample_sd": float(np.std(aucs, ddof=1)) if len(aucs) > 1 else None,
        }
    result["interpretation"] = (
        "Three seed settings on the same fixed development cohort; "
        "not independent datasets, not confidence intervals, and not a held-out tuning criterion."
    )
    atomic_json(base / "seed-variability.json", result)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    analyze(parser.parse_args().base)
