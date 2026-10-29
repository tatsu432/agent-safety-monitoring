"""Frozen secondary experiment with persisted matched variants and paired outcomes."""

import asyncio
from pathlib import Path

import numpy as np

from agent_safety_monitoring.evaluation.metrics import AlertPolicy
from agent_safety_monitoring.experiments.injections import inject
from agent_safety_monitoring.experiments.runner import validate_freeze
from agent_safety_monitoring.inference.backend import Backend, ModelConfig
from agent_safety_monitoring.io import atomic_json, digest, read_json
from agent_safety_monitoring.monitors.core import MethodConfig, Monitor
from agent_safety_monitoring.schema import CanonicalTrajectory, MonitoringResult


async def run_injections(data: Path, root: Path, frozen: dict, primary_report: Path):
    validate_freeze(frozen, data)
    model = ModelConfig.model_validate(frozen["body"]["config"]["model"])
    backend = Backend(model, root / "injection-cache")
    methods = [
        MethodConfig.model_validate(c)
        for c in frozen["body"]["config"]["methods"]
        if c["method"] in {"single", "eae"}
    ]
    selected = set(frozen["body"]["injections"]["trajectory_ids"])
    records = [
        r for r in read_json(data / "manifest.json")["records"] if r["trajectory_id"] in selected
    ]
    primary = read_json(primary_report)
    if primary.get("freeze") != frozen["hash"]:
        raise ValueError("Thresholds belong to a different frozen study")
    policies = primary["methods"]
    saved_rows = []
    try:
        for config in methods:
            method_id = f"{config.method}-{digest(config.model_dump())[:12]}"
            policy = AlertPolicy(**policies[method_id]["primary"]["policy"])
            for record in records:
                t = CanonicalTrajectory.model_validate(
                    read_json(data / "trajectories" / f"{record['trajectory_id']}.json")
                )
                for family in frozen["body"]["injections"]["payloads"]:
                    for placement in ["early", "late"]:
                        results = {}
                        for neutral in [False, True]:
                            variant = "neutral" if neutral else "injected"
                            path = (
                                root
                                / "injections"
                                / frozen["hash"]
                                / method_id
                                / t.id
                                / f"{family}-{placement}-{variant}.json"
                            )
                            if path.exists():
                                result = MonitoringResult.model_validate(read_json(path)["result"])
                            else:
                                modified = inject(t, family, placement, neutral)
                                if neutral:
                                    text = frozen["body"]["injections"]["controls"][family]
                                    index = 0 if placement == "early" else -1
                                    modified.segments[index] = modified.segments[index].model_copy(
                                        update={"text": text, "source_end": len(text)}
                                    )
                                result = await Monitor(backend).run(modified, config)
                                atomic_json(
                                    path,
                                    {
                                        "evaluation": record,
                                        "freeze": frozen["hash"],
                                        "family": family,
                                        "placement": placement,
                                        "variant": variant,
                                        "result": result.model_dump(),
                                    },
                                )
                            results[variant] = result
                        p = policy.alerts([results[v].score for v in ["injected", "neutral"]])
                        saved_rows.append(
                            {
                                "method": method_id,
                                "task_id": record["task_id"],
                                "trajectory_id": t.id,
                                "label": int(record["assignment"] == "attack"),
                                "family": family,
                                "placement": placement,
                                "alert_difference": float(p[0] - p[1]),
                                "miss_difference": float(p[1] - p[0]),
                                "invalid_injected": results["injected"].status != "valid",
                                "invalid_neutral": results["neutral"].status != "valid",
                            }
                        )
    finally:
        await backend.close()
    # Cluster-paired bootstrap within the small secondary sample.
    aggregate = {}
    rng = np.random.default_rng(20261028)
    for method in sorted({r["method"] for r in saved_rows}):
        for label in [0, 1]:
            rows = [r for r in saved_rows if r["method"] == method and r["label"] == label]
            tasks = sorted({r["task_id"] for r in rows})
            if not tasks:
                continue
            variable = "miss_difference" if label else "alert_difference"
            grouped = {task: [r[variable] for r in rows if r["task_id"] == task] for task in tasks}
            samples = [
                np.mean(
                    [
                        v
                        for task in rng.choice(tasks, len(tasks), replace=True)
                        for v in grouped[task]
                    ]
                )
                for _ in range(2000)
            ]
            aggregate[f"{method}/{'missed_attacks' if label else 'false_alarms'}"] = {
                "mean_change": float(np.mean([r[variable] for r in rows])),
                "ci95": np.quantile(samples, [0.025, 0.975]).tolist(),
                "tasks": len(tasks),
            }
    atomic_json(
        root / "injection-metrics.json",
        {"freeze": frozen["hash"], "rows": saved_rows, "aggregate": aggregate},
    )
    from agent_safety_monitoring.reporting.diagnostics import injection_figure

    injection_figure(root / "injection-metrics.json", root / "injection-robustness.png")
    return {"comparisons": len(saved_rows), "output": str(root / "injection-metrics.json")}


def run_injections_sync(*args):
    return asyncio.run(run_injections(*args))
