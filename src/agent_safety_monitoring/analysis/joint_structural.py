"""Fixed development-grid structural sensitivity, with task-paired uncertainty."""

from itertools import combinations

import numpy as np
from sklearn.metrics import roc_auc_score

from agent_safety_monitoring.analysis.audit import validate_pairs
from agent_safety_monitoring.evaluation.metrics import calibrate
from agent_safety_monitoring.evaluation.structural import fit_baselines
from agent_safety_monitoring.io import atomic_json, digest, read_json
from agent_safety_monitoring.reporting.report import load_results


def grid_spec(records, features):
    by_id = {f["trajectory_id"]: f for f in features}
    dev = [
        r
        for r in records
        if r["split"] == "development"
        and not r["exclusion"]
        and (r["assignment"] == "benign" or r["outcome"] == "success")
    ]
    fields = [
        "source_tokens"
        if all(
            by_id[r["trajectory_id"]].get("source_tokens") is not None
            for r in records
            if not r["exclusion"]
        )
        else "characters",
        "tool_calls",
    ]
    edges = [
        np.unique(
            np.quantile(
                [np.log1p(by_id[r["trajectory_id"]][field]) for r in dev], [0.2, 0.4, 0.6, 0.8]
            )
        ).tolist()
        for field in fields
    ]
    return {"fields": fields, "log_edges": edges, "development_n": len(dev)}


def evaluate(rows, features, spec, policy):
    x = np.array(
        [[np.log1p(features[r["trajectory_id"]][f]) for f in spec["fields"]] for r in rows]
    )
    cells = np.array([np.digitize(x[:, i], edge) for i, edge in enumerate(spec["log_edges"])]).T
    labels = np.array([r["label"] for r in rows])
    weights = np.zeros(len(rows))
    overlap = []
    for a in range(len(spec["log_edges"][0]) + 1):
        for b in range(len(spec["log_edges"][1]) + 1):
            mask = (cells == [a, b]).all(axis=1)
            counts = [int(sum(mask & (labels == k))) for k in (0, 1)]
            mass = min(counts)
            for k, n in enumerate(counts):
                if n:
                    weights[mask & (labels == k)] = mass / n
            overlap.append(
                {
                    "cell": [a, b],
                    "benign": counts[0],
                    "attack": counts[1],
                    "retained_mass_per_class": mass,
                }
            )
    alerts = policy.alerts([r["score"] for r in rows])
    result = {
        "overlap": overlap,
        "unsupported_n": int(sum(weights == 0)),
        "effective_sample_size": {},
        "weighted_feature_means": {},
        "infeasible_calibration": not policy.feasible,
    }
    for k, metric in ((0, "fpr"), (1, "tpr")):
        mask = labels == k
        w = weights[mask]
        result[metric] = float(np.average(alerts[mask], weights=w)) if w.sum() else None
        result["effective_sample_size"][str(k)] = float(w.sum() ** 2 / (w @ w)) if w.sum() else 0.0
        result["weighted_feature_means"][str(k)] = (
            np.average(x[mask], weights=w, axis=0).tolist() if w.sum() else None
        )
    valid = np.array([r["score"] is not None for r in rows]) & (weights > 0)
    result["auroc_valid"] = (
        float(
            roc_auc_score(
                labels[valid],
                [rows[i]["score"] for i in np.flatnonzero(valid)],
                sample_weight=weights[valid],
            )
        )
        if len(set(labels[valid])) == 2
        else None
    )
    result["conditional_cells"] = []
    for cell in overlap:
        mask = (cells == cell["cell"]).all(axis=1)
        result["conditional_cells"].append(
            {
                **cell,
                **{
                    metric: float(alerts[mask & (labels == k)].mean())
                    if sum(mask & (labels == k))
                    else None
                    for k, metric in ((0, "fpr"), (1, "tpr"))
                },
            }
        )
    return result


