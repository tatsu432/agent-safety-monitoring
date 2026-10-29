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

## Development configurations and physical pilot

```bash
uv run asm experiment configure --output runs/development-config.json
uv run --extra tokenizer asm data context --model-config configs/model/gpt-oss-20b.json
```

The composer combines separate science, model, hardware, environment and logging
files. The ten initial development configurations cover both effort settings,
2/3/5 repetitions, 1K/3K quotations, and 5/10 interaction chunks. Hardware and
engine values remain explicitly unverified until inspected. W&B is optional;
use `--extra tracking` for online/offline tracking, or logging mode `disabled`.

`asm experiment benchmark --config CONFIG --gpus N --limit K` requires Slurm and
a loaded real server. It uses fresh request caches for each homogeneous method
workload. The wrapper records startup, workload duration, exit status and GPU
telemetry. Prefix caching is disabled for the initial controlled timing study.
Actual allocation time from sacct remains authoritative, including failed jobs.
No workload estimate or script has yet been validated on Yale in this project.

A real freeze requires checksummed proof artifacts in the resolved study config:

```json
{
  "cohort_audit": {"path": "data/prepared/context-audit.json", "sha256": "ACTUAL_SHA256"},
  "pilot_measurement": {"path": "runs/pilot/pilot-measurements.json", "sha256": "ACTUAL_SHA256"},
  "budget_approval": {"approved_by": "user", "gpu_hours": 0}
}
```

The zero is a placeholder and is rejected. Record the actual user-approved total
cap after the pilot. Accept the pilot only after checking all methods, low/medium/high
reasoning, short/median/longest development cases, valid final answers, GPU mapping,
peak memory, workload timing and resume. Preserve the original measurements and
record acceptance as a separately versioned artifact with `backend_validated: true`.
Also set the verified hardware profile and engine version. Context proof must match
model/tokenizer revisions, limits and the current manifest; every included source
must fit. A freeze protects dependency locks as well as Python source and prompts.

## Secondary diagnostics

After frozen primary results exist:

```bash
uv run asm experiment structural --frozen runs/study-freeze.json \
  --run-root RUN_DIRECTORY --output runs/structural
uv run asm experiment injections --frozen runs/study-freeze.json \
  --primary-report runs/report/metrics.json --output runs/secondary
```

Structural models fit development features only. The length diagnostic uses bins
chosen from development lengths, class-balanced weights inside each bin, overlap
reporting, and task-cluster bootstrap with recalibration. Injection thresholds must
come from the same frozen study. The sample IDs, token-matched neutral controls,
payloads and methods are frozen; authentic evidence remains unchanged. The runner
saves paired outcomes and generates an injection figure.

Independent reference annotations for missed-attack evidence remain a human or
separately audited grader-evidence task. `evaluation.evidence.retention` validates
exact annotated spans and checks retention/citations; it does not invent reference
evidence or infer semantic understanding from a missing citation.
