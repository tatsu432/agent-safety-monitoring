"""Small, explicitly synthetic fixtures for an end-to-end software check."""

from pathlib import Path

from agent_safety_monitoring.experiments.runner import create_freeze, run_sync
from agent_safety_monitoring.io import atomic_json, digest
from agent_safety_monitoring.schema import CanonicalTrajectory, EvaluationRecord, Segment


def demo(root: Path):
    data = root / "data"
    records = []
    for split, n in [("development", 3), ("calibration", 6), ("test", 6)]:
        for i in range(n):
            for label in [0] if split == "calibration" else [0, 1]:
                uid = digest(["synthetic", split, i, label])
                text = f"Synthetic tool output for software testing {i}."
                t = CanonicalTrajectory(
                    id=uid,
                    task="Synthetic task: inspect a test fixture.",
                    segments=[
                        Segment(
                            id="step0",
                            role="tool",
                            kind="tool_result",
                            text=text,
                            source_message=0,
                            source_end=len(text),
                            interaction=0,
                        )
                    ],
                )
                r = EvaluationRecord(
                    trajectory_id=uid,
                    task_id=f"synthetic-{split}-{i}",
                    assignment="attack" if label else "benign",
                    outcome="success" if label else "not_applicable",
                    objective="synthetic" if label else None,
                    source_file="synthetic",
                    source_sha256=digest("synthetic"),
                    sample_id=uid,
                    provenance={"synthetic": True},
                    split=split,
                )
                records.append(r.model_dump())
                atomic_json(data / "trajectories" / f"{uid}.json", t.model_dump())
    atomic_json(
        data / "manifest.json",
        {
            "version": 1,
            "records": records,
            "rejected": [],
            "sources": {"synthetic": digest("synthetic")},
        },
    )
    from agent_safety_monitoring.data.ingest import audit

    audit(data)
    config = {
        "model": {"backend": "mock"},
        "methods": [{"method": m} for m in ["single", "think", "average", "eae", "mrt"]],
    }
    # Demo regeneration is allowed; production freezes are immutable.
    freeze_path = root / "freeze.json"
    freeze_path.unlink(missing_ok=True)
    frozen = create_freeze(data, config, freeze_path)
    result = None
    for split in ["development", "calibration", "test"]:
        result = run_sync(
            data, root / "results", config, split, frozen if split != "development" else None
        )
    from agent_safety_monitoring.reporting.report import generate

    report = generate(Path(result["run_root"]), root / "report", replicates=100)
    from agent_safety_monitoring.experiments.injection_runner import run_injections_sync
    from agent_safety_monitoring.reporting.diagnostics import structural_report

    structural_report(data, Path(result["run_root"]), frozen, root / "structural", replicates=30)
    run_injections_sync(data, root / "secondary", frozen, root / "report" / "metrics.json")
    return {"software_only": True, "last_run": result, "report": report}
