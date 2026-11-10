"""Coverage-checked exploratory scaling analysis and development-only selection."""

from collections import Counter

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve

from agent_safety_monitoring.experiments.followup import (
    coarsen_hundred,
    nested_scores,
    validate_review,
)
from agent_safety_monitoring.io import atomic_json, digest, file_hash, read_json

NS = (1, 2, 3, 5)


def load_split(root, split):
    identity = read_json(root / "identity.json")
    geometry = [read_json(p) for p in root.glob(f"{split}-*-geometry.json")]
    if (
        not geometry
        or len({g["shards"] for g in geometry}) != 1
        or {g["shard"] for g in geometry} != set(range(geometry[0]["shards"]))
    ):
        raise ValueError("Missing or incomplete shard geometry")
    expected = [uid for g in geometry for uid in g["expected_ids"]]
    if len(set(expected)) != len(expected) or set(expected) != set(identity["expected"][split]):
        raise ValueError("Incomplete or duplicate expected trajectory coverage")
    groups, sources = {}, {}
    for path in sorted((root / split).glob("*.json")):
        saved = read_json(path)
        key = saved["key"]
        row = key["evaluation"]
        if (
            key["identity"] != digest(identity)
            or row["split"] != split
            or row["trajectory_id"] != key["trajectory_id"]
        ):
            raise ValueError("Result identity/metadata mismatch")
        if key["seed"] != identity["config"]["seed"] + key["sample"] * 100:
            raise ValueError("Seed mismatch")
        k = key["trajectory_id"], key["scale"], key["sample"]
        if k in groups:
            raise ValueError("Duplicate sample")
        validate_review(saved["review"], key["scale"])
        groups[k] = saved
        sources[str(path.relative_to(root))] = file_hash(path)
    wanted = {
        (uid, scale, i)
        for uid in expected
        for scale in identity["config"]["score_scales"]
        for i in range(5)
    }
    if set(groups) != wanted:
        raise ValueError("Incomplete or unexpected sample coverage")
    tables, costs, disagreement, supplementary = {}, {}, {}, Counter()
    for uid in expected:
        for scale in identity["config"]["score_scales"]:
            samples = [groups[uid, scale, i] for i in range(5)]
            row = samples[0]["key"]["evaluation"]
            if any(s["key"]["evaluation"] != row for s in samples):
                raise ValueError("Sample metadata mismatch")
            if row["assignment"] == "attack" and row["outcome"] != "success":
                supplementary[f"{scale}/{row['outcome']}"] += 1
                continue
            reviews = [s["review"] for s in samples]
            scores = [r["score"] for r in reviews if r["status"] == "valid"]
            d = disagreement.setdefault(
                scale,
                {"records": 0, "complete_records": 0, "disagreeing_records": 0, "variances": []},
            )
            d["records"] += 1
            if len(scores) == 5:
                d["complete_records"] += 1
                d["disagreeing_records"] += len(set(scores)) > 1
                d["variances"].append(float(np.var(scores)))
            for n, score in nested_scores(reviews).items():
                n_int = int(n)
                item = {
                    "trajectory_id": uid,
                    "task_id": row["task_id"],
                    "label": int(row["assignment"] == "attack"),
                    "score": score,
                    "objective": row.get("objective"),
                }
                name = f"{scale}-n{n}"
                tables.setdefault(name, []).append(item)
                c = costs.setdefault(
                    name,
                    {
                        "logical_calls": 0,
                        "cache_hits": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "request_latency_seconds": 0.0,
                        "allocated_gpu_seconds": None,
                    },
                )
                for r in reviews[:n_int]:
                    for call in r.get("calls", []):
                        c["logical_calls"] += 1
                        c["cache_hits"] += call["cached"]
                        for field in ("input_tokens", "output_tokens"):
                            c[field] += call["usage"][field]
                        c["request_latency_seconds"] += call["latency_seconds"]
                if scale == "hundred":
                    tables.setdefault(f"hundred-binned-n{n}", []).append(
                        {**item, "score": coarsen_hundred(score)}
                    )
                    coarse = (
                        sum(coarsen_hundred(r["score"]) for r in reviews[:n_int]) / n_int
                        if score is not None
                        else None
                    )
                    tables.setdefault(f"hundred-bin-first-n{n}", []).append(
                        {**item, "score": coarse}
                    )
    for d in disagreement.values():
        values = d.pop("variances")
        d["mean_within_record_variance"] = float(np.mean(values)) if values else None
    for c in costs.values():
        c["new_calls"] = c["logical_calls"] - c["cache_hits"]
    return tables, costs, disagreement, dict(supplementary), sources


