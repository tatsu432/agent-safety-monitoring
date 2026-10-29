# Operations

## Local setup and validation

```bash
uv sync --locked --extra data --extra tokenizer
uv run ruff check src tests
uv run pytest -q
uv run asm experiment demo
```

Demo artifacts under `runs/demo/` are synthetic software checks, never research
results. They exercise all methods, frozen calibration/test, intervals and figures.

## Data

```bash
uv run --extra data asm data download
uv run --extra data asm data import data/raw/honest.eval data/raw/attack.eval
uv run asm data audit
uv run --extra tokenizer asm data audit --model-config configs/model/gpt-oss-20b.json
```

Raw sources and canonical evidence stay under ignored `data/`. The source manifest
contains URLs, SHA-256 checksums and retrieval times; the prepared manifest records
per-sample labels, provenance, task splits and exclusions. Inspect them locally.
Public data source: https://control-leaderboard.redwoodresearch.org/data (evaluation
only; not for training or uploads to training-retaining services). Dataset metadata
links CC BY-SA 4.0; preserve source attribution and upstream usage instructions.

## Inference

```bash
uv run asm experiment run --config configs/science/mock.json --limit 1
```

This last command runs MOCK judgments on real development evidence and tests wiring
only. For real inference, pin a verified engine version in the model configuration,
start vLLM on a compute node, and build a study configuration with `model`, `methods`,
and measured readiness artifacts. Never send benchmark transcripts to a hosted API.

Freeze only after development measurements and finalized cohort:

```bash
uv run asm experiment freeze --config STUDY.json --output runs/study-freeze.json
uv run asm experiment run --frozen runs/study-freeze.json --split calibration
uv run asm experiment run --frozen runs/study-freeze.json --split test
uv run asm report --run-root RUN_DIRECTORY --output runs/report
```

Code, prompt, configuration, data-manifest and canonical-evidence hashes are checked
before held-out runs. Changes require a new documented freeze. Outputs are atomic,
resumable per-trajectory files. Shard with `--shard I --shards N`; use consistent N,
separate cache shards, and never launch duplicate jobs. Result directories merge
by unique method/trajectory filenames. Summaries must show complete coverage.

## External resources

Read [Yale HPC](yale-hpc.md). Authorized alias: `yale-hpc-cpsc4710`. Authenticate
normally with Duo. Do not reuse the previous project's resource allowance.
Initial pilot cap is four allocated GPU-hours; larger runs require a measured cap.
Secrets belong in user-owned mode-600 files outside Git, configs and Slurm arguments.
W&B may receive aggregates only. Keep local artifacts authoritative when tracking fails.
