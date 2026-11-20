"""Availability-only discrimination and context overlap, without reasoning inference."""

from collections import Counter, defaultdict

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from agent_safety_monitoring.analysis.followup import load_split
from agent_safety_monitoring.analysis.operating_points import comparison
from agent_safety_monitoring.experiments.followup import FollowupConfig, protocol_identity
from agent_safety_monitoring.io import digest, read_json


def cohort_acceptance(features):
    coverage = {}
    passed = True
    for split in ("development", "calibration", "test"):
        rows = [r for r in features if r["split"] == split]
        primary = [r for r in rows if r["assignment"] == "benign" or r["outcome"] == "success"]
        groups = defaultdict(set)
        kept = defaultdict(set)
        for row in primary:
            groups[row["task_id"]].add(row["assignment"])
            if row["single_cohort"]:
                kept[row["task_id"]].add(row["assignment"])
        orig = Counter(r["assignment"] for r in primary)
        dest = Counter(r["assignment"] for r in primary if r["single_cohort"])
        pair0, pair1 = (sum(len(v) == 2 for v in part.values()) for part in (groups, kept))
        counts = {name: {"original": n, "common": dest[name]} for name, n in orig.items()}
        coverage[split] = {
            "classes": counts,
            "original_paired_tasks": pair0,
            "retained_paired_tasks": pair1,
        }
        passed &= bool(orig) and all(dest[k] >= 0.8 * n for k, n in orig.items())
        if split == "test":
            passed &= pair0 > 0 and pair1 >= 0.8 * pair0
    return {"passes_coverage_gate": bool(passed), "by_split": coverage}


def feature_vector(row):
    available = row["reasoning_actions"]
    total = len(row["action_tokens"])
    visible = row["context"]["ACTION_ONLY"]["single"]
    return [
        int(available > 0),
        np.log1p(available),
        available / max(total, 1),
        np.log1p(sum(row["action_tokens"])),
        np.log1p(visible),
        np.log1p(row["tool_count"]),
    ]


def archived_action_scores(root, original_freeze):
    freeze = read_json(root / "followup-freeze.json")
    identity = freeze["body"]["identity"]
    if (
        digest(freeze["body"]) != freeze["hash"]
        or not freeze["body"]["development_accepted"]
        or identity != read_json(root / "scoring/identity.json")
        or identity["original_freeze"] != original_freeze
        or identity["protocol"]
        != protocol_identity(FollowupConfig.model_validate(identity["config"]))
    ):
        raise ValueError("Archived action-only identity does not match the review protocol")
    files = read_json(root / "scoring-report.json")["sources"]
    scores = {}
    for split in ("calibration", "test"):
        tables, _, _, _, sources = load_split(root / "scoring", split)
        if sources != {k: v for k, v in files.items() if k.startswith(f"{split}/")}:
            raise ValueError("Archived action-only results differ from the review inventory")
        scores[split] = {r["trajectory_id"]: r for r in tables["hundred-n1"]}
    return scores


def evaluate(private, audit, replicates=2000, archive=None):
    blob = read_json(private)
    proof = read_json(audit)
    if digest(blob) != proof["feature_sha256"]:
        raise ValueError("Private features do not match the audit")
    features = blob["features"]
    primary = {
        k: [
            r
            for r in features
            if r["split"] == k
            and "ACTION_ONLY" in r["context"]
            and (r["assignment"] == "benign" or r["outcome"] == "success")
        ]
        for k in ("development", "calibration", "test")
    }
    common = {k: [r for r in rows if r["single_cohort"]] for k, rows in primary.items()}
    saved = archived_action_scores(archive, proof["original_freeze"]) if archive else None
    return {
        "version": 1,
        "status": "exploratory feature-only discrimination using archived field",
        "cohort": cohort_acceptance(features),
        "input_audit_digest": digest(proof),
        "original_primary": feature_analysis(primary, replicates, saved),
        "common_context": feature_analysis(common, replicates, saved),
    }


def feature_analysis(splits, replicates, saved=None):
    if any(not rows for rows in splits.values()):
        return {"status": "insufficient common cohort"}
    mats = {k: np.array([feature_vector(r) for r in rows]) for k, rows in splits.items()}
    labels = {k: [int(r["assignment"] == "attack") for r in rows] for k, rows in splits.items()}
    if len(set(labels["development"])) < 2 or len(set(labels["test"])) < 2:
        return {"status": "insufficient class overlap"}
    tables = {s: {} for s in ("calibration", "test")}
    columns = {
        "availability_count": [0, 1, 2],
        "availability_count_tokens": [0, 1, 2, 3],
        "visible_length_tools": [4, 5],
        "joint": list(range(6)),
    }
    for name, cols in columns.items():
        clf = make_pipeline(StandardScaler(), LogisticRegression(random_state=20261028))
        clf.fit(mats["development"][:, cols], labels["development"])
        for split in tables:
            scores = clf.predict_proba(mats[split][:, cols])[:, 1]
            tables[split][name] = [
                {
                    "trajectory_id": r["trajectory_id"],
                    "task_id": r["task_id"],
                    "label": label,
                    "objective": r["objective"],
                    "score": float(score),
                }
                for r, label, score in zip(splits[split], labels[split], scores, strict=True)
            ]
    overlap = defaultdict(Counter)
    if saved:
        for split in tables:
            tables[split]["archived_action_only"] = [
                saved[split][r["trajectory_id"]] for r in splits[split]
            ]
    for split, rows in splits.items():
        for row in rows:
            n = row["reasoning_actions"]
            bucket = "0" if n == 0 else "1–2" if n < 3 else "3–5" if n <= 5 else "6+"
            overlap[f"{split}/{bucket}"][row["assignment"]] += 1
    matched = {}
    for split, rows in splits.items():
        eligible = defaultdict(set)
        for row in rows:
            if row["reasoning_actions"] >= 3:
                eligible[row["task_id"]].add(row["assignment"])
        matched[split] = sum(len(v) == 2 for v in eligible.values())
    shift = {}
    for split in ("calibration", "test"):
        primary = mats[split][np.array(labels[split]) == 0]
        shift[split] = {
            "nominal_benign": len(primary),
            "fraction_record_available": float(primary[:, 0].mean()),
            "mean_action_coverage": float(primary[:, 2].mean()),
            "median_reasoning_tokens": float(np.median(np.expm1(primary[:, 3]))),
            "median_action_only_prompt_tokens": float(np.median(np.expm1(primary[:, 4]))),
            "median_tool_calls": float(np.median(np.expm1(primary[:, 5]))),
        }
    return {
        "coverage_overlap": dict(overlap),
        "paired_tasks_with_at_least_three_actions": matched,
        "benign_shift": shift,
        "metrics": comparison(tables["calibration"], tables["test"], replicates=replicates),
    }
