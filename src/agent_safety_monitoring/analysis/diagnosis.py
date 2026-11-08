"""Read-only frozen-run forensics; publish aggregates, keep diagnostic rows private."""

from collections import Counter

import numpy as np

from agent_safety_monitoring.analysis.audit import audit, validate_pairs
from agent_safety_monitoring.analysis.operating_points import comparison
from agent_safety_monitoring.evaluation.metrics import metrics, paired_bootstrap
from agent_safety_monitoring.experiments.resources import allocation_usage
from agent_safety_monitoring.io import atomic_json, file_hash, read_json
from agent_safety_monitoring.reporting.report import load_results


def terminal_branches(result):
    chunking = [a for a in result.artifacts if a["stage"] == "chunking"]
    if len(chunking) != 1:
        raise ValueError("One saved chunking artifact required")
    n = len(chunking[0]["chunks"])
    if not n:
        raise ValueError("Empty chunking")
    accepted = {}
    for a in result.artifacts:
        if "output" in a:
            if a["stage"] in accepted:
                raise ValueError("Duplicate accepted stage")
            accepted[a["stage"]] = a["output"]
    sequential = accepted.get(f"sequential-{n - 1}")
    if any(f"sequential-{i}" not in accepted for i in range(n)):
        sequential = None
    level = [accepted.get(f"leaf-{i}") for i in range(n)]
    depth = 0
    while len(level) > 1:
        level = [
            level[i]
            if i + 1 == len(level)
            else accepted.get(f"merge-{depth}-{i // 2}")
            if level[i] is not None and level[i + 1] is not None
            else None
            for i in range(0, len(level), 2)
        ]
        depth += 1
    hierarchical = level[0]
    if result.status == "valid" and (
        sequential is None
        or hierarchical is None
        or not np.isclose(result.score, (sequential["score"] + hierarchical["score"]) / 2)
    ):
        raise ValueError("Reconstructed branches disagree with frozen hybrid")
    return sequential, hierarchical, accepted, n


def branch_tables(tables):
    output = {s: {"sequential": [], "hierarchical": []} for s in tables}
    diagnostics = []
    for split, methods in tables.items():
        name = next(n for n in methods if n.startswith("mrt-"))
        for row in methods[name]:
            seq, tree, stages, chunks = terminal_branches(row["result"])
            for branch, terminal in [("sequential", seq), ("hierarchical", tree)]:
                output[split][branch].append(
                    {**row, "score": terminal["score"] if terminal else None}
                )
            if split == "test":
                seqs = [
                    stages[f"sequential-{i}"] for i in range(chunks) if f"sequential-{i}" in stages
                ]
                diagnostics.append(
                    {
                        "trajectory_id": row["trajectory_id"],
                        "task_id": row["task_id"],
                        "label": row["label"],
                        "chunks": chunks,
                        "sequential_scores": [s["score"] for s in seqs],
                        "sequential_terminal": seq["score"] if seq else None,
                        "hierarchical_terminal": tree["score"] if tree else None,
                        "earlier_citations_missing_final": len(
                            set(c for s in seqs[:-1] for c in s["citations"])
                            - set(seq["citations"] if seq else [])
                        ),
                        "invalid_attempt_categories": [
                            a["category"] for a in row["result"].artifacts if "invalid_attempt" in a
                        ],
                    }
                )
    return output, diagnostics


def tie_summary(rows):
    b = Counter(r["score"] for r in rows if not r["label"] and r["score"] is not None)
    a = Counter(r["score"] for r in rows if r["label"] and r["score"] is not None)
    pairs = sum(a.values()) * sum(b.values())
    tied = sum(n * b[s] for s, n in a.items())
    return {
        "valid_cross_class_pairs": pairs,
        "tied_pairs": tied,
        "tie_fraction": tied / pairs if pairs else None,
        "auc_contribution_from_ties": 0.5 * tied / pairs if pairs else None,
        "histograms": {
            str(c): dict(Counter(str(r["score"]) for r in rows if r["label"] == c)) for c in [0, 1]
        },
    }


def extraction_diagnostics(tables, data):
    name = next(n for n in tables["test"] if n.startswith("eae-"))
    rows = []
    for r in tables["test"][name]:
        t = read_json(data / "trajectories" / f"{r['trajectory_id']}.json")
        steps = {s["id"]: s for s in t["segments"]}
        order = {s["id"]: i for i, s in enumerate(t["segments"])}
        extracts = [
            a["output"]["quotes"]
            for a in r["result"].artifacts
            if a["stage"] == "extract" and "output" in a
        ]
        if len(extracts) > 1:
            raise ValueError("Duplicate accepted extraction")
        quotes = extracts[0] if extracts else []
        for q in quotes:
            if steps[q["step"]]["text"][q["start"] : q["end"]] != q["text"]:
                raise ValueError("Saved quote does not match canonical source")
        positions = [(order[q["step"]], q["start"]) for q in quotes]
        selected = {q["step"] for q in quotes}
        calls = {
            s["tool_call_id"]
            for s in t["segments"]
            if s["kind"] == "tool_call" and s["id"] in selected
        }
        results = {
            s["tool_call_id"]
            for s in t["segments"]
            if s["kind"] == "tool_result" and s["id"] in selected
        }
        rows.append(
            {
                "trajectory_id": r["trajectory_id"],
                "label": r["label"],
                "quotes": len(quotes),
                "out_of_source_order": positions != sorted(positions),
                "selected_chars": sum(len(q["text"]) for q in quotes),
                "selected_tool_calls": len(calls),
                "selected_tool_results": len(results),
                "linked_call_result_ids": len((calls & results) - {None}),
                "relative_positions": [p[0] / max(1, len(steps) - 1) for p in positions],
                "score": r["score"],
            }
        )
    return rows


