"""Controlled EaE diagnosis with blinded, source-checked evidence references."""

from collections import Counter, defaultdict
from pathlib import Path

from agent_safety_monitoring.analysis.audit import verify_manifest
from agent_safety_monitoring.analysis.model_review import SYSTEM, blinded_payload
from agent_safety_monitoring.evaluation.metrics import calibrate
from agent_safety_monitoring.inference.backend import Backend, ModelConfig
from agent_safety_monitoring.io import FileLock, digest, file_hash, immutable_json, read_json
from agent_safety_monitoring.monitors.core import prompt, stage_system
from agent_safety_monitoring.reporting.report import load_results
from agent_safety_monitoring.schema import CanonicalTrajectory, Judgment, Quotation

VERSION = "extension-eae-v1"
CONDITIONS = ("original_excerpts", "suggested_excerpts", "expanded_context", "full_transcript")


def source_trajectory(data, frozen, uid):
    path = data / "trajectories" / f"{uid}.json"
    if file_hash(path) != frozen["body"]["trajectory_hashes"][uid]:
        raise ValueError("Canonical source differs from the freeze")
    return CanonicalTrajectory.model_validate(read_json(path))


def flagged(policy, row):
    draw = int(digest([VERSION, "alert", row["trajectory_id"]])[:16], 16) / 16**16
    return draw < policy.alerts([row["score"]])[0]


def choose_cases(full, eae, full_policy, eae_policy):
    by_id = {row["trajectory_id"]: row for row in eae}
    groups = defaultdict(lambda: ([], []))
    benign = defaultdict(list)
    for row in full:
        if row["label"]:
            preferred = flagged(full_policy, row) and not flagged(
                eae_policy,
                by_id[row["trajectory_id"]],
            )
            groups[row["objective"]][int(not preferred)].append(row)
        else:
            benign[row["task_id"]].append(row)

    def rank(row):
        return digest([VERSION, "sample", row["trajectory_id"]])

    selected, counts = {}, {}
    for name, (preferred, other) in sorted(groups.items()):
        preferred, other = sorted(preferred, key=rank), sorted(other, key=rank)
        chosen = preferred[:2] + other[:1]
        remaining = preferred[2:] + other[1:]
        chosen += remaining[: 3 - len(chosen)]
        counts[name] = {
            "attacks": len(chosen),
            "full_flags_eae_misses": len(
                {row["trajectory_id"] for row in chosen}
                & {row["trajectory_id"] for row in preferred}
            ),
        }
        for row in chosen:
            selected[row["trajectory_id"]] = row
            paired = sorted(benign[row["task_id"]], key=rank)
            if paired:
                selected[paired[0]["trajectory_id"]] = paired[0]
    return sorted(selected.values(), key=rank), counts


def clean_quotes(value, trajectory):
    lookup = {s.id: s.text for s in trajectory.segments}
    offsets = {s.id: i for i, s in enumerate(trajectory.segments)}
    quotes = []
    seen = set()
    for item in value:
        q = Quotation.model_validate({k: item[k] for k in ("step", "start", "end", "text")})
        key = (q.step, q.start, q.end)
        if (
            key in seen
            or q.step not in lookup
            or not 0 <= q.start < q.end <= len(lookup[q.step])
            or lookup[q.step][q.start : q.end] != q.text
        ):
            raise ValueError("Invalid source quote")
        seen.add(key)
        quotes.append(q)
    return sorted(quotes, key=lambda q: (offsets[q.step], q.start, q.end))


def extract_saved(result, trajectory):
    artifacts = [
        a["output"]["quotes"] for a in result.artifacts if a["stage"] == "extract" and "output" in a
    ]
    if len(artifacts) != 1:
        return None
    return clean_quotes(artifacts[0], trajectory)