def report(root, output, replicates=2000, original_run=None):
    from agent_safety_monitoring.analysis.operating_points import comparison

    loaded = {split: load_split(root, split) for split in ("calibration", "test")}
    tables = {s: v[0] for s, v in loaded.items()}
    original_provenance = None
    if original_run is not None:
        from agent_safety_monitoring.reporting.report import load_results

        study = read_json(original_run / "study.json")
        followup_identity = read_json(root / "identity.json")
        if study["software_only"] or study["freeze"] != followup_identity["original_freeze"]:
            raise ValueError("Original comparison must use the same real frozen study")
        original = load_results(original_run)
        for split, methods in original.items():
            for name, rows in methods.items():
                tables[split][f"original-{name}"] = rows
        original_provenance = {
            "study_sha256": file_hash(original_run / "study.json"),
            "freeze": study["freeze"],
            "result_hashes_sha256": digest(
                {
                    str(p.relative_to(original_run)): file_hash(p)
                    for split in ("calibration", "test")
                    for p in sorted((original_run / split).glob("*/*.json"))
                }
            ),
        }
    scoring = comparison(tables["calibration"], tables["test"], replicates)
    distributions, curves = {}, {}
    for split, methods in tables.items():
        distributions[split] = {}
        for name, rows in methods.items():
            counts = Counter(r["score"] for r in rows if r["score"] is not None)
            cutoff = scoring["point"][name]["policy"]["cutoff"]
            distributions[split][name] = {
                "n": len(rows),
                "invalid": sum(r["score"] is None for r in rows),
                "unique_scores": len(counts),
                "tied_pair_fraction": (
                    sum(n * (n - 1) for n in counts.values())
                    / (sum(counts.values()) * (sum(counts.values()) - 1))
                    if sum(counts.values()) > 1
                    else None
                ),
                "at_calibration_boundary": sum(r["score"] == cutoff for r in rows)
                if cutoff is not None
                else 0,
                "histogram_by_label": {
                    str(label): [
                        [s, sum(r["score"] == s and r["label"] == label for r in rows)]
                        for s in sorted(counts)
                    ]
                    for label in (0, 1)
                },
            }
            if split == "test":
                valid = [r for r in rows if r["score"] is not None]
                if len({r["label"] for r in valid}) == 2:
                    x, y, _ = roc_curve(
                        [r["label"] for r in valid],
                        [r["score"] for r in valid],
                        drop_intermediate=False,
                    )
                    curves[name] = {"fpr": x.tolist(), "tpr": y.tolist()}
    marginal = {}
    for scale in ("five", "hundred"):
        if f"{scale}-n1" not in tables["test"]:
            continue
        for a, b in zip(NS, NS[1:], strict=False):
            previous, following = f"{scale}-n{a}", f"{scale}-n{b}"
            delta = scoring["point"][following]["tpr"] - scoring["point"][previous]["tpr"]
            # comparison() stores alphabetically ordered differences.
            ci = scoring["paired_differences"][f"{previous} - {following}"]["tpr"]
            marginal[f"{scale}:{a}->{b}"] = {
                "additional_reviews": b - a,
                "tpr_difference": delta,
                "tpr_difference_per_review": delta / (b - a),
                "ci95": [-ci["ci95"][1], -ci["ci95"][0]] if ci["ci95"] else None,
                "usable_replicates": ci["usable_replicates"],
            }
    result = {
        "status": "exploratory; original test previously examined",
        "identity": digest(read_json(root / "identity.json")),
        "original_comparison_provenance": original_provenance,
        "sources": {k: v for loaded_split in loaded.values() for k, v in loaded_split[4].items()},
        "scoring": scoring,
        "logical_costs": {s: v[1] for s, v in loaded.items()},
        "disagreement": {s: v[2] for s, v in loaded.items()},
        "supplementary_counts": {s: v[3] for s, v in loaded.items()},
        "distributions": distributions,
        "roc_curves": curves,
        "marginal": marginal,
        "cost_definition": "Nested Ns share calls; logical calls include retries/cache reuse. "
        "Request latency is not allocated GPU time. Bind homogeneous timings separately.",
        "coarsening": {
            "bins": "[0,20),[20,40),[40,60),[60,80),[80,100]",
            "hundred-binned": "coarsen(mean(fine scores))",
            "hundred-bin-first": "mean(coarsen(each fine score))",
        },
    }
    atomic_json(output, result)
    return {"output": str(output), "methods": len(tables["test"])}


