> **November 1 post-hoc analysis:** the frozen study is reported complete. Do not
> use historical launch commands below to restart completed shards. Current
> aggregate analyses and remaining reconciliation are documented in
> [the analysis runbook](reports/analysis-reproduction.md). New analysis runs use a
> separate checkout; the frozen runtime and proofs remain unchanged.

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
The former four-hour pilot cap is historical. The user authorizes GPU submissions
needed for this project without further approval; maintain measured accounting and
a documented resource cap, updating it based on evidence when necessary.
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
Yale H200 compatibility and development execution have been exercised. The revised
3K EaE screen meets the validity limit, and comparable cold timing and final selection
were completed. See the readiness report for the exact evidence.

A real freeze requires checksummed proof artifacts in the resolved study config:

```json
{
  "cohort_audit": {"path": "data/prepared/context-audit.json", "sha256": "ACTUAL_SHA256"},
  "pilot_measurement": {"path": "runs/pilot/accepted-readiness.json", "sha256": "ACTUAL_SHA256"},
  "budget_approval": {"approved_by": "user", "gpu_hours": 0}
}
```

The zero is a placeholder and is rejected. Record a measured total cap under the
user’s standing authorization; do not represent an agent-selected number as
user-specified. Accept the pilot only after checking all methods, low/medium/high
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

Prepare a stratified independent annotation file only after primary results exist:

```bash
uv run asm experiment annotation-sample --frozen runs/study-freeze.json \
  --run-root RUN_DIRECTORY --primary-report runs/report/metrics.json \
  --output runs/annotations.json
# Review canonical records locally and enter exact source spans with provenance.
uv run asm experiment annotation-report --frozen runs/study-freeze.json \
  --run-root RUN_DIRECTORY --annotations runs/annotations.json --output runs/evidence.json
```

Sample selection includes detected/missed outcomes, objectives and length bins.
Annotation templates do not show monitor-selected evidence or scores. Spans are
verified against canonical text before aggregation; unresolved annotations remain
unreviewed and are not fabricated. Keep annotation files private with run artifacts.

After a completed development benchmark, `asm experiment select --measurements
runs/pilot/trials/default/pilot-measurements.json --config runs/development-config.json --output
runs/selection.json` selects one feasible configuration per method/budget using
only development outcomes. Small budget is twice measured single-review cost;
large is at least small and at least the cheapest feasible configuration of every
available method. Selection maximizes valid-score development AUROC, requires at
least ten valid records per class and at most 5% invalid outputs, and uses invalid rate, cost and configuration hash as
tie-breakers. Unavailable methods remain explicit. Review the result, copy its
`configuration` object into the study configuration, and add the verified
prerequisite proofs and the measured full-study cap before freezing.

## Pre-main readiness, progress and recovery

Use the locked environment (`uv sync --locked --extra data --extra tokenizer --extra tracking`).
W&B defaults to **online**, with aggregate scalars only. Supply credentials through an
existing protected environment or W&B credential store, never a command argument.
`ASM_TRACKING_MODE=offline` keeps local W&B events for later `wandb sync DIRECTORY`;
**offline does not provide a live cloud dashboard**. `ASM_TRACKING_MODE=disabled`
needs no W&B import in the runner. Tracking failures preserve local computation.
Unique attempt runs share the study hash as their W&B group; offline resume is not used.

```bash
uv run --locked asm experiment status --run-root RUN_DIRECTORY
squeue --me
sacct -j JOB_ID -X --format=JobID,State,ElapsedRaw,AllocTRES --parsable2
nvidia-smi  # inside your allocation only
```

Status snapshots update every 30 seconds and include method progress, retries, token
usage, cache reuse, estimated remaining time and job IDs. An old heartbeat is not proof
a job is alive. Local result files remain authoritative. A successful allocation exit
alone does not establish scientific completion: inspect `state`, `expected`, and
`completed_results` in the shard summary and run the coverage-checking report.

Repeat the exact `experiment run` command to resume. Keep the same split, shard count,
selected development limit and configuration. Kernel locks reject duplicate shard workers.
Malformed files are renamed with `.corrupt-ATTEMPT` before regenerating; valid incompatible
files fail explicitly. Completed scientific invalid judgments stay completed. Infrastructure
failures remain private attempt artifacts and are retried on resume. Request caches retain
compatible completed stages. Journals preserve in-flight and finished calls after crashes.
Logical costs include reused calls; physical attempt costs count only new requests.

