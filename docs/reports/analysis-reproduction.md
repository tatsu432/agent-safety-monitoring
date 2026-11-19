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
  --features runs/analysis/feature-shift.json --output runs/analysis/regenerated-reports
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

If the reusable Yale SSH connection has expired, complete Duo using `ssh yale-hpc-cpsc4710` and retain a ControlMaster connection.
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

The accepted indexed-passage configuration is `configs/analysis/model-review-repair-2.json`. Download its
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
The repaired indexed-passage configuration was physically validated on an H200.

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
an output directory. It replays the original frozen judge and was physically executed on the selected diagnostic sample. Preserve failures and report all exclusion/status counts.

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

After recovering the original cold screen, verify its accepted proof and export
numeric-only measurements:

```bash
uv run --locked python scripts/analysis/cold_screen.py \
  --measurement runs/yale-recovered/selected-cold-measurements.json \
  --acceptance "$ASM_SOURCE/runs/readiness/accepted-readiness.json" \
  --output docs/reports/cold-screen-aggregate.json
```


Recompute paired evidence-replacement rates from the recovered private outputs:

```bash
uv run --locked python scripts/analysis/summarize_replacement.py \
  --run-root "$ASM_RUN" --replacement-root runs/yale-recovered/model-replacement \
  --output docs/reports/model-evidence-paired-summary.json
```

The repaired 800-character indexed-passage reviewer used the locked configuration
`configs/analysis/model-review-repair-2.json`; development and held-out model-review
identities, proofs and source records remain private. The diagnostic used the same
fixed sample selected before annotation. Repeating it is not needed to reproduce
aggregate analyses. The full allocation summary is generated from project-filtered
Slurm data using `scripts/analysis/resource_summary.py`; individual logs remain
private. The published [resource summary](resource-accounting.json) records the
accounting-input hash and follow-up allocation totals.

The aggregate generator writes baseline report templates to the requested output
folder. The checked-in research report and specialized analyses incorporate the
subsequent full-record and model-evidence findings; do not overwrite them with the
older aggregate-only templates. The figure and table scripts above reproduce the
relevant numeric artifacts independently.

For the November 3 accounting snapshot, the underlying private `sacct -X` file
was parsed with the existing `asm experiment resource-usage` command. Reproduce
the public summary from that private file and parsed allocation artifact with:

```bash
uv run --locked python scripts/analysis/resource_summary.py \
  --allocation runs/yale-recovered/allocation-final-nov3.json \
  --accounting runs/yale-recovered/sacct-final-nov3.txt \
  --follow-up 31619759 31802302 31802796 31802993 31804042 \
  --output docs/reports/resource-accounting.json
```

## November 10 joint sensitivity and controlled follow-ups

Run the joint analysis from an isolated checkout against the recovered original run:

```bash
uv run --locked asm analysis joint-structural --data "$ASM_SOURCE/data/prepared" \
  --run-root "$ASM_RUN" --output runs/extra-check/joint-structural.json
uv run --locked python scripts/analysis/joint_structural_report.py \
  --source runs/extra-check/joint-structural.json --output runs/extra-check/report
```

The checked-in `joint-structural-aggregate.json` contains aggregate cells, intervals,
feature means and hashes, with no record identifiers or source text. Bootstrap
conditions on the development-fitted baselines and boundaries; matching is not
causal identification. Rendering that artifact requires no benchmark records.

Follow-up CLI additions are `experiment followup-timing`, `analysis followup-select`,
`analysis followup-report` and `analysis followup-figures`. Timing takes a private JSON
list of exactly 40 development IDs with `--ids`. Selection takes the complete
150-record development output via `--run-root` and physical timing artifact via
`--measurements`. A held-out `experiment followup-freeze` now also requires
`--selection`, binding development selection and full coverage before inference.
The physical three-record pilot alone does not authorize a held-out freeze.

After all eight held-out shards per split are complete:

