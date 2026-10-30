"""Private development-only replay of saved EaE validation, without inference."""

from collections import Counter
from pathlib import Path

from agent_safety_monitoring.inference.backend import ModelConfig, Tokenizer
from agent_safety_monitoring.io import atomic_json, read_json
from agent_safety_monitoring.monitors.core import (
    failure_category,
    passage_table,
    resolve_passages,
    resolve_quotes,
    validate_quotes,
)
from agent_safety_monitoring.schema import (
    CanonicalTrajectory,
    EvidenceSelection,
    Extraction,
    PassageSelection,
)


def diagnose(root: Path, data: Path, output: Path):
    study = read_json(root / "study.json")
    tokenizer = Tokenizer(ModelConfig.model_validate(study["configuration"]["model"]))
    records = {r["trajectory_id"]: r for r in read_json(data / "manifest.json")["records"]}
    configs = {m["method"]: m for m in study["configuration"]["methods"]}
    rows, final, attempts = [], Counter(), Counter()
    for path in sorted((root / "development").glob("eae-*/*.json")):
        saved = read_json(path)
        uid = saved["result"]["trajectory_id"]
        if records[uid]["split"] != "development" or saved["evaluation"]["split"] != "development":
            raise ValueError("Diagnosis is restricted to development records")
        trajectory = CanonicalTrajectory.model_validate(
            read_json(data / "trajectories" / f"{uid}.json")
        )
        budget = configs["eae"].get("quote_tokens", 1000)
        failures = []
        for call in saved["result"]["calls"]:
            if call["stage"] != "extract":
                continue
            detail, category, total = None, None, None
            try:
                if call["error"]:
                    category = "transport_server"
                elif call["finish_reason"] not in {None, "stop"}:
                    category = "truncation"
                else:
                    import json

                    obj = json.loads(call["response"])
                    if "passage_ids" in obj:
                        selection = PassageSelection.model_validate(obj)
                        table = passage_table(trajectory, tokenizer)
                        resolved = resolve_passages(selection, table, trajectory, tokenizer, 10**12)
                    elif obj.get("quotes") and "start" in obj["quotes"][0]:
                        resolved = Extraction.model_validate(obj)
                        validate_quotes(resolved, trajectory, tokenizer, 10**12)
                    else:
                        selection = EvidenceSelection.model_validate(obj)
                        resolved = resolve_quotes(selection, trajectory, tokenizer, 10**12)
                    total = sum(tokenizer.count(q.text) for q in resolved.quotes)
                    if total > budget:
                        category, detail = "quotation_budget", f"selected={total}, limit={budget}"
            except Exception as exc:
                from pydantic import ValidationError

                category = (
                    "schema"
                    if isinstance(exc, (ValidationError, ValueError))
                    and (isinstance(exc, ValidationError) or "JSON" in type(exc).__name__)
                    else failure_category(exc)
                )
                detail = type(exc).__name__  # raw Pydantic messages can include source text
            if category:
                attempts[category] += 1
                failures.append({"category": category, "detail": detail, "selected_tokens": total})
        result = saved["result"]
        last = failures[-1]["category"] if failures else result["status"]
        if result["status"] != "valid":
            if result["status"] == "context_overflow":
                last = "context_overflow"
            elif result["error"] and result["error"].startswith("judge:"):
                last = "citation_or_judge_validation"
            final[last] += 1
        rows.append(
            {
                "trajectory_id": uid,
                "status": result["status"],
                "final_category": last,
                "failed_attempts": failures,
            }
        )
    report = {
        "run_identity": study["identity"],
        "records": rows,
        "final_failure_categories": dict(final),
        "attempt_failure_categories": dict(attempts),
    }
    atomic_json(output, report)
    return {
        "records": len(rows),
        "final_failure_categories": dict(final),
        "attempt_failure_categories": dict(attempts),
        "private_output": str(output),
    }
