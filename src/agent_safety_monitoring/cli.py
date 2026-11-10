"""Command-line entry points; real scientific runs require explicit frozen inputs."""

import json
from pathlib import Path
from typing import Annotated

import typer

from agent_safety_monitoring.io import read_json

app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
data_app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
experiment_app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
app.add_typer(data_app, name="data")
app.add_typer(experiment_app, name="experiment")


def show(value):
    typer.echo(json.dumps(value, indent=2))


@data_app.command()
def download(root: Path = Path("data/raw")):
    """Download checksummed raw BashArena logs (never execute them)."""
    from agent_safety_monitoring.data.download import download as fetch

    show(fetch(root))


@data_app.command("import")
def import_data(
    sources: list[Path],
    root: Path = Path("data/prepared"),
    development_tasks: int = 30,
    seed: int = 20261028,
):
    """Normalize Inspect logs, audit labels, and split whole tasks."""
    from agent_safety_monitoring.data.ingest import import_logs

    show(import_logs(sources, root, development_tasks, seed))


@data_app.command()
def audit(root: Path = Path("data/prepared"), model_config: Path | None = None):
    """Audit counts; pass a pinned real model configuration for tokenizer lengths."""
    from agent_safety_monitoring.data.ingest import audit as audit_data
    from agent_safety_monitoring.inference.backend import ModelConfig, Tokenizer

    tokens = (
        Tokenizer(ModelConfig.model_validate(read_json(model_config))) if model_config else None
    )
    show(audit_data(root, tokens))


@data_app.command("report")
def data_report(root: Path = Path("data/prepared"), output: Path = Path("runs/dataset-report")):
    """Generate aggregate dataset measurements and figure, with no raw text."""
    from agent_safety_monitoring.reporting.dataset import dataset_report

    show(dataset_report(root, output))


@data_app.command("context")
def context(model_config: Annotated[Path, typer.Option()], root: Path = Path("data/prepared")):
    """Measure complete real-tokenizer prompts and generation/retry headroom."""
    from agent_safety_monitoring.data.context import audit_context
    from agent_safety_monitoring.inference.backend import ModelConfig

    show(audit_context(root, ModelConfig.model_validate(read_json(model_config))))


@experiment_app.command()
def configure(
    output: Annotated[Path, typer.Option()],
    science: Path = Path("configs/science/development.json"),
    model: Path = Path("configs/model/gpt-oss-20b.json"),
    hardware: Path = Path("configs/hardware/pilot.json"),
    environment: Path = Path("configs/environment/yale.json"),
    logging: Path = Path("configs/logging/aggregate.json"),
):
    """Compose separate configuration domains into a reviewable resolved study."""
    from agent_safety_monitoring.io import atomic_json

    hw = read_json(hardware)
    config = {
        **read_json(science),
        "model": read_json(model),
        "hardware": hw,
        "execution": hw.get("execution", {}),
        "environment": read_json(environment),
        "logging": read_json(logging),
    }
    atomic_json(output, config)
    show(
        {
            "output": str(output),
            "methods": len(config["methods"]),
            "hardware_verified": hw["verified"],
        }
    )


@experiment_app.command()
def freeze(
    config: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    data: Path = Path("data/prepared"),
):
    """Freeze exact code, data, prompts, analysis, and inference settings."""
    from agent_safety_monitoring.experiments.runner import create_freeze

    frozen = create_freeze(data, read_json(config), output)
    show(
        {
            "freeze": str(output),
            "hash": frozen["hash"],
            "software_only": frozen["body"]["software_only"],
        }
    )


@experiment_app.command()
def run(
    config: Path | None = None,
    frozen: Path | None = None,
    data: Path = Path("data/prepared"),
    output: Path = Path("runs"),
    split: str = "development",
    shard: int = 0,
    shards: int = 1,
    limit: int | None = None,
):
    """Run/resume a development or frozen held-out shard."""
    from agent_safety_monitoring.experiments.runner import run_sync

    if split not in {"development", "calibration", "test"}:
        raise typer.BadParameter("Unknown split")
    lock = read_json(frozen) if frozen else None
    if config is None and lock is None:
        raise typer.BadParameter("Supply --config or --frozen")
    configuration = read_json(config) if config else lock["body"]["config"]
    show(run_sync(data, output, configuration, split, lock, shard, shards, limit))


@experiment_app.command()
def status(run_root: Annotated[Path, typer.Option()]):
    """Read local progress and job-attempt identities without a running server."""
    from agent_safety_monitoring.experiments.progress import status as inspect_status

    show(inspect_status(run_root))


@experiment_app.command()
def diagnose(
    run_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    data: Path = Path("data/prepared"),
):
    """Replay development EaE validation into a private diagnostic file."""
    from agent_safety_monitoring.experiments.diagnose import diagnose as inspect_failures

    show(inspect_failures(run_root, data, output))


