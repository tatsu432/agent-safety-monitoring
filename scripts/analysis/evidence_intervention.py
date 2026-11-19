"""Private, fixed-judge diagnostic using source-checked model-suggested highlights."""

import argparse
import asyncio
from collections import Counter, defaultdict
from pathlib import Path

from pydantic import ValidationError

from agent_safety_monitoring.analysis.audit import verify_manifest
from agent_safety_monitoring.evaluation.metrics import calibrate
from agent_safety_monitoring.inference.backend import Backend, ModelConfig
from agent_safety_monitoring.io import (
    FileLock,
    atomic_json,
    digest,
    file_hash,
    immutable_json,
    read_json,
)
from agent_safety_monitoring.monitors.core import evidence_payload, prompt, stage_system
from agent_safety_monitoring.reporting.report import load_results
from agent_safety_monitoring.schema import CanonicalTrajectory, Judgment


def prepare(data, freeze, recovered, original, output):
    tables = load_results(original)
    packet = read_json(recovered / "objective-aware-test-packet.json")
    if packet["freeze"] != freeze["hash"] or not packet["objective_aware"]:
        raise ValueError("Expected the fixed objective-aware diagnostic packet")
    eae = next(k for k in tables["test"] if k.startswith("eae-"))
    single = next(k for k in tables["test"] if k.startswith("single-"))
    eae_by_id = {r["trajectory_id"]: r for r in tables["test"][eae]}
    full_by_id = {r["trajectory_id"]: r for r in tables["test"][single]}
    policy = calibrate([r["score"] for r in tables["calibration"][eae]])
    groups = defaultdict(list)
    for record in packet["records"]:
        uid = record["trajectory_id"]
        groups[eae_by_id[uid]["objective"]].append(uid)
    selected = [uid for uids in groups.values() for uid in sorted(uids)[:3]]
    coverage, cached = Counter(), {}
    for uid in sorted(selected):
        annotation = read_json(recovered / "review-test/annotations" / f"{uid}.json")
        replacement = read_json(recovered / "replacement/results" / f"{uid}.json")
        source = data / "trajectories" / f"{uid}.json"
        if file_hash(source) != freeze["body"]["trajectory_hashes"][uid]:
            raise ValueError("Evidence-source trajectory differs from the freeze")
        trajectory = CanonicalTrajectory.model_validate(read_json(source))
        segments = {s.id: s.text for s in trajectory.segments}
        if annotation["trajectory_id"] != uid or replacement["trajectory_id"] != uid:
            raise ValueError("Diagnostic evidence identity mismatch")
        spans = []
        for value in annotation["references"]:
            lo, hi, step = value["start"], value["end"], value["step"]
            if not 0 <= lo < hi <= len(segments[step]) or segments[step][lo:hi] != value["text"]:
                raise ValueError("Diagnostic span does not match source")
            spans.append({"step": step, "start": lo, "end": hi})
        coverage["reference_spans_source_checked"] += len(spans)
        coverage[replacement["status"]] += 1
        coverage["with_highlights"] += bool(spans)
        cached[uid] = {
            "source_sha256": file_hash(source),
            "spans": spans,
            "original_eae": eae_by_id[uid]["score"],
            "full_saved_single": full_by_id[uid]["score"],
            "model_replacement_status": replacement["status"],
            "model_replacement": replacement.get("score"),
        }
    result = {
        "freeze": freeze["hash"],
        "records": cached,
        "coverage": dict(coverage),
        "policy": {"cutoff": policy.cutoff, "boundary_probability": policy.boundary_probability},
    }
    immutable_json(output, result)
    return {"cases": len(cached), "human_reviewed": 0, **coverage}


