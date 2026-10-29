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
def benchmark(
    config: Annotated[Path, typer.Option()],
    gpus: int = 1,
    limit: int = 4,
    data: Path = Path("data/prepared"),
    output: Path = Path("runs/pilot"),
):
    """Measure development workloads inside a Slurm allocation with a loaded server."""
    from agent_safety_monitoring.experiments.benchmark import benchmark as measure

    show(measure(data, output, read_json(config), gpus, limit))


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


@app.command()
def report(
    run_root: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    replicates: int = 2000,
):
    """Generate aggregate results, paired bootstrap intervals, tables and figures."""
    from agent_safety_monitoring.reporting.report import generate

    show(generate(run_root, output, replicates))


if __name__ == "__main__":
    app()