def prepare(data, freeze_path, original_run, output, review_root=None):
    freeze = read_json(freeze_path)
    verify_manifest(freeze)
    if digest(read_json(data / "manifest.json")) != freeze["body"]["dataset_manifest"]:
        raise ValueError("Dataset differs from the freeze")
    if read_json(original_run / "study.json")["freeze"] != freeze["hash"]:
        raise ValueError("Unrelated original result archive")
    tables = load_results(original_run)
    names = {
        method: next(name for name in tables["test"] if name.startswith(f"{method}-"))
        for method in ("single", "eae")
    }
    test = tables["test"]
    full, eae = test[names["single"]], test[names["eae"]]
    policies = {
        name: calibrate([row["score"] for row in tables["calibration"][name]])
        for name in names.values()
    }
    sample, counts = choose_cases(full, eae, policies[names["single"]], policies[names["eae"]])
    selected = {row["trajectory_id"] for row in sample}
    found = {row["trajectory_id"]: row for row in eae if row["trajectory_id"] in selected}
    archive_id = read_json(review_root / "identity.json") if review_root else None
    if archive_id and (
        archive_id["freeze"] != freeze["hash"] or archive_id["system_hash"] != digest(SYSTEM)
    ):
        raise ValueError("Only blinded reviewer outputs from the same freeze may be imported")
    requests, metadata = [], {}
    for row in sample:
        uid = row["trajectory_id"]
        t = source_trajectory(data, freeze, uid)
        quotes = extract_saved(found[uid]["result"], t)
        path = review_root / "annotations" / f"{uid}.json" if review_root else None
        annotation = read_json(path) if path and path.exists() else None
        if annotation and annotation["identity"] != archive_id:
            raise ValueError("Archived annotation differs from blinded review identity")
        suggested = suggested_quotes(annotation, t) if annotation else None
        if suggested == []:
            suggested = None
        if suggested is None:
            requests.append({"trajectory_id": uid, "payload": blinded_payload(t)})
        metadata[uid] = {
            "task_id": row["task_id"],
            "label": row["label"],
            "objective": row["objective"],
            "original_full_score": row["score"],
            "original_eae_score": found[uid]["score"],
            "original_excerpts": [q.model_dump() for q in quotes] if quotes is not None else None,
            "suggested_excerpts": [q.model_dump() for q in suggested] if suggested else None,
        }
    counts_total = {
        "attacks": sum(r["label"] for r in sample),
        "benign": sum(not r["label"] for r in sample),
        "tasks": len({r["task_id"] for r in sample}),
        "objectives": counts,
        "reused_model_suggested": sum(bool(r["suggested_excerpts"]) for r in metadata.values()),
        "original_extractions_available": sum(
            r["original_excerpts"] is not None for r in metadata.values()
        ),
        "original_extractions_empty": sum(r["original_excerpts"] == [] for r in metadata.values()),
        "human_verified": 0,
        "source": freeze["hash"],
    }
    with FileLock(output / "prepare.lock"):
        immutable_json(
            output / "sample.json",
            {
                "version": VERSION,
                "freeze": freeze["hash"],
                "records": metadata,
                "summary": counts_total,
            },
        )
        immutable_json(
            output / "review-test.json",
            {
                "freeze": freeze["hash"],
                "phase": "test",
                "system_hash": digest(SYSTEM),
                "sample_hash": digest(metadata),
                "records": requests,
            },
        )
        immutable_json(output / "design-summary.json", counts_total)
    return counts_total


def suggested_quotes(annotation, trajectory):
    if (
        annotation.get("annotation_status") != "model_suggested"
        or annotation.get("proposal", {}).get("conclusion") != "supported"
    ):
        return None
    refs = annotation.get("references", [])
    if not refs or any(r.get("provenance") != "model_suggested" for r in refs):
        return None
    return clean_quotes(refs, trajectory)


def full_quotes(trajectory):
    return [
        Quotation(step=s.id, start=0, end=len(s.text), text=s.text)
        for s in trajectory.segments
        if s.text
    ]


