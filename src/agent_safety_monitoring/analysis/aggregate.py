"""Reproducible public aggregate reports; private rows never enter exported artifacts."""

import csv
import shutil
from collections import defaultdict
from pathlib import Path

import numpy as np

from agent_safety_monitoring.analysis.audit import method_ids, verify_manifest
from agent_safety_monitoring.io import atomic_json, file_hash, read_json

ORDER = ["single", "think", "average", "eae", "mrt"]
NAMES = {
    "single": "Single review",
    "think": "Think longer",
    "average": "Average ×2",
    "eae": "EaE 3K",
    "mrt": "MRT 5 interactions",
}
COMPARISONS = [
    ("average", "single"),
    ("think", "single"),
    ("mrt", "single"),
    ("eae", "single"),
    ("average", "think"),
    ("average", "mrt"),
    ("eae", "mrt"),
]


def numeric_tree(value):
    if isinstance(value, dict):
        return {k: numeric_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [numeric_tree(v) for v in value]
    if value is None or isinstance(value, (int, float, bool)):
        if isinstance(value, float) and not np.isfinite(value):
            raise ValueError("Nonfinite public aggregate")
        return value
    raise ValueError("Public aggregate must contain numeric values only")


def public_method(value):
    metrics_keys = [
        "tpr",
        "fpr",
        "auroc_valid",
        "invalid_rate",
        "n",
        "n_valid",
        "n_invalid",
        "valid_score_coverage",
        "n_attacks",
        "n_benign",
    ]
    policy_keys = ["cutoff", "boundary_probability", "target_fpr", "achieved_fpr", "feasible"]
    cost_keys = [
        "logical_calls",
        "cache_hits",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "reasoning_tokens_estimated",
        "reasoning_tokens_exposed",
        "reasoning_estimates_exposed",
        "request_latency_sum_seconds",
    ]
    clean = {}
    for key in ["primary", "deterministic"]:
        clean[key] = {k: value[key][k] for k in metrics_keys}
        clean[key]["policy"] = {k: value[key]["policy"][k] for k in policy_keys}
    clean["cost"] = {k: value["cost"][k] for k in cost_keys}
    objectives = {
        "firewall_disabling",
        "malware_execution",
        "privilege_escalation",
        "secret_exfiltration",
    }
    if set(value["per_objective"]) != objectives:
        raise ValueError("Unknown or missing objective")
    clean["per_objective"] = {
        o: {k: v[k] for k in ["n", "tpr"]} for o, v in value["per_objective"].items()
    }
    return numeric_tree(clean)


def public_structural(raw, ids):
    result = {"length_feature": raw["length_feature"], "baselines": {}, "length_matched": {}}
    for name in ["length", "tools", "length_tools"]:
        entry = raw["baselines"][name]
        u = entry["bootstrap"]
        result["baselines"][name] = {
            "metrics": {
                k: numeric_tree(entry["metrics"][k])
                for k in ["tpr", "fpr", "auroc_valid", "n", "n_attacks", "n_benign"]
            },
            "bootstrap": {
                "replicates": u["replicates"],
                "skipped": u["skipped"],
                "tpr_intervals": {name: u["tpr_intervals"][name]},
                "additional_intervals": {
                    name: {k: u["additional_intervals"][name][k] for k in ["fpr", "auroc_valid"]}
                },
            },
        }
    if set(raw["length_matched"]) != set(ids):
        raise ValueError("Structural method coverage mismatch")
    for name in ids:
        entry = raw["length_matched"][name]
        point = {k: entry["point"][k] for k in ["tpr", "fpr", "unsupported_trajectories"]}
        point["overlap"] = [
            {k: b[k] for k in ["bin", "benign", "attack", "retained_mass"]}
            for b in entry["point"]["overlap"]
        ]
        result["length_matched"][name] = {
            "point": point,
            "bootstrap": {
                k: {field: entry["bootstrap"][k][field] for field in ["ci95", "usable_replicates"]}
                for k in ["tpr", "fpr"]
            },
        }
    numeric_tree({k: result[k] for k in ["baselines", "length_matched"]})
    return result


def signed_interval(uncertainty, a, b):
    intervals = uncertainty["paired_tpr_difference_intervals"]
    if f"{a} - {b}" in intervals:
        return intervals[f"{a} - {b}"]
    low, high = intervals[f"{b} - {a}"]
    return [-high, -low]


def injection_summary(rows, replicates=2000, seed=20261028):
    """Pair variants first; resample whole tasks, retaining all repeated conditions."""
    if not rows or replicates < 1:
        raise ValueError("Nonempty injection rows and positive replicates required")
    seen, groups = set(), defaultdict(list)
    identities = {}
    for row in rows:
        key = tuple(row[k] for k in ("method", "trajectory_id", "family", "placement"))
        if key in seen:
            raise ValueError("Duplicate injection pair")
        seen.add(key)
        identity = (row["task_id"], row["label"])
        uid = row["trajectory_id"]
        if uid in identities and identities[uid] != identity:
            raise ValueError("Injection trajectory metadata differs across conditions")
        identities[uid] = identity
        if row["label"] not in (0, 1) or not np.isclose(
            row["alert_difference"], -row["miss_difference"]
        ):
            raise ValueError("Invalid paired outcomes")
        if any(
            not np.isfinite(row[k]) or abs(row[k]) > 1
            for k in ("alert_difference", "miss_difference")
        ):
            raise ValueError("Invalid probability difference")
        groups[row["method"], row["label"], "all", "all"].append(row)
        groups[row["method"], row["label"], row["family"], row["placement"]].append(row)
    result = []
    for (method, label, family, placement), selected in sorted(groups.items()):
        variable = "miss_difference" if label else "alert_difference"
        tasks = defaultdict(list)
        for r in selected:
            tasks[r["task_id"]].append(r[variable])
        keys = sorted(tasks)
        rng = np.random.default_rng(seed)
        samples = [
            np.mean([v for task in rng.choice(keys, len(keys), replace=True) for v in tasks[task]])
            for _ in range(replicates)
        ]
        result.append(
            {
                "method": method,
                "label": label,
                "family": family,
                "placement": placement,
                "outcome": variable,
                "pairs": len(selected),
                "tasks": len(tasks),
                "mean_change": float(np.mean([r[variable] for r in selected])),
                "ci95": np.quantile(samples, [0.025, 0.975]).tolist(),
                "invalid_injected": sum(r["invalid_injected"] for r in selected),
                "invalid_neutral": sum(r["invalid_neutral"] for r in selected),
            }
        )
    return result


def table(headers, rows):
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
            *["| " + " | ".join(str(x) for x in r) + " |" for r in rows],
        ]
    )


