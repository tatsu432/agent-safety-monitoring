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
- **105 tests pass; Ruff passes.** Software tests do not establish new GPU compatibility.

## Active execution

Pilot **32795420** requests one H200 for at most 30 minutes. Its partition eligibility
was expanded in place to `gpu_h200,gpu_devel` with the verified `gpu:h200` feature;
GPU count, account, time cap and submission identity were preserved. It started on
`a1124u11n01` in `gpu_h200`. No duplicate was submitted.

CPU continuation **32796191** depends on the pilot. It verifies allocation and exact
coverage, checks completed-result replay with generation forbidden, imports compatible
original requests, then continues timing, development, seed repeats, calibration/test,
objective-aware review and fixed-judge substitution through the existing ledger.
It stops on failures, missing coverage, or incompatible identities; it never tunes
from held-out effectiveness. Final aggregate generation still requires report synthesis.

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
and the rendered submission PDF are not yet complete.