```bash
uv run --locked --extra tokenizer asm experiment diagnose --run-root DEVELOPMENT_RUN \
  --data data/prepared --output runs/private-eae-diagnostics.json
uv run --locked asm experiment resource-usage --sacct-file runs/sacct.txt \
  --output runs/allocation-usage.json
uv run --locked asm experiment cost-estimate --measurements MEASUREMENTS.json \
  --output runs/remaining-cost.json
```

Diagnosis is development-only and writes private identifiers locally. Never commit or
upload its detailed records. Allocation input must be `sacct -X --parsable2` with
`JobID,State,ElapsedRaw,AllocTRES`, filtered to this project's jobs. Count failed jobs.
Cost estimates state assumptions, include supplementary records and injection controls,
and are not approvals. Replace provisional rates after repaired-method measurements.

## Stable development benchmarks and submission ledger

```bash
uv run --locked --extra tokenizer asm experiment benchmark --config CONFIG.json \
  --data data/screen --output runs/readiness --limit 40 --gpus 1 --trial-id eae-repair-1
```

This requires an allocated GPU and loaded local server. Repeat the same trial ID and
arguments to recover missing work; completed trials are skipped. Choose a new explicit
trial ID for an independent cold-cache measurement. Changed configurations require a
new identity. Resumed timing trials retain useful work but are marked ineligible for
cold timing selection; preserve their GPU costs in the allocation ledger.

On Yale, prepare data/configuration before requesting a GPU. The benchmark wrapper
accepts `ASM_BENCHMARK_METHODS=eae`, `ASM_BENCHMARK_FIRST_ONLY=1`, `ASM_LIMIT`,
`ASM_TRIAL_ID`, `ASM_OUTPUT`, `ASM_DATA`, `ASM_SCIENCE_CONFIG`, `ASM_TRACKING_MODE`, and the existing
`ASM_SCRATCH`. Its generated configuration is private inside `ASM_OUTPUT`.
The wrappers request a 900-second shutdown warning. Python stops new work and drains
for at most 840 seconds (`ASM_DRAIN_SECONDS` may lower this); call journals and exact
request caches survive cancellation. Cleanup stops only this wrapper's own children.

Use the submission ledger rather than retrying `sbatch` after ambiguous SSH output:

```bash
uv run --locked python scripts/yale/submit.py --ledger runs/submissions.json \
  --identity eae-repair-1 --gpus 1 --minutes 20 --cap-hours 4 -- \
  --account=cpsc4710 --partition=VERIFIED_PARTITION --mem=48G --cpus-per-task=4 \
  --output=logs/eae-repair-%j.out scripts/yale/benchmark.sbatch
```

The partition must come from current permissions. All environment settings should
already be exported. The wrapper checks Slurm comments and recorded submission identity,
records intent before submission, rejects ambiguous retries and checks the requested
allocation against consumed GPU time. It conservatively refuses when other jobs are active.
Use a fresh attempt identity only after confirming existing scientific coverage and Slurm
state. A completed but incomplete scientific run needs that explicit reconciliation.

## Freeze and launch gate

`experiment select` rejects incomplete or incompatible real timing trials and resumed
cold measurements. Budget membership is preserved in the selected configuration.
Reports add `gpu-cost-performance.csv`, `budget-performance.json`, and, when measured
budget mappings exist, `gpu-cost-detection.png`. Its x-axis is measured **development**
GPU cost; it is not a fabricated held-out allocation measurement.

Create the real freeze with the same client Python patch version used for Yale
inference; that version is recorded and checked. The Slurm wrapper also checks frozen
GPU name/count, tensor parallelism, context, concurrency, revision and container checksum
before server startup.

Real freeze acceptance additionally requires the accepted pilot artifact to name
`feasible_method_hashes` (digests of normalized method configs), the exact `model` and
`hardware` configurations, plus `backend_validated: true`. The environment must contain
verified `container_sha256` and immutable registry `container_digest`. Acceptance remains
a reviewed, versioned artifact; never set these fields just to bypass the gate.

After those checks and the measured full-study cap are recorded:

