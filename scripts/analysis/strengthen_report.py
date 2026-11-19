"""Replay completed scoring runs and publish aggregate-only follow-up metrics."""

import argparse
import math
from collections import Counter
from pathlib import Path

from seed_variability import analyze as analyze_seeds

from agent_safety_monitoring.analysis.audit import audit, verify_manifest
from agent_safety_monitoring.analysis.followup import load_split, report
from agent_safety_monitoring.analysis.lengths import length_analysis
from agent_safety_monitoring.analysis.operating_points import comparison
from agent_safety_monitoring.io import atomic_json, digest, file_hash, read_json
from agent_safety_monitoring.reporting.report import load_results


def equivalent(expected, actual):
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return expected.keys() == actual.keys() and all(
            equivalent(expected[k], actual[k]) for k in expected
        )
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(
            equivalent(a, b) for a, b in zip(expected, actual, strict=True)
        )
    if isinstance(expected, float):
        return math.isclose(expected, actual, rel_tol=0, abs_tol=1e-12)
    return expected == actual


def main(args):
    base = args.recovered
    frozen = read_json(args.original_freeze)
    verify_manifest(frozen)
    followup = read_json(base / "followup-freeze.json")
    if digest(followup["body"]) != followup["hash"]:
        raise ValueError("Follow-up freeze digest mismatch")
    identity = read_json(base / "scoring/identity.json")
    acceptance = followup["body"]
    if (
        acceptance["identity"] != identity
        or identity["original_freeze"] != frozen["hash"]
        or not acceptance["development_accepted"]
    ):
        raise ValueError("Held-out results do not bind to the accepted follow-up freeze")
    continuation = read_json(base / "continuation.json")
    development_job = continuation["completed"]["development"]["job_id"]
    proofs = {
        "context_sha256": base / "context-canonical.json",
        "selection_sha256": base / "selection.json",
        "runtime_sha256": base / f"development/jobs/{development_job}-followup-runtime.json",
        "sacct_sha256": base / f"development-{development_job}-sacct.txt",
    }
    if any(file_hash(path) != acceptance[key] for key, path in proofs.items()):
        raise ValueError("Follow-up physical acceptance evidence differs from the freeze")
    output = args.private_output
    output.mkdir(parents=True, exist_ok=True)
    original_audit = audit(
        args.original_freeze,
        args.original_repo,
        args.data,
        output / "original-audit.json",
        args.original_run,
    )
    if not original_audit["integrity_passed"]:
        raise ValueError("Original integrity audit failed")

    archived = read_json(base / "scoring-report.json")
    scored = base / "scoring"
    report(scored, output / "scoring.json", args.replicates, args.original_run)
    generated = read_json(output / "scoring.json")
    if archived["sources"] != generated["sources"] or archived["identity"] != generated["identity"]:
        raise ValueError("Held-out artifact hashes differ from the completed archive")
    if args.replicates == archived["scoring"]["replicates"]:
        for key in ("point", "intervals", "paired_differences"):
            if any(
                not equivalent(v, generated["scoring"][key][k])
                for k, v in archived["scoring"][key].items()
            ):
                raise ValueError(f"Archive replay mismatch in {key}")

    dev, _, _, _, dev_sources = load_split(base / "development", "development")
    selection = read_json(base / "selection.json")
    if selection["sources"] != dev_sources:
        raise ValueError("Development selection and result hashes differ")
    loaded = {name: load_split(scored, name, record_costs=True) for name in ("calibration", "test")}
    tables = {name: obj[0] for name, obj in loaded.items()}
    originals = load_results(args.original_run)
    for split, values in originals.items():
        for name, rows in values.items():
            tables[split][f"original-{name.split('-', 1)[0]}"] = rows
    low_fpr = comparison(tables["calibration"], tables["test"], args.replicates, target=0.01)
    audit_data = read_json(args.data / "audit.json")
    lengths = length_analysis(
        dev["five-n1"],
        tables["calibration"],
        tables["test"],
        {r["trajectory_id"]: r for r in audit_data["features"]},
        args.replicates,
    )
    seed = read_json(base / "seed-variability.json")
    if not equivalent(seed, analyze_seeds(base, output / "seed-variability.json")):
        raise ValueError("Saved seed-repeat statistics differ from replay")
    replacement = read_json(base / "replacement/summary.json")
    retention = read_json(base / "objective-aware-retention.json")
    timing = read_json(base / "timing/measurements.json")
    allowed_keys = (
        "scoring",
        "logical_costs",
        "disagreement",
        "supplementary_counts",
        "distributions",
        "roc_curves",
        "marginal",
        "coarsening",
        "cost_definition",
    )
    publish = {
        "schema_version": 1,
        "status": generated["status"],
        "original_freeze": frozen["hash"],
        "original_source_commit": frozen["body"]["git_commit"],
        "followup_freeze": followup["hash"],
        "result_inventory_sha256": digest(generated["sources"]),
        "development_inventory_sha256": digest(dev_sources),
        "original_result_inventory_sha256": generated["original_comparison_provenance"][
            "result_hashes_sha256"
        ],
        "artifact_counts": dict(Counter(p.split("/", 1)[0] for p in generated["sources"])),
        "archived_scoring_sha256": file_hash(base / "scoring-report.json"),
        "selected_on_development": selection["selected"],
        "one_percent": low_fpr,
        "length": lengths,
        "seed_variability": seed,
        "timing": timing["methods"],
        "evidence_replacement": replacement,
        "evidence_retention": retention,
        **{key: generated[key] for key in allowed_keys},
    }
    atomic_json(args.output, publish)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in (
        "recovered",
        "original-freeze",
        "original-repo",
        "data",
        "original-run",
        "private-output",
        "output",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=2000)
    main(parser.parse_args())