def analyze(data, run_root, output, replicates=2000):
    if replicates < 1:
        raise ValueError("Positive bootstrap replicate count required")
    manifest = read_json(data / "manifest.json")
    audit = read_json(data / "audit.json")
    tables = load_results(run_root)
    validate_pairs(tables)
    fitted = fit_baselines(manifest["records"], audit["features"])
    for name, splits in fitted["models"].items():
        for split in ("calibration", "test"):
            metadata = {r["trajectory_id"]: r for r in tables[split][next(iter(tables[split]))]}
            tables[split][f"structural-{name}"] = [
                {**r, "objective": metadata[r["trajectory_id"]]["objective"]} for r in splits[split]
            ]
    validate_pairs(tables)
    mapping = {f["trajectory_id"]: f for f in audit["features"]}
    spec = grid_spec(manifest["records"], audit["features"])
    objectives = {r["trajectory_id"]: r.get("objective") for r in manifest["records"]}
    names = sorted(tables["test"])
    first = names[0]
    cal_tasks = sorted({r["task_id"] for r in tables["calibration"][first]})
    test_tasks = sorted({r["task_id"] for r in tables["test"][first]})
    groups = {
        split: {
            name: {
                task: [r for r in rows if r["task_id"] == task]
                for task in (cal_tasks if split == "calibration" else test_tasks)
            }
            for name, rows in methods.items()
        }
        for split, methods in tables.items()
    }
    points, draws, by_objective = {}, {}, {}
    metrics = ("tpr", "fpr", "auroc_valid")
    objective_names = sorted(
        {objectives[r["trajectory_id"]] for r in tables["test"][first] if r["label"]}
    )
    for name in names:
        policy = calibrate([r["score"] for r in tables["calibration"][name]])
        rows = tables["test"][name]
        points[name] = evaluate(rows, mapping, spec, policy)
        by_objective[name] = {
            obj: evaluate(
                [r for r in rows if not r["label"] or objectives[r["trajectory_id"]] == obj],
                mapping,
                spec,
                policy,
            )
            for obj in objective_names
        }
        draws[name] = {key: np.full(replicates, np.nan) for key in metrics}
    objective_draws = {
        name: {obj: np.full(replicates, np.nan) for obj in objective_names} for name in names
    }
    infeasible = dict.fromkeys(names, 0)
    rng = np.random.default_rng(20261028)
    for i in range(replicates):
        c = rng.choice(cal_tasks, len(cal_tasks), replace=True)
        t = rng.choice(test_tasks, len(test_tasks), replace=True)
        for name in names:
            policy = calibrate(
                [r["score"] for task in c for r in groups["calibration"][name][task]]
            )
            rows = [r for task in t for r in groups["test"][name][task]]
            values = evaluate(rows, mapping, spec, policy)
            infeasible[name] += not policy.feasible
            for key in metrics:
                if values[key] is not None:
                    draws[name][key][i] = values[key]
            for obj in objective_names:
                selected = [
                    r for r in rows if not r["label"] or objectives[r["trajectory_id"]] == obj
                ]
                value = evaluate(selected, mapping, spec, policy)["tpr"]
                if value is not None:
                    objective_draws[name][obj][i] = value

    def interval(values):
        finite = values[np.isfinite(values)]
        return {
            "ci95": np.quantile(finite, [0.025, 0.975]).tolist() if len(finite) else None,
            "usable_replicates": len(finite),
        }

    result = {
        "status": "exploratory",
        "specification": spec,
        "point": points,
        "intervals": {n: {k: interval(v) for k, v in d.items()} for n, d in draws.items()},
        "paired_differences": {
            f"{a} - {b}": {k: interval(draws[a][k] - draws[b][k]) for k in metrics}
            for a, b in combinations(names, 2)
        },
        "per_objective": by_objective,
        "objective_tpr_intervals": {
            n: {o: interval(v) for o, v in d.items()} for n, d in objective_draws.items()
        },
        "infeasible_calibration_replicates": infeasible,
        "manifest_hash": digest(manifest),
        "feature_hash": digest(audit),
        "study_hash": digest(read_json(run_root / "study.json")),
        "replicates": replicates,
        "interpretation": "Fixed development grid; class-balanced common-support test "
        "population differs from the original target population. Calibration unchanged. "
        "Bootstrap recalibrates and reweights whole tasks, conditional on fitted "
        "development baselines and grid. Residual within-cell confounding remains.",
    }
    atomic_json(output, result)
    return {"output": str(output), "methods": len(names), "replicates": replicates}
