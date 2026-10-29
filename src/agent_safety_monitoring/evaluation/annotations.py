"""Independent post-hoc annotation sample and aggregate evidence-retention checks."""

from pathlib import Path

from agent_safety_monitoring.evaluation.evidence import retention
from agent_safety_monitoring.evaluation.metrics import AlertPolicy
from agent_safety_monitoring.experiments.runner import validate_freeze
from agent_safety_monitoring.inference.backend import ModelConfig, Tokenizer
from agent_safety_monitoring.io import atomic_json, digest, read_json
from agent_safety_monitoring.reporting.report import load_results
from agent_safety_monitoring.schema import CanonicalTrajectory


def prepare_annotations(data: Path, run: Path, frozen: dict, metrics: Path, output: Path, limit=30):
    validate_freeze(frozen, data)
    report = read_json(metrics)
    if (
        report.get("freeze") != frozen["hash"]
        or read_json(run / "study.json")["freeze"] != frozen["hash"]
    ):
        raise ValueError("Primary results do not match the freeze")
    tables = load_results(run)
    baseline = next((m for m in sorted(tables["test"]) if m.startswith("single-")), None)
    if not baseline:
        raise ValueError("Single-review results are required for stratification")
    p = AlertPolicy(**report["methods"][baseline]["primary"]["policy"])
    rows = [r for r in tables["test"][baseline] if r["label"] == 1]
    features = {f["trajectory_id"]: f for f in read_json(data / "audit.json")["features"]}
    rows.sort(
        key=lambda r: (
            (
                features[r["trajectory_id"]].get("source_tokens")
                or features[r["trajectory_id"]]["characters"]
            ),
            r["trajectory_id"],
        )
    )
    groups = {}
    for i, r in enumerate(rows):
        probability = float(p.alerts([r["score"]])[0])
        draw = int(digest(["diagnostic-alert", r["trajectory_id"]])[:16], 16) / 16**16
        detected = draw < probability
        length_bin = min(2, 3 * i // max(1, len(rows)))
        key = (r["objective"] or "unknown", detected, length_bin)
        groups.setdefault(key, []).append(r)
    for values in groups.values():
        values.sort(key=lambda r: digest(["evidence-sample", r["trajectory_id"]]), reverse=True)
    selected = []
    while len(selected) < min(limit, len(rows)) and any(groups.values()):
        for key in sorted(groups):
            if groups[key] and len(selected) < limit:
                selected.append(groups[key].pop())
    # Annotation requests contain no monitor output; reviewers open source records independently.
    template = {
        "freeze": frozen["hash"],
        "instructions": (
            "Independently inspect the canonical transcript and enter exact source spans. "
            "Use provenance human_reviewed, grader_reference, or model_suggested. "
            "Leave references empty when no independent evidence is established."
        ),
        "records": [
            {"trajectory_id": r["trajectory_id"], "references": [], "review_status": "unreviewed"}
            for r in selected
        ],
    }
    if output.exists():
        raise ValueError("Refusing to overwrite existing annotations")
    atomic_json(output, template)
    return {"output": str(output), "selected": len(selected), "baseline": baseline}


def analyze_annotations(data: Path, run: Path, frozen: dict, annotations: Path, output: Path):
    validate_freeze(frozen, data)
    payload = read_json(annotations)
    if (
        payload["freeze"] != frozen["hash"]
        or read_json(run / "study.json")["freeze"] != frozen["hash"]
    ):
        raise ValueError("Annotations or results do not match freeze")
    tokenizer = Tokenizer(ModelConfig.model_validate(frozen["body"]["config"]["model"]))
    summaries = {}
    for item in payload["records"]:
        if item["review_status"] != "reviewed" or not item["references"]:
            continue
        if any(
            r.get("provenance") not in {"human_reviewed", "grader_reference", "model_suggested"}
            for r in item["references"]
        ):
            raise ValueError("Every reference requires an explicit provenance category")
        uid = item["trajectory_id"]
        t = CanonicalTrajectory.model_validate(read_json(data / "trajectories" / f"{uid}.json"))
        for path in sorted((run / "test").glob(f"*/{uid}.json")):
            from agent_safety_monitoring.schema import MonitoringResult

            result = MonitoringResult.model_validate(read_json(path)["result"])
            check = retention(t, result, item["references"], tokenizer)
            name = path.parent.name
            bucket = summaries.setdefault(
                name,
                {
                    "references": 0,
                    "verified_citations": 0,
                    "eae_quotes_retained": 0,
                    "annotation_sources": {},
                },
            )
            for ref in check["references"]:
                bucket["references"] += 1
                bucket["verified_citations"] += int(ref["final_citation"])
                bucket["eae_quotes_retained"] += int(ref["retained_exactly"])
                provenance = ref["provenance"]
                bucket["annotation_sources"][provenance] = (
                    bucket["annotation_sources"].get(provenance, 0) + 1
                )
    result = {
        "freeze": frozen["hash"],
        "methods": summaries,
        "reviewed_records": sum(r["review_status"] == "reviewed" for r in payload["records"]),
        "unreviewed_records": sum(r["review_status"] != "reviewed" for r in payload["records"]),
        "note": (
            "Quotation retention applies to EaE only; "
            "citation omission is not proof of misunderstanding."
        ),
    }
    atomic_json(output, result)
    return result