```bash
uv run --locked asm experiment freeze --config STUDY.json --output runs/study-freeze.json
# On allocated compute nodes with the matching pinned local server:
uv run --locked --extra tokenizer asm experiment run --frozen runs/study-freeze.json \
  --data data/prepared --output runs/study --split calibration
uv run --locked --extra tokenizer asm experiment run --frozen runs/study-freeze.json \
  --data data/prepared --output runs/study --split test
uv run --locked asm report --run-root RUN_DIRECTORY --output runs/report
```

For Slurm use `inference.sbatch` with `ASM_FREEZE`, `ASM_SPLIT`, `ASM_SHARD`,
`ASM_SHARDS`, and the verified runtime settings from the runbook. Keep shard geometry
fixed across restarts. Source, lock and Yale execution scripts are protected by the freeze.


## Authorized development measurement

The user authorized continued GPU use without further approval requests on October 29.
The following five-method development job was submitted as **31312445** with a
**6.5 GPU-hour** project cap (2.5 hours beyond the original four). The five-setting candidate config excludes the known-infeasible 1K setting;
it does not claim final scientific selection. The same fixed 40-record cohort is used.
The submission used the following environment and command:

```bash
cd /nfs/roberts/project/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring-readiness
export ASM_SCRATCH=/nfs/roberts/scratch/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring
export ASM_DATA=data/screen ASM_OUTPUT=runs/selected-cold ASM_LIMIT=40
export ASM_SCIENCE_CONFIG=configs/science/readiness-screen.json ASM_TRIAL_ID=selected-cold-1
export ASM_BENCHMARK_METHODS=single,think,average,eae,mrt ASM_BENCHMARK_FIRST_ONLY=1
export ASM_TRACKING_MODE=online ASM_DRAIN_SECONDS=60
.venv/bin/python scripts/yale/submit.py --ledger runs/readiness/submissions.json \
  --identity selected-cold-1 --gpus 1 --minutes 150 --cap-hours 6.5 -- \
  --account=cpsc4710 --partition=gpu_h200 --signal=B:USR1@120 \
  --mem=48G --cpus-per-task=4 --output=logs/selected-cold-%j.out scripts/yale/benchmark.sbatch
# Only after complete cold timings and coverage have been verified:
.venv/bin/asm experiment select \
  --measurements runs/selected-cold/trials/selected-cold-1/pilot-measurements.json \
  --config runs/selected-cold/development-config.json --output runs/selection.json
```

This bounded development job uses the short warning rather than the long-run default
so the warning does not stop scheduling 15 minutes before a 150-minute allocation ends.
If the measured workload still exceeds its limit, preserve and report incomplete timing;
do not reinterpret a resumed trial as an independent cold benchmark.

## Current frozen Yale launch procedure

The frozen checkout is at source commit `a0fd3fd`; the source hashes and Python
patch version are fixed by `runs/study-freeze.json`. The current readiness assessment
and 90 allocated GPU-hour total cap are in the [readiness report](reports/pre-main-experiment-readiness.md).
Calibration job `31347741` was submitted after the user authorized full execution.
Dependent controller `31347875` verifies each completed shard and starts the next
within the 90-hour cap. The manual commands below are recovery instructions; do
not submit duplicates while the controller chain is active.

Set the verified environment in a Yale shell, from the clean frozen checkout:

```bash
cd /nfs/roberts/project/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring-frozen-prep
mkdir -p logs
export ASM_SCRATCH=/nfs/roberts/scratch/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring
export HF_HOME="$ASM_SCRATCH/huggingface" UV_CACHE_DIR="$ASM_SCRATCH/uv-cache"
export UV_PROJECT_ENVIRONMENT="$ASM_SCRATCH/frozen-inference-venv" UV_OFFLINE=1 HF_HUB_OFFLINE=1
export ASM_IMAGE="$PWD/images/vllm-openai-v0.11.0.sif"
export ASM_IMAGE_SHA256=056a8f8f182b1652c88ecf567d11dfa18a5b0a7ddd33d17b3fcc5d5869731c03
export ASM_MODEL_REVISION=6cee5e81ee83917806bbde320786a8fb61efebee
export ASM_GPUS=1 ASM_TP=1 ASM_CONTEXT=131072 ASM_CONCURRENCY=1
export ASM_FREEZE=runs/study-freeze.json ASM_DATA=data/prepared ASM_TRACKING_MODE=online
export ASM_ACTION=run ASM_OUTPUT=runs/study ASM_SHARDS=8 ASM_DRAIN_SECONDS=840
```

