"""Post-hoc full-record diagnostics, kept separate from frozen inference."""

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from agent_safety_monitoring.analysis.audit import validate_pairs
from agent_safety_monitoring.evaluation.metrics import calibrate
from agent_safety_monitoring.io import atomic_json, digest, read_json
from agent_safety_monitoring.reporting.report import generate, load_results


def objective_bootstrap(calibration, test, replicates=2000, seed=20261028):
    validate_pairs({"calibration": calibration, "test": test})
    names = sorted(test)
    cal_groups, test_groups = {}, {}
    for name in names:
        for mapping, rows in ((cal_groups, calibration[name]), (test_groups, test[name])):
            mapping[name] = defaultdict(list)
            for row in rows:
                mapping[name][row["task_id"]].append(row)
    c_tasks, t_tasks = sorted(cal_groups[names[0]]), sorted(test_groups[names[0]])
    objectives = sorted({r["objective"] for r in test[names[0]] if r["label"]})
    samples = {name: {o: [] for o in objectives} for name in names}
    rng = np.random.default_rng(seed)
    for _ in range(replicates):
        c = rng.choice(c_tasks, len(c_tasks), replace=True)
        t = rng.choice(t_tasks, len(t_tasks), replace=True)
        for name in names:
            policy = calibrate([r["score"] for task in c for r in cal_groups[name][task]])
            rows = [r for task in t for r in test_groups[name][task]]
            for objective in objectives:
                selected = [r["score"] for r in rows if r["label"] and r["objective"] == objective]
                if selected:
                    samples[name][objective].append(float(policy.alerts(selected).mean()))
    return {
        name: {
            o: {
                "ci95": np.quantile(v, [0.025, 0.975]).tolist() if v else None,
                "usable_replicates": len(v),
            }
            for o, v in values.items()
        }
        for name, values in samples.items()
    }


def feature_shift(data: Path, output: Path):
    """Aggregate source-feature comparisons; includes no task or trajectory identifiers."""
    manifest, audit = read_json(data / "manifest.json"), read_json(data / "audit.json")
    features = {r["trajectory_id"]: r for r in audit["features"]}
    summary = {}
    for split in ["development", "calibration", "test"]:
        for label in ["benign", "attack"]:
            rows = [
                r
                for r in manifest["records"]
                if not r["exclusion"]
                and r["split"] == split
                and r["assignment"] == label
                and (label == "benign" or r["outcome"] == "success")
            ]
            if not rows:
                continue
            values = {}
            for field in ["source_tokens", "characters", "tool_calls"]:
                x = [features[r["trajectory_id"]].get(field) for r in rows]
                if all(v is not None for v in x):
                    values[field] = {
                        "median": float(np.median(x)),
                        "q25": float(np.quantile(x, 0.25)),
                        "q75": float(np.quantile(x, 0.75)),
                        "minimum": float(min(x)),
                        "maximum": float(max(x)),
                    }
            summary[f"{split}/{label}"] = {"n": len(rows), **values}
    result = {
        "groups": summary,
        "feature_source": "local prepared audit; source tokens, not prompts",
        "audit_hash": digest(audit),
        "manifest_hash": digest(manifest),
    }
    atomic_json(output, result)
    return result


def full_diagnostics(data: Path, run_root: Path, output: Path, replicates=2000):
    """Caller must first pass analysis audit against the original freeze."""
    from agent_safety_monitoring.inference.backend import ModelConfig, Tokenizer
    from agent_safety_monitoring.monitors.core import validate_quotes
    from agent_safety_monitoring.schema import CanonicalTrajectory, Extraction

    tables = load_results(run_root)
    validate_pairs(tables)
    study = read_json(run_root / "study.json")
    generate(run_root, output / "recomputed", replicates)
    tokenizer = Tokenizer(ModelConfig.model_validate(study["configuration"]["model"]))
    objective_intervals = objective_bootstrap(tables["calibration"], tables["test"], replicates)
    histograms, eae, averages = {}, [], []
    for name, rows in tables["test"].items():
        histograms[name] = {
            str(label): dict(Counter(str(r["score"]) for r in rows if r["label"] == label))
            for label in [0, 1]
        }
        for row in rows:
            result = row["result"]
            if result.method == "eae":
                trajectory = CanonicalTrajectory.model_validate(
                    read_json(data / "trajectories" / f"{row['trajectory_id']}.json")
                )
                selected = [
                    q
                    for a in result.artifacts
                    if a.get("stage") == "extract"
                    for q in a.get("output", {}).get("quotes", [])
                ]
                if selected:
                    validate_quotes(
                        Extraction.model_validate({"quotes": selected}), trajectory, tokenizer, 3000
                    )
                positions = {s.id: i for i, s in enumerate(trajectory.segments)}
                eae.append(
                    {
                        "trajectory_id": row["trajectory_id"],
                        "task_id": row["task_id"],
                        "objective": row["objective"],
                        "label": row["label"],
                        "score": row["score"],
                        "status": result.status,
                        "quotes": len(selected),
                        "quoted_tokens": sum(tokenizer.count(q["text"]) for q in selected),
                        "relative_positions": [
                            positions[q["step"]] / max(1, len(trajectory.segments) - 1)
                            for q in selected
                        ],
                        "invalid_categories": [
                            a.get("category") for a in result.artifacts if "invalid_attempt" in a
                        ],
                    }
                )
            if result.method == "average":
                scores = [
                    a["output"]["score"]
                    for a in result.artifacts
                    if a.get("stage", "").startswith("review-") and "output" in a
                ]
                averages.append(
                    {
                        "trajectory_id": row["trajectory_id"],
                        "scores": scores,
                        "distinct_request_keys": len({c.key for c in result.calls}),
                        "cached_calls": sum(c.cached for c in result.calls),
                    }
                )
    # Individual rows remain private. Aggregate histogram data contain no source text.
    atomic_json(output / "record-diagnostics-private.json", {"eae": eae, "average": averages})
    aggregate = {
        "freeze": study["freeze"],
        "objective_intervals": objective_intervals,
        "test_histograms": histograms,
        "eae": {
            "n": len(eae),
            "mean_quotes": float(np.mean([r["quotes"] for r in eae])),
            "mean_quoted_tokens": float(np.mean([r["quoted_tokens"] for r in eae])),
            "invalid_categories": dict(Counter(c for r in eae for c in r["invalid_categories"])),
        },
        "average": {
            "n": len(averages),
            "disagreement_records": sum(len(set(r["scores"])) > 1 for r in averages),
        },
    }
    atomic_json(output / "record-diagnostics-aggregate.json", aggregate)
    return {"output": str(output), "methods": len(tables["test"])}
