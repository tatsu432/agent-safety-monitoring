# Analysis reproduction and remaining cluster work

Run from the analysis checkout. The original checkout and its ignored artifacts
remain unchanged. `ASM_SOURCE` below identifies the existing local source bundle.

```bash
uv sync --locked --extra data --extra tokenizer --extra tracking
export ASM_SOURCE=../agent-safety-monitoring
uv run --locked asm analysis audit \
  --freeze "$ASM_SOURCE/runs/readiness/study-freeze.json" \
  --repository "$ASM_SOURCE" --data "$ASM_SOURCE/data/prepared" \
  --output runs/analysis/artifact-audit.json
uv run --locked asm analysis features --data "$ASM_SOURCE/data/prepared" \
  --output runs/analysis/feature-shift.json
uv run --locked asm analysis structural-check --data "$ASM_SOURCE/data/prepared" \
  --expected "$ASM_SOURCE/runs/full-study/structural/structural-diagnostics.json" \
  --output runs/analysis/structural-verification.json
uv run --locked asm analysis aggregate --bundle "$ASM_SOURCE/runs/full-study" \
  --freeze "$ASM_SOURCE/runs/readiness/study-freeze.json" \
  --features runs/analysis/feature-shift.json --output docs/reports
```

Aggregate generation defaults to online W&B and exports a fixed allowlist of
numeric summary metrics. Tracking failure does not invalidate local results.
For a repeated reproducibility check, add `--tracking-mode disabled` to avoid a
duplicate cloud run. No per-record arrays, quotes, model text, or raw inputs are
uploaded. `analysis-aggregates.json` stores the exact source-file hashes.

Historical development EaE analysis uses an earlier repair screen, not the final
cold selection or held-out results:

```bash
uv run --locked --extra tokenizer asm analysis historical-eae \
  --data "$ASM_SOURCE/data/prepared" \
  --run-root "$ASM_SOURCE/runs/readiness/eae-repair/trials/eae-repair-1/method-1/ad2e2b0c590caac136998f239973b9da7a955fd75a9b2895b28901553a4aeaf5" \
  --output runs/analysis/historical-eae-aggregate.json
```

The report's historical aggregate was copied from that numeric output. The
artifact-audit prose records the corresponding local audit. Generated report
narrative describes this particular study; its claims must be revised when
verification status changes. Aggregate figures are reproducible from summaries;
objective intervals, score histograms, and ROC regeneration require full records.
The original saved ROC is copied unchanged with its hash recorded.

## Full prediction reconciliation

Yale noninteractive SSH currently fails with keyboard-interactive authentication.
Complete Duo using `ssh yale-hpc-cpsc4710` and retain a ControlMaster connection.
Before any GPU action, inspect current permissions, personal project/scratch
storage, `squeue --me`, the completion/controller record, submission ledger, and
project-filtered `sacct -X` entries including failed jobs. Do not submit duplicates.

Recover the full frozen run and annotation sample with checksummed private copies.
The documented frozen checkout is
`/nfs/roberts/project/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring-frozen-prep`.
Discover its actual single `study.json` under `runs/study/`; do not assume the run
folder name. Preserve all original artifacts. Set `ASM_RUN` to that recovered
study directory, then run:

```bash
uv run --locked --extra tokenizer asm analysis records \
  --freeze "$ASM_SOURCE/runs/readiness/study-freeze.json" \
  --repository "$ASM_SOURCE" --data "$ASM_SOURCE/data/prepared" \
  --run-root "$ASM_RUN" --output runs/analysis/full-records
```

This validates coverage/evaluation metadata against the frozen manifest before
recomputing metrics and objective intervals. Private diagnostic rows remain under
`runs/`. Reconcile regenerated metrics numerically with the original summaries.
The unchanged original checkout must separately pass its original freeze validator
with the original Python 3.12.15 environment; analysis code does not weaken that gate.

## Local model evidence review

The pinned configuration is `configs/analysis/model-review.json`. Download its
exact 120B revision into this project's model cache without exposing records to
any service. Verify storage/quota and prepare the locked client before allocating
GPUs. The launcher uses the original digest-verified vLLM image, but 120B memory
and context compatibility remain untested. Model download is not GPU validation.

