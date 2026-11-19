"""Aggregate stage diagnostics over archived EaE quotations and MRT summary states."""

import json
from bisect import bisect_right
from collections import Counter, defaultdict
from statistics import mean

from agent_safety_monitoring.analysis.diagnosis import extraction_diagnostics, terminal_branches
from agent_safety_monitoring.inference.backend import ModelConfig, Tokenizer
from agent_safety_monitoring.io import atomic_json, file_hash, read_json
from agent_safety_monitoring.reporting.report import load_results


def summarize_evidence(data, run, freeze_path, score_analysis, output):
    freeze = read_json(freeze_path)
    tokenizer = Tokenizer(ModelConfig.model_validate(freeze["body"]["config"]["model"]))
    tables = load_results(run)
    extracted = {p["trajectory_id"]: p for p in extraction_diagnostics(tables, data)}
    features = {f["trajectory_id"]: f for f in read_json(data / "audit.json")["features"]}
    analysis = read_json(score_analysis)
    bounds = [b["upper_exclusive"] for b in analysis["length"]["bins"][:-1]]
    eae = defaultdict(list)
    mrt = defaultdict(list)
    for method, rows in tables["test"].items():
        kind = method.split("-", 1)[0]
        if kind not in ("mrt", "eae"):
            continue
        for row in rows:
            uid = row["trajectory_id"]
            group = "attack" if row["label"] else "benign"
            strata = [
                "all",
                group,
                f"length-bin-{bisect_right(bounds, features[uid]['source_tokens'])}",
            ]
            if row["objective"]:
                strata.append(row["objective"])
            saved = row["result"]
            failures = Counter(a["category"] for a in saved.artifacts if "invalid_attempt" in a)
            if kind == "eae":
                selection = next(
                    (
                        a["output"]["quotes"]
                        for a in saved.artifacts
                        if a["stage"] == "extract" and "output" in a
                    ),
                    None,
                )
                d = extracted[uid]
                item = {
                    "extracted": selection is not None,
                    "quote_tokens": sum(tokenizer.count(q["text"]) for q in selection or []),
                    "quotes": d["quotes"],
                    "out_of_order": d["out_of_source_order"],
                    "unpaired_calls": d["selected_tool_calls"] - d["linked_call_result_ids"],
                    "unpaired_results": d["selected_tool_results"] - d["linked_call_result_ids"],
                    "relative_positions": d["relative_positions"],
                    "invalid": saved.status != "valid",
                    "failures": failures,
                }
                for name in strata:
                    eae[name].append(item)
                continue

            seq, tree, stages, chunks = terminal_branches(saved)
            sequential = [
                stages[f"sequential-{i}"] for i in range(chunks) if f"sequential-{i}" in stages
            ]
            prior = {c for stage in sequential[:-1] for c in stage["citations"]}
            leaf = {
                c
                for name, stage in stages.items()
                if name.startswith("leaf-")
                for c in stage["citations"]
            }
            terminal = [seq, tree]
            chunk_rows = next(a["chunks"] for a in saved.artifacts if a["stage"] == "chunking")
            call_parts = defaultdict(lambda: defaultdict(set))
            for segment in (segment for chunk in chunk_rows for segment in chunk):
                call_id = segment["tool_call_id"]
                if call_id is not None:
                    call_parts[call_id][segment["kind"]].add(segment["id"])
            source_pairs = [
                (part["tool_call"], part["tool_result"])
                for part in call_parts.values()
                if part["tool_call"] and part["tool_result"]
            ]
            citations = [set(s["citations"]) if s else set() for s in terminal]
            item = {
                "scores": [s["score"] if s else None for s in terminal],
                "prior_seq_citations_missing": len(prior - set(seq["citations"])) if seq else None,
                "leaf_citations_missing": len(leaf - set(tree["citations"])) if tree else None,
                "size": [
                    tokenizer.count(json.dumps(s, ensure_ascii=False)) for s in stages.values()
                ],
                "failures": failures,
                "source_tool_pairs": len(source_pairs),
                "terminal_jointly_cited_tool_pairs": [
                    sum(bool(c & left) and bool(c & right) for left, right in source_pairs)
                    for c in citations
                ],
            }
            for name in strata:
                mrt[name].append(item)

    quote_budget = next(
        m["quote_tokens"] for m in freeze["body"]["config"]["methods"] if m["method"] == "eae"
    )
    summary_budget = next(
        m["summary_tokens"] for m in freeze["body"]["config"]["methods"] if m["method"] == "mrt"
    )
    eae_results, mrt_results = {}, {}
    for name, rows in eae.items():
        selected = [r for r in rows if r["extracted"]]
        positions = Counter(min(3, int(p * 4)) for r in selected for p in r["relative_positions"])
        eae_results[name] = {
            "records": len(rows),
            "failed_extraction": len(rows) - len(selected),
            "successful_empty": sum(r["quotes"] == 0 for r in selected),
            "invalid": sum(r["invalid"] for r in rows),
            "mean_quote_tokens_per_accepted_extraction": (
                mean(r["quote_tokens"] for r in selected) if selected else None
            ),
            "mean_quote_count_per_accepted_extraction": (
                mean(r["quotes"] for r in selected) if selected else None
            ),
            "records_with_out_of_order_quotes": sum(r["out_of_order"] for r in selected),
            "records_with_unpaired_calls": sum(r["unpaired_calls"] > 0 for r in selected),
            "records_with_unpaired_results": sum(r["unpaired_results"] > 0 for r in selected),
            "quotation_position_quartiles": [positions[q] for q in range(4)],
            "invalid_attempt_categories": dict(sum((r["failures"] for r in rows), Counter())),
        }
    for name, rows in mrt.items():
        sizes = [n for r in rows for n in r["size"]]
        mrt_results[name] = {
            "records": len(rows),
            "branch_disagreements": sum(a != b for a, b in (r["scores"] for r in rows)),
            "terminal_score_counts": [
                dict(Counter(str(r["scores"][i]) for r in rows)) for i in range(2)
            ],
            "records_with_sequential_citation_loss": sum(
                bool(r["prior_seq_citations_missing"]) for r in rows
            ),
            "records_with_hierarchical_citation_loss": sum(
                bool(r["leaf_citations_missing"]) for r in rows
            ),
            "accepted_states": len(sizes),
            "states_above_90_percent_budget": sum(n > 0.9 * summary_budget for n in sizes),
            "mean_accepted_state_tokens": mean(sizes) if sizes else None,
            "source_tool_pairs": sum(r["source_tool_pairs"] for r in rows),
            "terminal_jointly_cited_tool_pairs": [
                sum(r["terminal_jointly_cited_tool_pairs"][i] for r in rows) for i in range(2)
            ],
            "invalid_attempt_categories": dict(sum((r["failures"] for r in rows), Counter())),
        }
    result = {
        "original_freeze": freeze["hash"],
        "scoring_aggregate_sha256": file_hash(score_analysis),
        "tokenizer_revision": tokenizer.tokenizer.init_kwargs.get("_commit_hash")
        or freeze["body"]["config"]["model"]["tokenizer_revision"],
        "quote_budget_tokens": quote_budget,
        "summary_budget_tokens": summary_budget,
        "eae": eae_results,
        "mrt": mrt_results,
        "interpretation": "Citation retention and quotation overlap measure structure only.",
    }
    atomic_json(output, result)
    return result