Run **one shard at a time** with the submission ledger. Use `calibration` first,
then `test`; set `ASM_SHARD` to each integer from 0 through 7. For example, this
submits the first calibration shard, with an eight-hour maximum:

```bash
export ASM_SPLIT=calibration ASM_SHARD=0
.venv/bin/python scripts/yale/submit.py --ledger runs/submissions.json \
  --identity "main-${ASM_SPLIT}-${ASM_SHARD}-attempt-1" \
  --gpus 1 --minutes 480 --cap-hours 90 -- \
  --account=cpsc4710 --partition=gpu_h200 --mem=48G --cpus-per-task=4 \
  --output="logs/main-${ASM_SPLIT}-${ASM_SHARD}-%j.out" scripts/yale/inference.sbatch
```

Before submitting the next shard, check `squeue --me`, `sacct -j JOBID -X`,
the shard summary and heartbeat. The ledger refuses to submit when any other user
job is active. A completed allocation does not alone prove full shard coverage;
inspect `state`, `expected` and `completed_results`. If interrupted or incomplete,
inspect the existing results and logs first, then retain the same split, shard,
shard count, output and freeze and use a fresh attempt identity. Never re-run a
completed shard as a new timing trial. Adjust `--minutes` downward if the remaining
cap cannot reserve eight hours. If additional GPU time is needed, reassess and
document an evidence-based revised cap without asking for GPU submission approval. Preserve the frozen science and
record the budget amendment separately rather than changing an existing freeze.

When both splits have complete coverage, find the single `study.json` under
`runs/study/`, set `RUN_ROOT` to its parent directory, and generate the report:

```bash
find runs/study -name study.json -print
export RUN_ROOT=runs/study/REPLACE_WITH_STUDY_ID
.venv/bin/asm report --run-root "$RUN_ROOT" --output runs/report
.venv/bin/asm experiment structural --frozen "$ASM_FREEZE" \
  --data "$ASM_DATA" --run-root "$RUN_ROOT" --output runs/structural
```

For the frozen matched-control injection study, the staged launcher is
`runs/injections.sbatch` (copy of [the reference launcher](reference/yale-injections.sbatch),
SHA-256 `6ebfa1165e63e3fbac8787475de7462a8298021d0609e84920adfe07561d2008`).
It has passed shell syntax checks, but has not been run on a GPU. After generating the
primary report, verify its checksum and submit it within the same cap:

```bash
sha256sum runs/injections.sbatch
export ASM_PRIMARY_REPORT=runs/report/metrics.json ASM_OUTPUT=runs/secondary
.venv/bin/python scripts/yale/submit.py --ledger runs/submissions.json \
  --identity injections-attempt-1 --gpus 1 --minutes 480 --cap-hours 90 -- \
  --account=cpsc4710 --partition=gpu_h200 --mem=48G --cpus-per-task=4 \
  --output=logs/injections-%j.out runs/injections.sbatch
```

On interruption, inspect the per-variant artifacts and logs before retrying; the
injection runner resumes persisted variants but does not have the primary runner's
shard locks or per-attempt W&B telemetry. Submit only one injection job at a time,
retain the same output and freeze, and review infrastructure failures before reuse.
GPU allocation accounting comes from `sacct`, including failed and interrupted jobs.


## Active automated continuation

The controller is `runs/study-controller.py` in the frozen checkout, matching the
[versioned reference](reference/yale-study-controller.py), SHA-256
`d5bf22915e94bdd59267688f53210a094847feec2011e0ddff1a5209c5da6581`.
A dependent CPU job checks the prior Slurm exit, freeze identity and exact saved
shard coverage before starting the next calibration/test shard. It accounts for
all allocated GPU time, reserves each next allocation within 90 total GPU-hours,
records submission intent before `sbatch`, and refuses duplicates or concurrent
user jobs. After test coverage it runs the primary report and structural analysis,
then submits the checksum-verified injection launcher and verifies the matched
variant coverage. Completion is recorded in `runs/study-completion.json`.

The chain deliberately stops on failed/incomplete jobs, ambiguous submissions,
unexpected concurrent jobs, a failed analysis, or an exhausted cap. The standing
GPU authorization permits an evidence-based cap amendment without asking the user.
Inspect `logs/study-controller-*.out`, `runs/submissions.json`, `squeue` and `sacct` before
any manual recovery. A successful submission alone is not evidence of completion.