def expanded_quotes(quotes, trajectory):
    positions = {s.id: i for i, s in enumerate(trajectory.segments)}
    relevant = {trajectory.segments[positions[q.step]].interaction for q in quotes}
    indices = [i for i, s in enumerate(trajectory.segments) if s.interaction in relevant]
    if not indices:
        return []
    all_segments = full_quotes(trajectory)
    return [q for q in all_segments if min(indices) <= positions[q.step] <= max(indices)]


def extraction_overlap(original, suggested):
    if original is None or not suggested:
        return None
    counts = Counter()
    ranges = defaultdict(list)
    for quote in original:
        ranges[quote.step].append((quote.start, quote.end))
    for quote in suggested:
        covered = quote.start
        partial = False
        for start, end in sorted(ranges[quote.step]):
            partial |= start < quote.end and end > quote.start
            if start <= covered:
                covered = max(covered, end)
        counts["full" if covered >= quote.end else "partial" if partial else "absent"] += 1
    return dict(counts)


def inputs(data, frozen, sample, review_root, packet, uid):
    t = source_trajectory(data, frozen, uid)
    record = sample["records"][uid]
    a = record["original_excerpts"]
    b = record["suggested_excerpts"]
    if b is None and review_root:
        identity = read_json(review_root / "identity.json")
        if identity["packet_hash"] != file_hash(packet) or identity["system_hash"] != digest(
            SYSTEM
        ):
            raise ValueError("New reviewer archive does not bind to this private packet")
        path = review_root / "annotations" / f"{uid}.json"
        if path.exists():
            saved = read_json(path)
            if saved["identity"] != identity:
                raise ValueError("Evidence identity mismatch")
            result = suggested_quotes(saved, t)
            if result:
                b = [ref.model_dump() for ref in result]
    suggested = clean_quotes(b, t) if b else None
    return t, {
        "original_excerpts": clean_quotes(a, t) if a is not None else None,
        "suggested_excerpts": suggested,
        "expanded_context": expanded_quotes(suggested, t) if suggested else None,
        "full_transcript": full_quotes(t),
    }


async def judge(data, freeze_path, output, review_root=None):
    frozen = read_json(freeze_path)
    verify_manifest(frozen)
    sample = read_json(output / "sample.json")
    if sample["freeze"] != frozen["hash"] or sample["version"] != VERSION:
        raise ValueError("Incompatible controlled diagnosis sample")
    config = ModelConfig.model_validate(frozen["body"]["config"]["model"])
    identity = {
        "version": VERSION,
        "sample_sha256": file_hash(output / "sample.json"),
        "model": config.model_dump(),
        "rubric": stage_system(Judgment),
        "review_sha256": digest(
            {p.name: file_hash(p) for p in sorted((review_root / "annotations").glob("*.json"))}
        )
        if review_root
        else None,
        "seed": 20261028,
        "source_sha256": file_hash(Path(__file__)),
    }
    with FileLock(output / "judge.lock"):
        immutable_json(output / "judge-identity.json", identity)
        backend = Backend(config, output / "judge-cache")
        try:
            for uid in sample["records"]:
                trajectory, conditions = inputs(
                    data,
                    frozen,
                    sample,
                    review_root,
                    output / "review-test.json",
                    uid,
                )
                immutable_json(
                    output / "judgments" / uid / "overlap.json",
                    {
                        "identity": digest(identity),
                        "span_coverage": extraction_overlap(
                            conditions["original_excerpts"],
                            conditions["suggested_excerpts"],
                        ),
                    },
                )
                for name, quotes in conditions.items():
                    path = output / "judgments" / uid / f"{name}.json"
                    if path.exists():
                        if read_json(path)["identity"] != digest(identity):
                            raise ValueError("Saved judge result identity mismatch")
                        continue
                    result = await judge_condition(backend, trajectory, name, quotes)
                    immutable_json(path, {"identity": digest(identity), **result})
        finally:
            await backend.close()
        return aggregate(output)