def run_diagnosis(freeze, repository, data, run_root, sacct, output, replicates=2000):
    checked = audit(freeze, repository, data, output / "artifact-audit.json", run_root)
    if not checked["integrity_passed"]:
        raise ValueError("Frozen integrity audit failed")
    tables = load_results(run_root)
    validate_pairs(tables)
    result = comparison(tables["calibration"], tables["test"], replicates)
    # Independently reconcile every original scalar and interval, not only rounded prose.
    legacy = paired_bootstrap(tables["calibration"], tables["test"], replicates)
    reconciliation = {}
    for name in tables["test"]:
        old = metrics([r["score"] for r in tables["calibration"][name]], tables["test"][name])
        new = result["point"][name]
        reconciliation[name] = {
            "points_match": all(
                np.isclose(old[k], new[k], atol=1e-12) for k in ["tpr", "fpr", "auroc_valid"]
            ),
            "tpr_interval_matches": bool(
                np.allclose(
                    result["intervals"][name]["tpr"]["ci95"],
                    legacy["tpr_intervals"][name],
                    atol=1e-12,
                )
            ),
            "fpr_interval_matches": bool(
                np.allclose(
                    result["intervals"][name]["fpr"]["ci95"],
                    legacy["additional_intervals"][name]["fpr"],
                    atol=1e-12,
                )
            ),
            "auroc_interval_matches": bool(
                np.allclose(
                    result["intervals"][name]["auroc_valid"]["ci95"],
                    legacy["additional_intervals"][name]["auroc_valid"],
                    atol=1e-12,
                )
            ),
            "original": old,
            "deterministic": metrics(
                [r["score"] for r in tables["calibration"][name]],
                tables["test"][name],
                deterministic=True,
            ),
        }
    saved_report = repository / "runs/full-study/report/metrics.json"
    saved = read_json(saved_report)
    for name, r in reconciliation.items():
        r["saved_primary_matches"] = saved["methods"][name]["primary"] == r["original"]
        r["saved_tpr_interval_matches"] = bool(
            np.allclose(
                legacy["tpr_intervals"][name],
                saved["uncertainty"]["tpr_intervals"][name],
                atol=1e-12,
            )
        )
        r["saved_fpr_auroc_intervals_match"] = all(
            np.allclose(
                legacy["additional_intervals"][name][key],
                saved["uncertainty"]["additional_intervals"][name][key],
                atol=1e-12,
            )
            for key in ["fpr", "auroc_valid"]
        )
    branches, private_mrt = branch_tables(tables)
    all_cal = {**tables["calibration"], **branches["calibration"]}
    all_test = {**tables["test"], **branches["test"]}
    branch_comparison = comparison(all_cal, all_test, replicates)
    common_ids = set.intersection(
        *[
            {r["trajectory_id"] for r in rows if r["score"] is not None}
            for rows in tables["test"].values()
        ]
    )
    common_valid = comparison(
        tables["calibration"],
        {
            n: [r for r in rows if r["trajectory_id"] in common_ids]
            for n, rows in tables["test"].items()
        },
        replicates,
    )
    eae = extraction_diagnostics(tables, data)
    manifest = read_json(data / "manifest.json")
    raw_hashes = {}
    for name, expected in manifest["sources"].items():
        candidates = list((repository / "data/raw").rglob(name))
        raw_hashes[name] = file_hash(candidates[0]) == expected if len(candidates) == 1 else None
    accounting = allocation_usage(sacct.read_text())
    provenance = {
        "freeze": read_json(freeze)["hash"],
        "study_sha256": file_hash(run_root / "study.json"),
        "sacct_sha256": file_hash(sacct),
        "raw_source_hashes_match": raw_hashes,
        "status": "post-hoc analysis of frozen predictions; no new inference",
    }
    summary = {
        **provenance,
        "operating_points": result,
        "reconciliation": reconciliation,
        "branches": branch_comparison,
        "common_valid_sensitivity": {
            "n": len(common_ids),
            "comparison": common_valid,
            "interpretation": "Conditional common-valid test population; not deployment rates.",
        },
        "allocation": accounting,
        "ties": {n: tie_summary(rows) for n, rows in tables["test"].items()},
        "eae": {
            str(c): {
                "n": len([r for r in eae if r["label"] == c]),
                "empty_quotes": sum(r["quotes"] == 0 for r in eae if r["label"] == c),
                "out_of_source_order": sum(
                    r["out_of_source_order"] for r in eae if r["label"] == c
                ),
                "selected_call_without_result": sum(
                    r["selected_tool_calls"] > r["linked_call_result_ids"]
                    for r in eae
                    if r["label"] == c
                ),
                "mean_quotes": float(np.mean([r["quotes"] for r in eae if r["label"] == c])),
            }
            for c in [0, 1]
        },
        "mrt": {
            "n": len(private_mrt),
            "branch_disagreement": sum(
                r["sequential_terminal"] != r["hierarchical_terminal"] for r in private_mrt
            ),
            "sequential_score_decreased": sum(
                any(
                    b < a
                    for a, b in zip(
                        r["sequential_scores"], r["sequential_scores"][1:], strict=False
                    )
                )
                for r in private_mrt
            ),
            "earlier_citation_missing_final": sum(
                r["earlier_citations_missing_final"] > 0 for r in private_mrt
            ),
            "invalid_attempt_categories": dict(
                Counter(c for r in private_mrt for c in r["invalid_attempt_categories"])
            ),
        },
    }
    atomic_json(output / "diagnosis-private.json", {"mrt": private_mrt, "eae": eae})
    atomic_json(output / "diagnosis-aggregate.json", summary)
    return summary
