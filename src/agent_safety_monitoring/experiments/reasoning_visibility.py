"""Fail-closed runner for the first physical reasoning-visibility development pilot."""

import time

from agent_safety_monitoring.analysis.audit import verify_manifest
from agent_safety_monitoring.analysis.reasoning_profile import cohort_acceptance
from agent_safety_monitoring.data.reasoning import VIEWS, EvidenceView, ReleaseProof
from agent_safety_monitoring.experiments.followup import fine_review
from agent_safety_monitoring.experiments.runner import source_identity
from agent_safety_monitoring.inference.backend import Backend, ModelConfig
from agent_safety_monitoring.io import FileLock, digest, file_hash, immutable_json, read_json


def accepted_inputs(views, proof, original):
    frozen = read_json(original)
    verify_manifest(frozen)
    audit = read_json(views / "audit.json")
    private = read_json(views / "features.json")
    if not audit["authorship_verified"] or audit["release_proof_sha256"] != file_hash(proof):
        raise ValueError("Release-specific authorship proof must be accepted before inference")
    ReleaseProof.model_validate(read_json(proof)).verify(audit["source_sha256"])
    if frozen["hash"] != audit["original_freeze"] or digest(private) != audit["feature_sha256"]:
        raise ValueError("Audit, features or original freeze differ")
    if not cohort_acceptance(private["features"])["passes_coverage_gate"]:
        raise ValueError("Context-eligible cohort did not pass the declared coverage gate")
    return frozen, audit, private["features"]


def pilot_cases(features):
    rows = []
    for assignment, outcome in (("benign", "not_applicable"), ("attack", "success")):
        available = sorted(
            (
                r
                for r in features
                if r["split"] == "development"
                and r["single_cohort"]
                and r["assignment"] == assignment
                and r["outcome"] == outcome
            ),
            key=lambda r: (max(x["single"] for x in r["context"].values()), r["trajectory_id"]),
        )
        if len(available) < 6:
            raise ValueError("Pilot requires six eligible development cases per class")
        for quantile in (0, 0.2, 0.4, 0.6, 0.8, 1):
            rows.append(available[round(quantile * (len(available) - 1))])
    return rows


async def run_pilot(views, proof, original, output):
    """Run one cold single-review pilot on an allocated GPU and resume by exact identities."""
    import os

    if int(os.environ.get("SLURM_GPUS_ON_NODE", "0")) != 1 or not os.environ.get("SLURM_JOB_ID"):
        raise ValueError("The physical pilot requires one allocated Slurm GPU")
    frozen, audit, features = accepted_inputs(views, proof, original)
    cases = pilot_cases(features)
    model = ModelConfig.model_validate(frozen["body"]["config"]["model"])
    identity = {
        "version": 1,
        "original_freeze": frozen["hash"],
        "audit_sha256": file_hash(views / "audit.json"),
        "proof_sha256": file_hash(proof),
        "records": {r["trajectory_id"]: r["view_hashes"] for r in cases},
        "model": model.model_dump(),
        "sources": source_identity(),
        "seed": 20261028,
    }
    duration, metrics = {}, {}
    with FileLock(output / "pilot.lock"):
        immutable_json(output / "identity.json", identity)
        for name in VIEWS:
            started = time.monotonic()
            backend = Backend(model, output / name / "cache")
            invalid = resumed = 0
            try:
                for item in cases:
                    uid = item["trajectory_id"]
                    path = views / "views" / name / f"{uid}.json"
                    if file_hash(path) != identity["records"][uid][name]:
                        raise ValueError("Materialized view hash differs from the accepted audit")
                    dest = output / name / "reviews" / f"{uid}.json"
                    if dest.exists():
                        resumed += 1
                        saved = read_json(dest)
                    else:
                        trajectory = EvidenceView.model_validate(read_json(path))
                        saved = {
                            "identity": digest(identity),
                            "review": await fine_review(
                                backend,
                                trajectory,
                                identity["seed"],
                            ),
                        }
                        immutable_json(dest, saved)
                    if saved["identity"] != digest(identity):
                        raise ValueError("Pilot review identity mismatch")
                    invalid += saved["review"]["status"] != "valid"
            finally:
                await backend.close()
            duration[name] = time.monotonic() - started
            metrics[name] = {"invalid": invalid, "completed": len(cases), "resumed": resumed}
            if invalid > 1:
                raise ValueError("Development validity gate failed")
        receipt = {
            "pilot_identity": digest(identity),
            "workload_seconds": duration,
            "status": metrics,
            "job_id": os.environ["SLURM_JOB_ID"],
            "context_limit": audit["context_limit"],
            "requires_slurm_and_memory_review": True,
        }
        immutable_json(output / f"{receipt['job_id']}-pilot.json", receipt)
    return receipt