@experiment_app.command("resource-usage")
def resource_usage(
    sacct_file: Annotated[Path, typer.Option()], output: Annotated[Path, typer.Option()]
):
    """Read project-filtered sacct -X pipe-delimited allocation records."""
    from agent_safety_monitoring.experiments.resources import allocation_usage
    from agent_safety_monitoring.io import atomic_json

    result = allocation_usage(sacct_file.read_text())
    atomic_json(output, result)
    show(result)


@experiment_app.command("cost-estimate")
def cost_estimate(
    measurements: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    data: Path = Path("data/prepared"),
):
    """Project remaining costs from actual development measurements; not budget approval."""
    from agent_safety_monitoring.experiments.resources import estimate

    show(estimate(measurements, data, output))


@experiment_app.command("pilot-prep")
def pilot_prep(data: Path = Path("data/prepared"), output: Path = Path("data/pilot")):
    """Select short, median and long development examples for hardware testing."""
    from agent_safety_monitoring.experiments.pilot import prepare_pilot

    show(prepare_pilot(data, output))


@experiment_app.command()
def screen_prep(data: Path = Path("data/prepared"), output: Path = Path("data/screen")):
    """Create a balanced development-only screening cohort."""
    from agent_safety_monitoring.experiments.pilot import prepare_balanced_screen

    show(prepare_balanced_screen(data, output))


@experiment_app.command()
def benchmark(
    config: Annotated[Path, typer.Option()],
    gpus: int = 1,
    limit: int = 4,
    data: Path = Path("data/prepared"),
    output: Path = Path("runs/pilot"),
    trial_id: str = "default",
):
    """Measure development workloads inside a Slurm allocation with a loaded server."""
    from agent_safety_monitoring.experiments.benchmark import benchmark as measure

    show(measure(data, output, read_json(config), gpus, limit, trial_id))


@experiment_app.command()
def injections(
    frozen: Annotated[Path, typer.Option()],
    primary_report: Annotated[Path, typer.Option()],
    data: Path = Path("data/prepared"),
    output: Path = Path("runs/secondary"),
):
    """Run frozen matched-control injections after primary calibration/evaluation."""
    from agent_safety_monitoring.experiments.injection_runner import run_injections_sync

    show(run_injections_sync(data, output, read_json(frozen), primary_report))


@experiment_app.command()
def demo(output: Path = Path("runs/demo")):
    """Synthetic end-to-end check of all methods, not a scientific experiment."""
    from agent_safety_monitoring.experiments.demo import demo as run_demo

    show(run_demo(output))


@experiment_app.command()
def structural(
    frozen: Annotated[Path, typer.Option()],
    run_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    data: Path = Path("data/prepared"),
    replicates: int = 2000,
):
    """Development-fitted feature baselines and task-aware length sensitivity."""
    from agent_safety_monitoring.reporting.diagnostics import structural_report

    show(structural_report(data, run_root, read_json(frozen), output, replicates))