```bash
uv run --locked asm analysis followup-report --run-root runs/extra-check/scoring \
  --output runs/extra-check/scoring-report.json
uv run --locked asm analysis followup-figures --source runs/extra-check/scoring-report.json \
  --measurements runs/extra-check/timing/measurements.json --output runs/extra-check/figures
uv run --locked python scripts/analysis/seed_variability.py --base runs/extra-check
```

Follow-up report and selection artifacts contain private provenance paths/IDs;
keep them under `runs/`. Only vetted aggregate fields and figures may be published.
The dependency continuation uses existing `submit.py`, explicit attempt identities,
project accounting, full-coverage checks and separate physical acceptance. Inspect
`runs/extra-check/continuation.json` and the ledger before any manual recovery.
Cold timing trials intentionally regenerate requests for measurement; primary
follow-up inference imports exact compatible original calls and never restarts a
completed cold trial as if it were independent.

## Report PDF packaging

The report renderer reads public Markdown and figure files only. Its optional
report-only dependencies are pinned separately in
`configs/environment/report-renderer.json`; `uv run --locked` preserves the core
experiment lock. They are not installed into the active Yale inference checkout.

```bash
uv run --locked --with reportlab==5.1.0 python scripts/analysis/render_report.py \
  --source docs/reports/final-report.md \
  --append docs/reports/joint-structural-sensitivity.md \
  --output output/pdf/monitoring-study-draft.pdf
```

The current 11-page PDF is a visually inspected **draft**, with follow-up synthesis
pending in its footer. Final submission packaging requires the outstanding model
results and scientific review. Render each page with pinned `pypdfium2==5.15.2` or
Poppler and visually inspect before delivering a revision. Outputs and QA images
remain in ignored `output/` and `tmp/` directories.

### Active inference snapshot

The running Yale inference sources remain at **`5806d2a`**, with the versioned
analysis-controller update for canonical context serialization. Do not pull later analysis changes
into it while timing, development, or held-out jobs are active: source identities
are checked across the workflow. Later analysis can run in a separate checkout.
For paired comparisons with original think-longer, EaE and MRT, the newer
`analysis followup-report` also accepts `--original-run "$ASM_RUN"`; it verifies the
original freeze and common cohort before sharing task-bootstrap draws. This
postprocessing does not change the frozen monitoring procedures or calibrations.

Context acceptance compares normalized ModelConfig values, including declared
defaults. For the fixed inference snapshot's older raw-dictionary check, the
controller writes `context-canonical.json` only after confirming this equivalence.
It retains the original context audit, records its SHA-256, and preserves all prompt
counts, coverage and overflow checks. This is serialization reconciliation, not
permission to change model settings or mark an unvalidated runtime as accepted.

## Strengthened scoring and evidence analysis

Use the original prepared dataset and original completed study (above). Recover
the continuation directory `runs/extra-check/` from the project-owned Yale
checkout `agent-safety-monitoring-extra-check`. Keep source data, caches, receipts,
and per-record outputs in ignored private paths. For the offline replay the
`cache/` and `wandb/` subdirectories are unnecessary.