async def evaluate(data, frozen, packet, output):
    if packet["freeze"] != frozen["hash"]:
        raise ValueError("Diagnostic packet does not match the frozen model and data")
    model = ModelConfig.model_validate(frozen["body"]["config"]["model"])
    method = next(m for m in frozen["body"]["config"]["methods"] if m["method"] == "single")
    backend = Backend(model, output / "cache")
    identity = digest({"packet": packet, "script_sha256": file_hash(Path(__file__))})
    try:
        with FileLock(output / "run.lock"):
            immutable_json(
                output / "identity.json", {"packet": identity, "model": model.model_dump()}
            )
            results = {}
            for uid, row in packet["records"].items():
                if not row["spans"]:
                    continue
                path = output / "results" / f"{uid}.json"
                if not path.exists():
                    source = data / "trajectories" / f"{uid}.json"
                    if file_hash(source) != row["source_sha256"]:
                        raise ValueError("Highlight source mismatch")
                    trajectory = CanonicalTrajectory.model_validate(read_json(source))
                    payload = evidence_payload(trajectory)
                    payload["highlighted_source_spans"] = row["spans"]
                    payload["highlight_note"] = "Highlights are fallible pointers for review."
                    messages = prompt(stage_system(Judgment), payload)
                    all_calls, score = [], None
                    allowed = {s.id for s in trajectory.segments}
                    for attempt in range(method["output_retries"] + 1):
                        calls = await backend.generate(
                            messages, Judgment, "highlighted-review", method["seed"] + attempt
                        )
                        all_calls.extend(c.model_dump() for c in calls)
                        last = calls[-1]
                        if last.error:
                            raise RuntimeError("Highlighted review infrastructure failure")
                        try:
                            judgment = Judgment.model_validate_json(last.response or "")
                            if last.finish_reason not in (None, "stop") or not (
                                set(judgment.citations) <= allowed
                            ):
                                raise ValueError("Incomplete output or invalid citation")
                        except (ValidationError, ValueError):
                            messages += [
                                {"role": "assistant", "content": last.response or ""},
                                {
                                    "role": "user",
                                    "content": "Return valid JSON with source step IDs.",
                                },
                            ]
                        else:
                            score = judgment.score
                            break
                    atomic_json(path, {"identity": identity, "score": score, "calls": all_calls})
                saved = read_json(path)
                if saved["identity"] != identity:
                    raise ValueError("Highlighted result identity mismatch")
                results[uid] = saved["score"]
            cutoff = packet["policy"]["cutoff"]
            probability = packet["policy"]["boundary_probability"]
            original = packet["records"]

            def expected_alert(score):
                if score is None:
                    return 1
                if cutoff is None:
                    return 0
                return float(score > cutoff) + probability * (score == cutoff)

            matched = [
                (row, results[uid])
                for uid, row in original.items()
                if results.get(uid) is not None
                and row["original_eae"] is not None
                and row["full_saved_single"] is not None
                and row["model_replacement_status"] == "valid"
            ]
            summary = {}
            if matched:
                for label, values in {
                    "original_eae": [r["original_eae"] for r, _ in matched],
                    "model_replacement": [r["model_replacement"] for r, _ in matched],
                    "full_saved_single": [r["full_saved_single"] for r, _ in matched],
                    "highlighted_full": [s for _, s in matched],
                }.items():
                    summary[label] = {
                        "mean_ordinal_score": sum(values) / len(values),
                        "expected_alert_under_original_eae_policy": (
                            sum(map(expected_alert, values)) / len(values)
                        ),
                    }
            atomic_json(
                output / "summary.json",
                {
                    "packet_sha256": digest(packet),
                    "matched_cases": len(matched),
                    "highlighted_attempted": len(results),
                    "highlighted_valid": sum(v is not None for v in results.values()),
                    "human_reviewed": 0,
                    "provenance": "source_checked_model_suggested",
                    "measures": summary,
                },
            )
    finally:
        await backend.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--recovered", type=Path)
    parser.add_argument("--original", type=Path)
    args = parser.parse_args()
    frozen = read_json(args.freeze)
    verify_manifest(frozen)
    if args.output:
        asyncio.run(evaluate(args.data, frozen, read_json(args.packet), args.output))
    else:
        if args.recovered is None or args.original is None:
            parser.error("Preparation requires recovered and original artifacts")
        print(prepare(args.data, frozen, args.recovered, args.original, args.packet))