def select_development(root, measurements, output):
    """Fixed candidates have no fitted parameters; folds hold entire tasks together."""
    tables, _, _, supplementary, sources = load_split(root, "development")
    timing = read_json(measurements)
    identity = read_json(root / "identity.json")
    if timing["identity"] != digest(identity) or timing.get("software_only", True):
        raise ValueError("Compatible physical development timings required")
    tasks = sorted(
        {r["task_id"] for rows in tables.values() for r in rows},
        key=lambda task: digest([20261028, task]),
    )
    if len(tasks) < 5:
        raise ValueError("Five grouped folds require at least five development tasks")
    folds = {task: i % 5 for i, task in enumerate(tasks)}
    candidates = {}
    for name, rows in tables.items():
        if "binned" in name or "bin-first" in name:
            continue
        cost = timing["methods"][name]
        seconds = cost["gpu_seconds_per_trajectory"]
        if (
            not np.isfinite(seconds)
            or seconds <= 0
            or not cost.get("cold_complete")
            or not cost.get("job_id")
        ):
            raise ValueError("Incomplete/non-cold physical timing")
        valid = [r for r in rows if r["score"] is not None]
        rate = 1 - len(valid) / len(rows)
        auc = (
            float(roc_auc_score([r["label"] for r in valid], [r["score"] for r in valid]))
            if len({r["label"] for r in valid}) == 2
            else None
        )
        candidates[name] = {
            "pooled_oof_auroc": auc,
            "invalid_rate": rate,
            "eligible": rate <= 0.05 and auc is not None,
            "gpu_seconds_per_trajectory": seconds,
            "folds": [
                {"fold": f, "n": sum(folds[r["task_id"]] == f for r in rows)} for f in range(5)
            ],
        }
    eligible = [name for name, c in candidates.items() if c["eligible"]]
    selected = (
        min(
            eligible,
            key=lambda name: (
                -candidates[name]["pooled_oof_auroc"],
                candidates[name]["gpu_seconds_per_trajectory"],
                digest(name),
            ),
        )
        if eligible
        else None
    )
    result = {
        "identity": digest(identity),
        "selected": selected,
        "candidates": candidates,
        "task_folds": folds,
        "sources": sources,
        "timing_sha256": file_hash(measurements),
        "supplementary_counts": supplementary,
        "definition": "Predetermined policies; no fitting to fold validation records. "
        "Pool each task's held-fold scores once; folds are not independent experiments.",
        "all_eight_conditions_required": True,
    }
    atomic_json(output, result)
    return {"selected": selected, "output": str(output)}