```bash
export ASM_FOLLOWUP=runs/recovered/extra-check
export ASM_PRIVATE=runs/strengthen
export ASM_RAW="$ASM_SOURCE/data/raw"
export ASM_DATA="$ASM_SOURCE/data/prepared"
mkdir -p "$ASM_PRIVATE"
uv run --locked --extra data --extra tokenizer python scripts/analysis/strengthen_report.py \
  --recovered "$ASM_FOLLOWUP" --original-freeze "$ASM_ORIGINAL" \
  --original-repo "$ASM_SOURCE" --data "$ASM_DATA" --original-run "$ASM_RUN" \
  --private-output "$ASM_PRIVATE" --output docs/reports/strengthened-scoring.json
uv run --locked --extra data python -c \
  'import os; from pathlib import Path as P; from agent_safety_monitoring.analysis.visibility import audit_visibility; audit_visibility(P(os.environ["ASM_RAW"]), P("docs/reports/trajectory-visibility.json"))'
HF_HUB_OFFLINE=1 uv run --locked --extra tokenizer python -c \
  'import os; from pathlib import Path as P; from agent_safety_monitoring.analysis.evidence_diagnostics import summarize_evidence; summarize_evidence(P(os.environ["ASM_DATA"]), P(os.environ["ASM_RUN"]), P(os.environ["ASM_ORIGINAL"]), P("docs/reports/strengthened-scoring.json"), P("docs/reports/strengthened-evidence.json"))'
uv run --locked asm analysis followup-figures --source "$ASM_PRIVATE/scoring.json" \
  --measurements "$ASM_FOLLOWUP/timing/measurements.json" --output docs/reports/figures
uv run --locked python scripts/analysis/strengthen_figures.py \
  --scoring docs/reports/strengthened-scoring.json \
  --evidence docs/reports/strengthened-evidence.json --output docs/reports/figures
uv run --locked --with reportlab==5.1.0 python scripts/analysis/render_report.py \
  --source docs/reports/final-report.md --output output/pdf/monitoring-study.pdf \
  --status 'Verified results and exploratory follow-up'
pdftoppm -png output/pdf/monitoring-study.pdf tmp/pdfs/page
```

The aggregate replay checks both freezes and archived result digests, and
compares historical values within absolute floating-point tolerance of 1e-12.
It uses no inference backend. The quote and summary length analysis requires
the frozen tokenizer revision `6cee5e81ee83917806bbde320786a8fb61efebee` in
the local Hugging Face cache. Public outputs carry aggregate counts and
input digests. W&B receives a fixed scalar allowlist via
`scripts/analysis/publish_strengthened.py`.

For a new development diagnostic, use the original pinned serving environment,
the isolated source snapshot, `ASM_ACTION=development-diagnostic`,
`ASM_DIAGNOSTIC_CONFIG=configs/followup/diagnostics.json`, and
`ASM_DIAGNOSTIC_IDS="$ASM_FOLLOWUP/screen-ids.json"`. Set
`ASM_DIAGNOSTIC_CONDITION` to one versioned condition and submit through
`scripts/yale/submit.py` with the reconciled project ledger and cap. A
previously validated Python environment may be mounted read-only by setting
`ASM_CLIENT_PYTHON` after comparing `uv.lock` bytes. The launcher validates
the runtime against the original freeze. Each condition records identity,
validity, costs and decision latencies separately.

Prepare the matched evidence-intervention packet on CPU:

```bash
uv run --locked python scripts/analysis/evidence_intervention.py \
  --data "$ASM_DATA" --freeze "$ASM_ORIGINAL" --recovered "$ASM_FOLLOWUP" \
  --original "$ASM_RUN" --packet "$ASM_PRIVATE/evidence-intervention-packet.json"
```

Stage that private packet and supply its path as `ASM_EVIDENCE_PACKET` with
`ASM_ACTION=evidence-intervention`. The launcher records the private score
for each highlighted-transcript review and an aggregate matched-case summary.
The aggregate retains source-checked model provenance and the exploratory
fixed EaE-policy interpretation.

The medium-effort held-out inference is an additional, separately frozen
exploratory study. Recover its private `runs/strengthen/heldout/` directory and
the accepted `think-heldout-freeze-v2.json`, then run:

```bash
uv run --locked python scripts/analysis/medium_holdout_report.py \
  --root runs/strengthen/heldout \
  --plan runs/strengthen/think-heldout-freeze-v2.json \
  --data "$ASM_DATA" --followup "$ASM_FOLLOWUP/scoring" \
  --original "$ASM_RUN" --output docs/reports/medium-holdout.json
```

The replay validates both split identities, exact result coverage, freeze-bound
source hashes, invalid counts, and 2,000 paired task bootstraps at each target.
The original allocation checkpointed six reviews short. Its successful retry
reused the completed records. Workload durations in the final split summaries
describe the retry invocation and must not be treated as full-cohort GPU time.