```bash
uv run --locked asm analysis review-prepare \
  --freeze "$ASM_SOURCE/runs/readiness/study-freeze.json" \
  --data "$ASM_SOURCE/data/prepared" --development \
  --output runs/analysis/development-review-packet.json
```

Stage the analysis checkout and private packet on Yale. Use the existing
`submit.py` ledger with the original project ledger path, current project account/
partition, measured consumed total, and documented cap. Set `ASM_REVIEW_PACKET`,
`ASM_REVIEW_OUTPUT`, `ASM_REVIEW_CONFIG`, `ASM_IMAGE`, and project `HF_HOME` to
absolute cluster paths. Submit `scripts/analysis/model-review.sbatch` for one H200.
Start with a bounded development allocation; derive subsequent cost and cap
amendments from the measured workload, not an assumed 120B throughput. The wrapper
records runtime and utilization and verifies GPU, image checksum, and engine.
It has been syntax-checked only; no successful physical execution is claimed.

After the development allocation completes, save project-filtered Slurm accounting
with `JobID,State,ElapsedRaw,AllocTRES` and bind it to the measured runtime:

```bash
uv run --locked asm analysis review-accept \
  --summary "$ASM_REVIEW_OUTPUT/summary.json" \
  --runtime "$ASM_REVIEW_OUTPUT/jobs/$ASM_DEV_JOB/runtime.json" \
  --sacct runs/analysis/reviewer-sacct.txt --output runs/analysis/reviewer-accepted.json
uv run --locked asm analysis review-prepare \
  --freeze "$ASM_SOURCE/runs/readiness/study-freeze.json" \
  --data "$ASM_SOURCE/data/prepared" --sample "$ASM_EXISTING_ANNOTATIONS" \
  --output runs/analysis/diagnostic-review-packet.json
```

Do not regenerate the missing original sample with a new selection. Set the
launcher packet/output to the diagnostic locations and `ASM_REVIEW_PROOF` to the
accepted development proof. Resume with unchanged packet/config/output identities.
Valid model interpretations remain unverified; empty/unresolved evidence does not
become human-reviewed. Do not edit proof flags to bypass physical acceptance.

After annotation, run `asm analysis retention` with `--data`, `--run-root`,
`--freeze`, `--review-root`, and private `--output`. A separately accounted local
20B allocation can run `asm analysis replacement` with the same arguments, using
an output directory. It replays the original frozen judge and has not yet been
physically validated. Preserve failures and report all exclusion/status counts.

## Checks

```bash
uv run --locked --extra data --extra tokenizer --extra tracking pytest -q
uv run --locked ruff check src tests
bash -n scripts/analysis/model-review.sbatch
git diff --check
```

Software tests establish analysis safeguards only. They do not establish real GPU
compatibility, reliable model annotations, or scientific effectiveness.

After full-record diagnostics complete, regenerate the aggregate-only EaE table:

```bash
uv run --locked python scripts/analysis/summarize_eae.py \
  --input runs/yale-recovered/full-analysis/record-diagnostics-private.json \
  --output docs/reports/eae-test-extraction-aggregate.json
```

Regenerate record-level figures after completing full-record diagnostics:

```bash
uv run --locked python scripts/analysis/record_figures.py \
  --run-root "$ASM_RUN" \
  --diagnostics runs/yale-recovered/full-analysis/record-diagnostics-aggregate.json \
  --metrics runs/yale-recovered/full-analysis/recomputed/metrics.json \
  --output docs/reports/figures
```

Reproduce the post-hoc component and score-resolution sensitivity:

```bash
uv run --locked python scripts/analysis/score_resolution.py \
  --run-root "$ASM_RUN" --output docs/reports/score-resolution.json
```

Reproduce the descriptive within-task comparisons:

```bash
uv run --locked python scripts/analysis/paired_tasks.py \
  --run-root "$ASM_RUN" --output docs/reports/paired-task-diagnostics.json
```
