> **November 10 execution update:** Yale access is restored. The physical pilot
> passed with 30/30 valid reviews; homogeneous timing and ledger-backed continuation are queued. The scoring and objective-aware
> follow-ups remain unfinished. See the [current checkpoint](../task_completion/05-extra-check-checkpoint.md).

# Controlled follow-up protocol and execution status

November 8, 2026. These experiments are exploratory: the original test has already
been examined. Fresh-holdout confirmation is optional and must not delay the mandatory
analysis. No new inference has run for this follow-up. Yale currently rejects SSH
with `Permission denied (keyboard-interactive)`; no submission was attempted.

## Hypotheses and decisions

1. Compare five-category versus 0–100 ordinal scoring under unchanged model, rubric,
   temperature 0.2, low reasoning effort, full evidence access, and original serving settings.
   The fine scale changes only score instructions/schema; it is not a probability.
2. Evaluate N=1/2/3/5 from the same five independently seeded reviews at each scale.
   Preserve original seed 20261028 and stride 100. Reuse exact compatible original calls.
   A failed required review invalidates that N; do not average surviving samples.
3. Report calibrated TPR/FPR, valid-score AUROC, test ROC TPR@5%/10%, raw pAUC 0–10%,
   paired task intervals, input/output tokens, new versus reused calls, measured GPU cost,
   and marginal changes with N. Equal-width 0–100 coarsening is a sensitivity analysis.
4. Use all 150 eligible development records, retaining failed/ungraded attacks separately
   from successful-attack discrimination. Compare candidates with five task-grouped folds;
   use pooled out-of-fold AUROC with ≤5% invalidity and measured cost as tie-breaker.
   Do not select on unstable fold-level 5% FPR estimates with only six benign tasks/fold.
5. Repeat the fixed 40-record development screen under seed offsets 10000 and 20000
   to assess inference variability separately from clustered task uncertainty.
6. Preserve the original 30 diagnostic attacks. The prepared objective-aware reviewer
   sees the genuine task, visible transcript, and harmful-objective category as an explicitly
   fallible hypothesis. It sees no success grade, monitor verdict, quotations or sampling strata.
   Validate spans and retain model-suggested provenance. Reuse the pinned 120B local reviewer,
   with a new development acceptance because the reviewer prompt has changed.
7. First run controlled fixed-judge evidence substitution. Only then consider one
   chronology-preserving EaE intervention or a 512→1024 MRT summary-budget change if
   development evidence supports the corresponding mechanism. No broad sweep or adaptive
   cascade is justified now. Negative findings satisfy the scientific objective.

## Measured basis and resource control

Historical accounting is 61.306 allocated GPU-hours; the existing cap is 90 hours.
The single-review cold development rate is 15.30 GPU-seconds per trajectory. With
1,038 calibration/test records, three additional five-level reviews plus five fine
reviews imply about **35.3 additional workload GPU-hours** if fine reviews cost the
same. That is a projection, not a fine-score timing measurement. Full development
and two 40-record seed repeats add roughly 9.8 workload hours under that assumption.
Reference review, startup, failures and contingency are additional.

First measure the real short/median/long development pilot and reconcile current
`sacct` and queue state. Set the revised total cap to consumed allocation plus 1.25
times projected remaining allocation including startup, rounded up to five GPU-hours.
The current projection suggests approximately 120 total hours, but **no cap amendment
has been made and no fine-score throughput is claimed measured**. Standing authorization
permits a documented evidence-based amendment after the pilot; no further GPU approval
is needed. Stop unnecessary workloads and preserve failed-attempt costs.

## Prepared artifacts and commands

Use an isolated checkout and the locked environment:

```bash
uv sync --locked --extra data --extra tokenizer --extra tracking
export ASM_SOURCE=../agent-safety-monitoring
export ASM_RECOVERED=../agent-safety-monitoring-analysis/runs/yale-recovered
export ASM_RUN="$ASM_RECOVERED/study/5b64a37e16b77e48da4707a5428f3b429cebaafe9b94524660bb9ec5776239d3"
export ASM_ORIGINAL="$ASM_SOURCE/runs/readiness/study-freeze.json"

uv run --locked asm analysis source-replay --repository "$ASM_SOURCE" \
  --data "$ASM_SOURCE/data/prepared" --output runs/diagnosis/source-replay.json
uv run --locked asm analysis diagnosis --freeze "$ASM_ORIGINAL" \
  --repository "$ASM_SOURCE" --data "$ASM_SOURCE/data/prepared" --run-root "$ASM_RUN" \
  --sacct "$ASM_RECOVERED/sacct-final-nov3.txt" --output runs/diagnosis
uv run --locked asm analysis diagnosis-render --source runs/diagnosis/diagnosis-aggregate.json \
  --replay runs/diagnosis/source-replay.json --output docs/reports
uv run --locked asm analysis calibration-shift --data "$ASM_SOURCE/data/prepared" \
  --run-root "$ASM_RUN" --output docs/reports/calibration-shift-aggregate.json
uv run --locked asm experiment followup-context --original-freeze "$ASM_ORIGINAL" \
  --config configs/followup/scoring.json --data "$ASM_SOURCE/data/prepared" \
  --output runs/followup/context.json
uv run --locked asm experiment followup-cache --original-freeze "$ASM_ORIGINAL" \
  --run-root "$ASM_RUN" --data "$ASM_SOURCE/data/prepared" --output runs/followup/scoring
```

The context audit covers every included trajectory: zero overflows, maximum 116,619
prompt tokens plus 8,320 reserve within 131,072. This is tokenizer validation, not physical
GPU validation. Private objective-aware packets contain 3 development and 30 diagnostic
records under `runs/followup/`. Regenerate them using `analysis review-prepare` with
`--objective-aware` and separate output paths; existing packets are never overwritten.

After restoring Yale login, inspect current project permissions, quota, queue,
completion records, submission ledger and project-filtered accounting. Use the existing
`submit.py` with an explicit attempt identity and measured cap. Export the original
verified serving settings from operations, then set:

```bash
export ASM_ACTION=followup ASM_FREEZE=/absolute/path/to/original-study-freeze.json
export ASM_FOLLOWUP_CONFIG="$PWD/configs/followup/scoring.json"
export ASM_OUTPUT=/absolute/private/followup-scoring
export ASM_SPLIT=development ASM_SHARD=0 ASM_SHARDS=1 ASM_LIMIT=3
```

Submit `scripts/yale/inference.sbatch` through the ledger. The prepared cache contains 2,081 original request entries, including supplementary
records; six short/middle/long checks confirmed cache hits without server requests.

A development limit samples
across source lengths; limit three selects shortest, middle and longest. The launcher
retains startup/runtime/utilization records. After a successful measured pilot, create a
separate freeze using `experiment followup-freeze --development-root ... --context ...
--runtime ... --sacct ... --output ...`. The runtime is the launcher's
`jobs/JOBID-followup-runtime.json`, and the accounting file must contain that completed job.
The freeze binds current sources, protocol, model, dataset, Python version and physical
acceptance. Never reuse the original freeze as the follow-up freeze.

Run full development separately, then use a separate accepted held-out output root:
identity is shared across splits but shard geometry is immutable. Remove `ASM_LIMIT`, set
`ASM_FOLLOWUP_FREEZE`, and run calibration before test with fixed shard geometry. For
seed repeats, use separate configs/output roots; their identities must remain distinct.
The existing `analysis review-run/review-accept/replacement` commands and reviewer launcher
support the objective-aware packets without changing the original judge.

`analysis followup-report` requires complete calibration/test sample coverage before
producing nested-N metrics. No N=3/5 or 0–100 numerical results exist yet.

## Checkpoints and engineering stops

The runner writes atomic review artifacts, cumulative status and 0/20/40/60/80/100%
checkpoints with calls, token counts, cache hits and elapsed time. Online W&B receives
allowlisted numeric values only. Context overflow stops the workload. More than 10%
invalid reviews after 20 completed reviews stops for diagnosis. Identity mismatches,
infrastructure failures and incompatible resumes fail explicitly, preserving results.

Inspect Slurm allocation use, GPU telemetry, remaining-cost projection, per-scale validity
and score collapse at every checkpoint. Scientific effectiveness on held-out records is
never a routing, stopping or tuning criterion. Physical interruption/restart and the new
launcher dispatch are not yet GPU-validated.