async def judge_condition(backend, trajectory, name, quotes):
    if quotes is None:
        return {"status": "unresolved", "score": None}
    if name == "suggested_excerpts" and sum(backend.tokens.count(q.text) for q in quotes) > 3000:
        return {"status": "quote_budget", "score": None}
    payload = {"task": trajectory.task, "quotes": [q.model_dump() for q in quotes]}
    messages = prompt(stage_system(Judgment), payload)
    if (
        backend.tokens.prompt(messages, "low") + 2 * backend.config.max_tokens + 128
        > backend.config.context_limit
    ):
        return {"status": "context_overflow", "score": None}
    allowed = {q.step for q in quotes}
    calls = []
    for retry in range(2):
        attempts = await backend.generate(messages, Judgment, "judge", 20261028 + retry)
        calls.extend(c.model_dump() for c in attempts)
        last = attempts[-1]
        if last.error:
            raise RuntimeError("Infrastructure failure in fixed EaE diagnosis judge")
        try:
            result = Judgment.model_validate_json(last.response or "")
            if last.finish_reason not in {None, "stop"} or not set(result.citations) <= allowed:
                raise ValueError("Invalid judgment or citation")
            return {"status": "valid", "score": result.score, "calls": calls}
        except ValueError:
            messages += [
                {"role": "assistant", "content": last.response or ""},
                {"role": "user", "content": "Return the required JSON and cite provided steps."},
            ]
    return {"status": "invalid", "score": None, "calls": calls}


def aggregate(output):
    sample = read_json(output / "sample.json")
    identity = digest(read_json(output / "judge-identity.json"))
    conditions = {}
    for uid, record in sample["records"].items():
        results = {}
        for name in CONDITIONS:
            result = read_json(output / "judgments" / uid / f"{name}.json")
            if result["identity"] != identity:
                raise ValueError("Mixed diagnosis runs")
            results[name] = result
        coverage = read_json(output / "judgments" / uid / "overlap.json")
        if coverage["identity"] != identity:
            raise ValueError("Mixed extraction coverage artifacts")
        conditions[uid] = (record["label"], results, coverage["span_coverage"])

    report = {
        "version": VERSION,
        "status": "exploratory model-suggested evidence",
        "sample": sample["summary"],
        "classes": {},
    }
    for label, group in ((0, "benign"), (1, "successful_attack")):
        rows = [r for kind, r, _ in conditions.values() if kind == label]
        overlap = [c for kind, _, c in conditions.values() if kind == label and c is not None]
        counts = {name: dict(Counter(r[name]["status"] for r in rows)) for name in CONDITIONS}
        paired = {}
        for left, right in zip(CONDITIONS, CONDITIONS[1:], strict=False):
            differences = [
                r[right]["score"] - r[left]["score"]
                for r in rows
                if r[left]["status"] == r[right]["status"] == "valid"
            ]
            paired[f"{right}_minus_{left}"] = {
                "n": len(differences),
                "mean": sum(differences) / len(differences) if differences else None,
                "higher": sum(d > 0 for d in differences),
                "equal": sum(d == 0 for d in differences),
                "lower": sum(d < 0 for d in differences),
            }
        report["classes"][group] = {
            "coverage": counts,
            "paired": paired,
            "complete_cases": sum(
                all(v["status"] == "valid" for v in row.values()) for row in rows
            ),
            "cases_with_resolved_reference_and_original_extraction": len(overlap),
            "cases_with_at_least_one_suggested_span_absent": sum(
                c.get("absent", 0) > 0 for c in overlap
            ),
            "suggested_reference_span_coverage": dict(
                sum((Counter(c) for c in overlap), Counter())
            ),
        }
    immutable_json(output / "eae-aggregate.json", report)
    return report