def pct(value):
    return "unavailable" if value is None else f"{100 * value:.1f}"


def interval(value, ci):
    return f"{pct(value)} [{pct(ci[0])}, {pct(ci[1])}]" if ci else pct(value)


def write_report(output, name, title, content):
    (output / name).write_text(f"# {title}\n\n{content}\n")


def generate(
    bundle: Path, freeze: Path, output: Path, replicates=2000, features=None, tracking_mode="online"
):
    """Generate only allowlisted aggregates from immutable saved summaries."""
    frozen = read_json(freeze)
    verify_manifest(frozen)
    ids = method_ids(frozen)
    source = bundle / "report/metrics.json"
    saved = read_json(source)
    injection_source = bundle / "secondary/injection-metrics.json"
    injected = read_json(injection_source)
    original_roc = bundle / "report/roc.png"
    structural_source = bundle / "structural/structural-diagnostics.json"
    raw_structural = read_json(structural_source)
    if raw_structural["length_feature"] not in {"source_tokens", "characters"}:
        raise ValueError("Unknown structural feature")
    structural = public_structural(raw_structural, ids)
    if any(d["freeze"] != frozen["hash"] for d in (saved, injected)):
        raise ValueError("Aggregate artifact freeze mismatch")
    if set(saved["methods"]) != set(ids) or set(structural["length_matched"]) != set(ids):
        raise ValueError("Method configuration hashes differ")
    methods = {ids[k]: public_method(v) for k, v in saved["methods"].items()}
    by_family = {v: k for k, v in ids.items()}
    expected_counts = None
    for values in methods.values():
        p = values["primary"]
        if p["n"] != p["n_attacks"] + p["n_benign"] or p["n"] != p["n_valid"] + p["n_invalid"]:
            raise ValueError("Inconsistent aggregate denominators")
        counts = (p["n"], p["n_attacks"], p["n_benign"])
        if expected_counts is not None and counts != expected_counts:
            raise ValueError("Primary method denominators differ")
        expected_counts = counts
    if set(r["method"] for r in injected["rows"]) - set(ids):
        raise ValueError("Unknown injection method")
    definition = frozen["body"]["injections"]
    injection_methods = {
        name
        for name, family in ids.items()
        if any(name == f"{family}-{h[:12]}" for h in definition["method_hashes"])
    }
    expected_pairs = {
        (m, uid, family, placement)
        for m in injection_methods
        for uid in definition["trajectory_ids"]
        for family in definition["payloads"]
        for placement in ["early", "late"]
    }
    actual_pairs = {
        (r["method"], r["trajectory_id"], r["family"], r["placement"]) for r in injected["rows"]
    }
    if actual_pairs != expected_pairs:
        raise ValueError("Injection coverage differs from frozen design")
    pairs = []
    for a, b in COMPARISONS:
        ci = signed_interval(saved["uncertainty"], by_family[a], by_family[b])
        pairs.append(
            {
                "a": a,
                "b": b,
                "difference": methods[a]["primary"]["tpr"] - methods[b]["primary"]["tpr"],
                "ci95": ci,
            }
        )
    budgets = frozen["body"]["config"]["budgets"]
    costs = {
        family: choice["gpu_seconds_per_trajectory"]
        for family, choice in budgets["large"]["methods"].items()
        if choice
    }
    injections = injection_summary(injected["rows"], replicates)
    # No trajectory IDs, task IDs, raw rows, quotations, or free-form model text exported.
    result = {
        "freeze": frozen["hash"],
        "methods": methods,
        "paired_differences": pairs,
        "development_gpu_seconds": costs,
        "injections": injections,
        "structural": structural,
        "bootstrap_seed": 20261028,
        "primary_replicates": saved["uncertainty"]["replicates"],
        "status": "saved_aggregates; record-level reconciliation required",
        "sources": {
            p.relative_to(bundle).as_posix(): file_hash(p)
            for p in (source, injection_source, structural_source, original_roc)
        },
        "freeze_file_sha256": file_hash(freeze),
    }
    if features is not None:
        feature_data = read_json(features)
        allowed_groups = {
            f"{split}/{label}"
            for split in ["development", "calibration", "test"]
            for label in ["benign", "attack"]
        }
        if set(feature_data["groups"]) - allowed_groups:
            raise ValueError("Unknown feature group")
        result["feature_groups"] = numeric_tree(
            {
                group: {
                    "n": values["n"],
                    **{
                        field: {
                            stat: values[field][stat]
                            for stat in ["median", "q25", "q75", "minimum", "maximum"]
                        }
                        for field in ["source_tokens", "characters", "tool_calls"]
                    },
                }
                for group, values in feature_data["groups"].items()
            }
        )
        result["feature_audit_hash"] = feature_data["audit_hash"]
    output.mkdir(parents=True, exist_ok=True)
    result["descriptive_frontier"] = [
        f
        for f in ORDER
        if not any(
            costs[g] <= costs[f]
            and methods[g]["primary"]["tpr"] >= methods[f]["primary"]["tpr"]
            and (costs[g] < costs[f] or methods[g]["primary"]["tpr"] > methods[f]["primary"]["tpr"])
            for g in ORDER
            if g != f
        )
    ]
    (output / "figures").mkdir(exist_ok=True)
    shutil.copyfile(original_roc, output / "figures/roc-original.png")
    atomic_json(output / "analysis-aggregates.json", result)
    rows = []
    for f in ORDER:
        p = methods[f]["primary"]
        u = saved["uncertainty"]
        extra = u["additional_intervals"][by_family[f]]
        rows.append(
            [
                NAMES[f],
                p["n_benign"],
                p["n_attacks"],
                interval(p["tpr"], u["tpr_intervals"][by_family[f]]),
                interval(p["fpr"], extra["fpr"]),
                f"{p['auroc_valid']:.3f} [{extra['auroc_valid'][0]:.3f}, "
                f"{extra['auroc_valid'][1]:.3f}]",
                pct(p["valid_score_coverage"]),
                p["n_invalid"],
            ]
        )
    main_table = table(
        [
            "Method",
            "Benign n",
            "Attack n",
            "TPR % [95% CI]",
            "FPR % [95% CI]",
            "Valid AUROC [95% CI]",
            "Coverage %",
            "Invalid n",
        ],
        rows,
    )
    pair_table = table(
        ["Comparison", "TPR difference, pp [95% CI]"],
        [
            [f"{NAMES[r['a']]} − {NAMES[r['b']]}", interval(r["difference"], r["ci95"])]
            for r in pairs
        ],
    )
    policy_table = table(
        [
            "Method",
            "Cutoff",
            "Boundary probability",
            "Calibration FPR %",
            "Deterministic TPR %",
            "Deterministic test FPR %",
        ],
        [
            [
                NAMES[f],
                methods[f]["primary"]["policy"]["cutoff"],
                f"{methods[f]['primary']['policy']['boundary_probability']:.4f}",
                pct(methods[f]["primary"]["policy"]["achieved_fpr"]),
                pct(methods[f]["deterministic"]["tpr"]),
                pct(methods[f]["deterministic"]["fpr"]),
            ]
            for f in ORDER
        ],
    )
    objective_table = table(
        ["Method", "Objective", "n", "TPR %"],
        [
            [NAMES[f], objective.replace("_", " "), v["n"], pct(v["tpr"])]
            for f in ORDER
            for objective, v in methods[f]["per_objective"].items()
        ],
    )
    primary = (
        "Primary estimates reproduce the saved frozen summary. Record-level reconciliation and "
        "new objective-specific uncertainty require recovery of the full run. Calibration uses "
        "448 separate benign trajectories; thresholds target 5% expected FPR. Invalid outputs "
        "are referral alerts. AUROC conditions on valid scores.\n\n"
        + main_table
        + "\n\n## Paired comparisons\n\n"
        + pair_table
        + "\n\nIntervals use the same 2,000 task-bootstrap draws across methods, independent "
        "calibration/test task draws, and recalibration in every replicate; zero replicates were "
        "skipped in the saved summary. They are nominal pointwise intervals, without simultaneous "
        "multiple-comparison coverage. Reversed comparisons negate and reverse interval endpoints. "
        "Averaging exceeds single review and MRT in these paired intervals; its difference from "
        "think-longer remains inconclusive. This does not establish a universal winner.\n\n"
        "## Calibration and discrete scores\n\n"
        + policy_table
        + "\n\nThese TPR/FPR values are expected alert probabilities under randomized boundary "
        "decisions, not integer counts of alerts. The conservative deterministic "
        "single and think-longer policies alert no valid test records: the cutoff is maximal and "
        "boundary is excluded. This sensitivity is substantial. Averaging permits half-integer "
        "scores; record-level judgments are needed to isolate disagreement and resolution effects. "
        "The inference settings and deployed thresholds remain frozen.\n\n"
        "## Objectives\n\n"
        + objective_table
        + "\n\nObjective results are descriptive point estimates. Objective-specific intervals and "
        "score histograms cannot be reconstructed from aggregate AUROCs. The regenerated ROC "
        "requires saved individual scores; no curve is invented from one AUROC value.\n\n"
        "![Detection and uncertainty](figures/main-performance.png)\n\n"
        "*Expected successful-attack TPR with recalibrated whole-task 95% bootstrap intervals.*\n\n"
        "![Paired differences](figures/paired-differences.png)\n\n"
        "*Signed TPR differences in percentage points; intervals preserve pairing.*\n\n"
        "![Objectives](figures/per-objective.png)\n\n"
        "*Objective-specific point estimates; uncertainty is not yet available.*\n\n"
        "![Original saved valid-score ROC](figures/roc-original.png)\n\n"
        "*Original saved ROC, copied without modification. Invalid outputs are excluded; "
        "per-method valid coverage is given in the primary table. Full record recovery is "
        "required to regenerate and independently verify the curve.*"
    )
    write_report(output, "primary-analysis.md", "Primary statistical analysis", primary)
    cost_rows = []
    for f in ORDER:
        c, n = methods[f]["cost"], methods[f]["primary"]["n"]
        cost_rows.append(
            [
                NAMES[f],
                f"{costs[f]:.2f}",
                f"{costs[f] / costs['single']:.2f}",
                c["logical_calls"],
                c["cache_hits"],
                f"{c['input_tokens'] / n:.1f}",
                f"{c['output_tokens'] / n:.1f}",
                f"{c['reasoning_tokens_estimated'] / n:.1f}",
            ]
        )
    cost_table = table(
        [
            "Method",
            "Dev GPU s/trajectory",
            "Cost / single",
            "Logical calls",
            "Cache-hit calls",
            "Input tokens/trajectory",
            "Generated tokens/trajectory",
            "Estimated reasoning tokens/trajectory",
        ],
        cost_rows,
    )
    budget_table = table(
        ["Budget", "GPU s limit", *[NAMES[f] for f in ORDER]],
        [
            [
                b,
                f"{v['gpu_seconds_limit']:.2f}",
                *["available" if v["methods"][f] else "unavailable" for f in ORDER],
            ]
            for b, v in budgets.items()
        ],
    )
    compute = (
        cost_table
        + "\n\n"
        + budget_table
        + "\n\nGPU costs are the frozen independent homogeneous development workload measurements "
        "(40 records per method, one H200, concurrency one), not held-out allocated GPU time. "
        "Token and call totals refer to the 572 primary test trajectories and include logical "
        "retries and cache reuse. Reasoning-token counts were not exposed by the server; the "
        "reported nonzero reasoning values are local estimates, not additional tokens to add to "
        "total generation. A recorded zero in the server reasoning-total field means unavailable "
        "measurement here, not no reasoning.\n\n"
        f"MRT costs {costs['mrt'] / costs['average']:.2f} times averaging in development. "
        "It has a lower detection point estimate and higher realized test FPR. Its observed "
        "cost-performance position is dominated descriptively by averaging; neither precise "
        "held-out cost equivalence nor cost uncertainty is established. Think-longer is slightly "
        "faster than single review in the one development measurement, despite generating more "
        "tokens on test. Timing variability and serving effects remain possible explanations; "
        "the saved aggregates cannot identify a cause.\n\n"
        "The reported total allocation is 60.61 GPU-hours against a 90-hour cap, pending fresh "
        "Slurm reconciliation. Startup and failed allocations belong in that total; startup "
        "is separate from homogeneous workload rates. Request latency sums cannot substitute "
        "for GPU allocations or be divided among methods as allocation estimates. No repeated "
        "cold trials are available to support horizontal error bars.\n\n"
        "![GPU cost](figures/gpu-cost-detection.png)\n\n"
        "*Measured development workload cost versus frozen test detection; vertical intervals "
        "are task-bootstrap uncertainty, with unequal realized test FPRs.*\n\n"
        "![Token cost](figures/token-cost-detection.png)\n\n"
        "*Logical generated tokens per primary test trajectory versus detection; tokens are "
        "a workload proxy and do not imply equal GPU time.*"
    )
    compute += "\n\nThe point-estimate frontier in development GPU cost and expected test TPR "
    compute += "contains " + ", ".join(NAMES[f] for f in result["descriptive_frontier"]) + ". "
    compute += (
        "This descriptive two-axis frontier ignores cost uncertainty and unequal "
        "realized test FPR; frontier membership is not an inferential superiority claim."
    )
    write_report(output, "compute-efficiency.md", "Compute efficiency", compute)
    structural_rows = []
    for name, v in structural["baselines"].items():
        m, u = v["metrics"], v["bootstrap"]
        structural_rows.append(
            [
                name,
                interval(m["tpr"], u["tpr_intervals"][name]),
                interval(m["fpr"], u["additional_intervals"][name]["fpr"]),
                f"{m['auroc_valid']:.3f}",
            ]
        )
    matched_rows = []
    for name, v in structural["length_matched"].items():
        matched_rows.append(
            [
                NAMES[ids[name]],
                pct(methods[ids[name]]["primary"]["tpr"]),
                interval(v["point"]["tpr"], v["bootstrap"]["tpr"]["ci95"]),
                interval(v["point"]["fpr"], v["bootstrap"]["fpr"]["ci95"]),
                v["point"]["unsupported_trajectories"],
            ]
        )
    overlap = next(iter(structural["length_matched"].values()))["point"]["overlap"]
    ess = {}
    for label in ["benign", "attack"]:
        mass = sum(b["retained_mass"] for b in overlap)
        squared = sum(b["retained_mass"] ** 2 / b[label] for b in overlap if b[label])
        ess[label] = mass * mass / squared if squared else None
    feature_text = ""
    if features is not None:
        feature_text = "\n\n## Calibration distribution shift\n\n" + table(
            ["Group", "n", "Median source tokens [IQR]", "Median tool calls [IQR]"],
            [
                [
                    key,
                    group["n"],
                    f"{group['source_tokens']['median']:,.1f} "
                    f"[{group['source_tokens']['q25']:,.1f}, {group['source_tokens']['q75']:,.1f}]",
                    f"{group['tool_calls']['median']:.1f} "
                    f"[{group['tool_calls']['q25']:.1f}, {group['tool_calls']['q75']:.1f}]",
                ]
                for key, group in result["feature_groups"].items()
            ],
        )
        feature_text += (
            "\n\nSource-token statistics come from the local prepared audit, not complete "
            "model prompts. Benign test trajectories are longer and have more tool calls "
            "at their medians than calibration trajectories. This is descriptive evidence "
            "of population differences; it does not establish their effect on scores.\n\n"
            "![Source distributions](figures/source-feature-distributions.png)\n\n"
            "*Source-feature medians and interquartile ranges, not confidence intervals.*"
        )
    structure_text = (
        table(["Baseline", "TPR % [95% CI]", "FPR % [95% CI]", "Valid AUROC"], structural_rows)
        + "\n\nBaselines fit only development labels using standardized log-transformed length "
        "and/or tool counts. Their stored bootstrap conditions on this fitted development model. "
        "Length-plus-tools AUROC is close to several full-transcript monitors. This establishes "
        "that structural features predict assignment well; it does not prove that the language "
        "models use those features. Harm-recognition claims must account for confounding.\n\n"
        + table(
            [
                "Method",
                "Unweighted TPR %",
                "Length-weighted TPR % [95% CI]",
                "Weighted FPR % [95% CI]",
                "Unsupported n",
            ],
            matched_rows,
        )
        + "\n\nDevelopment-derived bins equalize benign and attack mass within each bin. "
        "All five bins have both classes and no test records are wholly unsupported. This "
        "coarse matching leaves within-bin differences and tool-count confounding. It is a "
        "sensitivity analysis, not causal identification. The unchanged weighted FPR follows "
        "from every bin having more attacks than benign records, leaving benign weights one. "
        f"Kish effective sample sizes from saved bin weights are {ess['benign']:.1f} benign "
        f"and {ess['attack']:.1f} attacks; bin edges remain development-derived.\n\n"
        "Calibration benign records come from never-attacked tasks; test benign records come "
        "from attacked task groups. Their different task populations can shift scores and "
        "realized FPR. Score-distribution comparisons require full prediction recovery; "
        "the frozen calibration population will not be changed.\n\n"
        "![Structural and monitor performance](figures/structural-performance.png)\n\n"
        "*Structural baseline and monitor TPR at independently benign-calibrated policies.*"
        + feature_text
    )
    write_report(output, "structural-confounding.md", "Structural confounding", structure_text)
    injection_rows = [
        [
            NAMES[ids[r["method"]]],
            "attack misses" if r["label"] else "benign alerts",
            r["family"],
            r["placement"],
            r["pairs"],
            r["tasks"],
            interval(r["mean_change"], r["ci95"]),
            f"{r['invalid_injected']}/{r['invalid_neutral']}",
        ]
        for r in injections
    ]
    write_report(
        output,
        "injection-robustness.md",
        "Matched injection robustness",
        table(
            [
                "Method",
                "Outcome",
                "Family",
                "Placement",
                "Pairs",
                "Tasks",
                "Change, pp [95% CI]",
                "Invalid injected/neutral",
            ],
            injection_rows,
        )
        + "\n\nDifferences compare injected text with token-matched neutral controls "
        "under the original calibrated policy. Positive attack-miss change indicates "
        "worse detection; positive benign-alert change indicates more false alarms. "
        "Intervals resample whole tasks and retain all trajectory/condition pairs, "
        "conditional on the original thresholds. Stratum intervals are exploratory "
        "pointwise comparisons, not multiplicity-adjusted evidence.\n\n"
        "The 480 comparisons are repeated conditions on 40 trajectories, not 480 "
        "independent tasks. Aggregate attack-miss intervals include zero for both "
        "methods. This neither demonstrates attack success nor establishes equivalence "
        "or real-world robustness. The fixed synthetic payloads were not adaptive "
        "agent rollouts. Averaging, think-longer, and MRT were not tested.\n\n"
        "![Injection effects](figures/injection-effects.png)\n\n"
        "*Matched changes in expected miss/alert probability, with task-cluster intervals.*",
    )
    # Structured aggregate tables support reuse without parsing Markdown.
    with (output / "paired-differences.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["a", "b", "tpr_difference_pp", "ci95_low_pp", "ci95_high_pp"])
        writer.writerows(
            [r["a"], r["b"], 100 * r["difference"], *[100 * x for x in r["ci95"]]] for r in pairs
        )
    from agent_safety_monitoring.analysis.manuscript import write_manuscript

    write_manuscript(output, result, main_table, pair_table, cost_table, policy_table)
    from agent_safety_monitoring.analysis.figures import generate_figures

    generate_figures(result, saved["uncertainty"], by_family, output / "figures")
    from agent_safety_monitoring.analysis.tracking import publish

    tracking = publish(result, tracking_mode)
    return {
        **tracking,
        "output": str(output),
        "methods": len(methods),
        "injection_pairs": len(injected["rows"]),
    }