@experiment_app.command("select")
def select(
    measurements: Annotated[Path, typer.Option()],
    config: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Choose fixed-budget candidates using development timing and labels only."""
    from agent_safety_monitoring.experiments.selection import select as choose

    show(choose(measurements, config, output))


@experiment_app.command("annotation-sample")
def annotation_sample(
    frozen: Annotated[Path, typer.Option()],
    run_root: Annotated[Path, typer.Option()],
    primary_report: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    data: Path = Path("data/prepared"),
    limit: int = 30,
):
    """Prepare an independent, stratified evidence annotation template."""
    from agent_safety_monitoring.evaluation.annotations import prepare_annotations

    show(prepare_annotations(data, run_root, read_json(frozen), primary_report, output, limit))


@experiment_app.command("annotation-report")
def annotation_report(
    frozen: Annotated[Path, typer.Option()],
    run_root: Annotated[Path, typer.Option()],
    annotations: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    data: Path = Path("data/prepared"),
):
    """Verify independent reference spans and aggregate evidence retention."""
    from agent_safety_monitoring.evaluation.annotations import analyze_annotations

    show(analyze_annotations(data, run_root, read_json(frozen), annotations, output))


@app.command()
def report(
    run_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    replicates: int = 2000,
):
    """Generate aggregate results, paired bootstrap intervals, tables and figures."""
    from agent_safety_monitoring.reporting.report import generate

    show(generate(run_root, output, replicates))


analysis_app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
app.add_typer(analysis_app, name="analysis")


@analysis_app.command("audit")
def analysis_audit(
    freeze: Annotated[Path, typer.Option()],
    repository: Annotated[Path, typer.Option()],
    data: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    run_root: Path | None = None,
):
    """Check frozen source objects/data without changing the original checkout."""
    from agent_safety_monitoring.analysis.audit import audit

    show(audit(freeze, repository, data, output, run_root))


@analysis_app.command("aggregate")
def analysis_aggregate(
    bundle: Annotated[Path, typer.Option()],
    freeze: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    replicates: int = 2000,
    features: Path | None = None,
    tracking_mode: str = "online",
):
    """Publish numerical aggregates only; never export private injection rows."""
    from agent_safety_monitoring.analysis.aggregate import generate

    show(generate(bundle, freeze, output, replicates, features, tracking_mode))


@analysis_app.command("features")
def analysis_features(
    data: Annotated[Path, typer.Option()], output: Annotated[Path, typer.Option()]
):
    """Aggregate calibration/test source-feature distributions without private IDs."""
    from agent_safety_monitoring.analysis.records import feature_shift

    show(feature_shift(data, output))


@analysis_app.command("records")
def analysis_records(
    freeze: Annotated[Path, typer.Option()],
    repository: Annotated[Path, typer.Option()],
    data: Annotated[Path, typer.Option()],
    run_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    replicates: int = 2000,
):
    """Reconcile full frozen records before private post-hoc diagnostics."""
    from agent_safety_monitoring.analysis.audit import audit
    from agent_safety_monitoring.analysis.records import full_diagnostics

    checked = audit(freeze, repository, data, output / "audit.json", run_root)
    if not checked["integrity_passed"]:
        raise typer.BadParameter("Frozen source/data integrity failed")
    show(full_diagnostics(data, run_root, output, replicates))


@analysis_app.command("review-prepare")
def analysis_review_prepare(
    freeze: Annotated[Path, typer.Option()],
    data: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    sample: Path | None = None,
    development: bool = False,
    objective_aware: bool = False,
):
    """Prepare a private blinded packet from development or the existing diagnostic sample."""
    from agent_safety_monitoring.analysis.model_review import prepare_packet

    show(prepare_packet(data, read_json(freeze), output, sample, development, objective_aware))


@analysis_app.command("review-run")
def analysis_review_run(
    packet: Annotated[Path, typer.Option()],
    config: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    proof: Path | None = None,
):
    """Run local model-suggested annotation; held-out diagnostics require a development proof."""
    import asyncio

    from agent_safety_monitoring.analysis.model_review import run_review

    show(asyncio.run(run_review(packet, config, output, proof)))


@analysis_app.command("review-accept")
def analysis_review_accept(
    summary: Annotated[Path, typer.Option()],
    runtime: Annotated[Path, typer.Option()],
    sacct: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Accept completed development validation using measured runtime and Slurm evidence."""
    from agent_safety_monitoring.analysis.model_review import accept_development

    show(accept_development(summary, runtime, sacct, output))


@analysis_app.command("retention")
def analysis_retention(
    data: Annotated[Path, typer.Option()],
    run_root: Annotated[Path, typer.Option()],
    freeze: Annotated[Path, typer.Option()],
    review_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Aggregate model-reference retention, without claiming human evidence verification."""
    from agent_safety_monitoring.analysis.model_review import annotation_retention

    show(annotation_retention(data, run_root, read_json(freeze), review_root, output))


@analysis_app.command("replacement")
def analysis_replacement(
    data: Annotated[Path, typer.Option()],
    run_root: Annotated[Path, typer.Option()],
    freeze: Annotated[Path, typer.Option()],
    review_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Exploratory replay of the frozen judge on complete model-suggested evidence."""
    import asyncio

    from agent_safety_monitoring.analysis.model_review import replacement_run

    show(asyncio.run(replacement_run(data, run_root, read_json(freeze), review_root, output)))


@analysis_app.command("structural-check")
def analysis_structural_check(
    data: Annotated[Path, typer.Option()],
    expected: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Recompute structural baseline points using development-only fitting."""
    from agent_safety_monitoring.analysis.records import verify_structural

    show(verify_structural(data, expected, output))


@analysis_app.command("historical-eae")
def analysis_historical_eae(
    data: Annotated[Path, typer.Option()],
    run_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Inspect real saved development repair outputs without new inference."""
    from agent_safety_monitoring.analysis.records import development_eae

    show(development_eae(data, run_root, output))


@analysis_app.command("diagnosis")
def analysis_diagnosis(
    freeze: Annotated[Path, typer.Option()],
    repository: Annotated[Path, typer.Option()],
    data: Annotated[Path, typer.Option()],
    run_root: Annotated[Path, typer.Option()],
    sacct: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    replicates: int = 2000,
):
    """Audit saved frozen results and reconstruct ROC/branch metrics without inference."""
    from agent_safety_monitoring.analysis.diagnosis import run_diagnosis

    result = run_diagnosis(freeze, repository, data, run_root, sacct, output, replicates)
    show({"output": str(output), "freeze": result["freeze"], "replicates": replicates})


@experiment_app.command("followup")
def experiment_followup(
    original_freeze: Annotated[Path, typer.Option()],
    config: Annotated[Path, typer.Option()],
    data: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    split: str = "development",
    limit: int | None = None,
    shard: int = 0,
    shards: int = 1,
    frozen: Path | None = None,
):
    """Run the versioned exploratory score-scale/N study; original artifacts stay read-only."""
    import asyncio

    from agent_safety_monitoring.experiments.followup import run_followup

    show(
        asyncio.run(
            run_followup(data, original_freeze, config, output, split, limit, shard, shards, frozen)
        )
    )


@experiment_app.command("followup-context")
def followup_context(
    original_freeze: Annotated[Path, typer.Option()],
    config: Annotated[Path, typer.Option()],
    data: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Check both scoring prompts with the pinned tokenizer, including retry reserve."""
    from agent_safety_monitoring.experiments.followup import context_preflight

    show(context_preflight(data, original_freeze, config, output))


@experiment_app.command("followup-freeze")
def followup_freeze(
    selection: Annotated[Path, typer.Option()],
    development_root: Annotated[Path, typer.Option()],
    context: Annotated[Path, typer.Option()],
    runtime: Annotated[Path, typer.Option()],
    sacct: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Freeze the follow-up using completed real development and allocation evidence."""
    from agent_safety_monitoring.experiments.followup import freeze_followup

    show(freeze_followup(development_root, context, runtime, sacct, output, selection))


@experiment_app.command("followup-cache")
def followup_cache(
    run_root: Annotated[Path, typer.Option()],
    original_freeze: Annotated[Path, typer.Option()],
    data: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Copy compatible saved original calls into a separate follow-up request cache."""
    from agent_safety_monitoring.experiments.followup import seed_cache

    show(seed_cache(run_root, original_freeze, data, output))


@analysis_app.command("followup-report")
def analysis_followup_report(
    run_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    replicates: int = 2000,
):
    """Require complete follow-up coverage before evaluating nested sample counts."""
    from agent_safety_monitoring.experiments.followup import followup_report

    show(followup_report(run_root, output, replicates))


@analysis_app.command("diagnosis-render")
def analysis_diagnosis_render(
    source: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    replay: Path | None = None,
):
    """Render aggregate-only diagnosis reports and figures."""
    from agent_safety_monitoring.analysis.diagnosis_report import render

    show(render(source, output, replay))


@analysis_app.command("source-replay")
def analysis_source_replay(
    repository: Annotated[Path, typer.Option()],
    data: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Compare all canonical records and labels against the raw Inspect logs."""
    from agent_safety_monitoring.analysis.source_replay import replay

    show(replay(repository, data, output))


@analysis_app.command("calibration-shift")
def analysis_calibration_shift(
    data: Annotated[Path, typer.Option()],
    run_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Describe benign population differences with whole-task uncertainty."""
    from agent_safety_monitoring.analysis.calibration_shift import analyze

    show(analyze(data, run_root, output))


@analysis_app.command("followup-select")
def analysis_followup_select(
    run_root: Annotated[Path, typer.Option()],
    measurements: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
):
    """Select fixed scale/N policies using development tasks and physical cost."""
    from agent_safety_monitoring.analysis.followup import select_development

    show(select_development(run_root, measurements, output))


@analysis_app.command("joint-structural")
def analysis_joint_structural(
    data: Annotated[Path, typer.Option()],
    run_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    replicates: int = 2000,
):
    """Evaluate joint length/tool overlap using a fixed development grid."""
    from agent_safety_monitoring.analysis.joint_structural import analyze

    show(analyze(data, run_root, output, replicates))


@experiment_app.command("followup-timing")
def experiment_followup_timing(
    data: Annotated[Path, typer.Option()],
    original_freeze: Annotated[Path, typer.Option()],
    config: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    ids: Annotated[Path, typer.Option()],
    gpus: int = 1,
):
    """Measure eight cold development workloads in a real GPU allocation."""
    import asyncio

    from agent_safety_monitoring.experiments.followup_timing import benchmark

    show(asyncio.run(benchmark(data, original_freeze, config, output, ids, gpus)))


@analysis_app.command("followup-figures")
def analysis_followup_figures(
    source: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    measurements: Path | None = None,
):
    """Render aggregate follow-up figures; measured cost is optional and explicit."""
    from agent_safety_monitoring.analysis.followup_figures import render

    show(render(source, output, measurements))


if __name__ == "__main__":
    app()
