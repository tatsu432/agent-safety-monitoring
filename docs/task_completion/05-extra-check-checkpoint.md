# Extra-check checkpoint - November 10, 2026

The full task is **in progress**, not complete.

## Completed

- Inspected local/GitHub main (`14a3e05`), existing worktrees and private recovered
  artifacts; preserved user changes and the original scientific freeze.
- Restored Duo authentication and a reusable Yale SSH connection. Reinspected the
  `cpsc4710` association, normal/interactive QOS, H200 partitions and group quotas.
  No user jobs were active before submission. Fresh accounting reproduces
  **220,700 allocated GPU-seconds = 61.3056 GPU-hours**, including failures.
- Added coverage-checked before/after coarsening, disagreement, distributions/ties,
  marginal N comparisons, eight-candidate development selection, homogeneous cold
  GPU timing, fixed-screen seed IDs, and publication figure generation.
- Held-out follow-up freeze now requires compatible full-development selection.
  Legacy frozen result schemas and prompts are unchanged.
- Executed joint length/tool sensitivity with development-derived fixed cells and
  2,000 paired whole-task draws, recalibration, and reweighting. It excludes 143 of
  572 test records (3 benign, 140 attacks); Kish ESS is 104.4/123.3. Averaging's
  weighted detection is 73.4% [58.9,84.4], versus 34.2% [26.6,46.2] single,
  48.2% [31.9,69.4] MRT, and 65.8% [48.5,95.1] think-longer. The structural
  length/tool baseline has weighted AUROC 0.676. These are exploratory estimates
  for a changed overlap population, with residual within-cell confounding.
- Re-ran the frozen source/data audit: all 1,200 canonical files and 47 frozen source
  objects match; no task leakage. Regenerated original five-method and 480 injection
  aggregates match the published numeric artifacts exactly.
- Published allowlisted aggregate scalars to
  [W&B](https://forge.coreweave.com/wandb/tatsu432s/agent-safety-monitoring/runs/nov10-joint).
- **108 tests pass; Ruff passes.** Software tests do not establish new GPU compatibility.

## Active execution

Pilot **32795420** completed successfully on one H200: all **30/30** reviews
were valid (15 per scale), with no retries or cache hits. Startup took 106 seconds,
workload 471 seconds, and Slurm allocated **577 GPU-seconds**. Actual maximum inputs
were 64,351 tokens (five categories) and 64,373 (0–100). The all-record context
preflight remains separate. [Aggregate physical measurements](../reports/followup-pilot-aggregate.json)
record model, Python, source identity and token counts. This pilot does not estimate
held-out effectiveness or prove all possible restart modes.

Completed-result replay passed with model generation explicitly forbidden. No
in-flight GPU interruption was tested. Accounting after the pilot is **61.4658 GPU-hours**.

The first CPU continuation **32796191** completed, imported 2,081 compatible original
requests, and submitted homogeneous timing **32797535** (one H200, at most six hours),
with dependent continuation **32797536**. Timing is running on `a1126u19n01`; complete homogeneous measurements
are not yet available. A model-default representation
mismatch in timing identities was corrected and regression-tested before that job
started. Full development will reaccept the final source identity before held-out work.

Continuation verifies allocation and exact coverage, then proceeds through timing,
development, fixed-screen seed repeats, calibration/test, objective-aware review and
fixed-judge substitution using the existing ledger. Pilot and predeclared N=5 timing
calls are reused for scientific development. It stops on failures, missing coverage,
or incompatible identities; it never tunes from held-out effectiveness. Final report
synthesis and PDF packaging remain outstanding after aggregate generation.

The cap remains **90 GPU-hours** pending physical timing. The continuation records a
separate evidence-based amendment after the eight timing workloads, using consumed
allocation + 1.25 times remaining projection, rounded up to five hours. An internal
accounting cap is not a scheduler resource grant.

## Locations and recovery

Remote checkout:
`/nfs/roberts/project/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring-extra-check`.
Private outputs: `runs/extra-check/`; continuation submission ledger: `runs/submissions.json`.
Inspect `squeue --me`, project-filtered `sacct`, `continuation.json`, any
`controller-failure.json`, summaries, and logs before recovery. Never resubmit an
ambiguous identity. Complete-result resume preserves geometry, protocol, source,
Python and model identities; interrupted cold timing is not a valid cold measurement.

[Joint sensitivity](../reports/joint-structural-sensitivity.md) contains the completed
CPU result. Scoring inference, objective-aware references/substitution, final synthesis,
and the final submission PDF are not yet complete. An 11-page draft PDF has been
rendered and visually checked, including the completed joint sensitivity.

The active inference checkout stays at `5806d2a`. Subsequent analysis-only changes
are developed separately and must not be pulled into active/frozen inference.
The newer report interface supports original-method paired comparisons through
`--original-run`, without changing original results.
