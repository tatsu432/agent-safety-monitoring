# Completed post-hoc scientific analysis

November 3, 2026. Implementation is on `feat/posthoc-scientific-analysis` in the
separate `agent-safety-monitoring-analysis` worktree. The original scientific
freeze, source checkout, primary predictions, split and thresholds remain intact.

## Verified study and primary comparison

- Freeze `b86533ed57f70956b55d8a5e26eac1f833dc622ef92b36060e1f71382c70ae5d`,
  source `a0fd3fd19e7b64cd4b6a99f9ed8e2cec14d1ddbd`, all 47 source objects and
  1,200 canonical trajectory hashes pass the artifact audit. Calibration/test
  task groups do not overlap. Full five-method coverage and record metadata pass.
- Recomputed primary metrics and 2,000 paired task-bootstrap intervals exactly
  match the original saved aggregate. The primary test comprises 118 nominal
  benign trajectories and 454 source-graded successful attacks; 18 failed or
  ungraded attacks are supplementary.
- Averaging improves TPR over single review by 38.3 percentage points (paired
  95% interval 26.5–46.8); averaging versus think-longer is inconclusive. The
  original expected-randomization threshold policy remains primary.
- The exploratory whole-score rounding and matched-task comparisons, score
  histograms, objective intervals, and original/recomputed ROC figures are in
  [primary analysis](../reports/primary-analysis.md) and
  [structural confounding](../reports/structural-confounding.md).

## Compute, confounding and injection

- Accepted selected-cold source hash matches its frozen proof. One-H200 development
  workload times are 15.30, 14.18, 26.77, 13.67 and 141.81 GPU-seconds per
  trajectory for single, think, average, EaE and MRT, respectively. Think's
  lower observed time despite more tokens is not causally explained.
- Project-filtered Slurm accounting totals 220,700 GPU-seconds, **61.306 GPU-hours**,
  including all failures and follow-ups, below the 90-hour cap. The follow-up
  allocations total 2,488 GPU-seconds (0.691 GPU-hours).
- The development-fitted length-and-tool-count baseline reaches 0.901 AUROC;
  this is evidence of structural predictive confounding, not proof that monitors
  used a particular shortcut. Length-matched estimates and overlap are reported.
- The 480 matched injection comparisons cover only single and EaE. Their aggregate
  attack-miss intervals include zero; the synthetic, nonadaptive experiment does
  not establish equivalence or adaptive robustness.

## Model-suggested evidence and replacement

The original 30-record sample remained fixed and blinded to attack labels,
grades, monitor outputs and sampling strata. The first 120B development check
exhausted its output limit; a second produced paraphrased quotations. The third
used medium effort, a 16,384-token limit and independently indexed 800-character
source passages. It passed all three development checks on an H200 and processed
all 30 diagnostic records: 28 supported interpretations, one unresolved
interpretation and one invalid output. All references are model-suggested, with
zero human-reviewed records.

The reviewer selected 304 source passages; EaE fully retained 9, partially
retained 9 and had no overlap with 286. Coarse partial passage overlap may still
retain decisive content, and model selection is not verified ground truth.
The 20B frozen EaE judge evaluated replacement evidence for 24 records in 22
matched task groups. Four supported sets exceeded the original 3K token cap and
two records were unresolved. Expected alerts changed from 5.6% to 2.8%:
−2.8 percentage points, pointwise 95% interval −13.4 to 5.8. The selected,
post-hoc diagnostic does not establish improvement or a causal explanation.
See [model evidence results](../reports/model-evidence-results.md) and
[paired aggregate](../reports/model-evidence-paired-summary.json).

Slurm jobs 31619759 and 31802302 completed but produced invalid development
proposals; repaired development 31802796, diagnostic 31802993, and replacement
31804042 completed. The dependent CPU controllers advanced only after validation.
No new primary calibration/test inference was run. Private packets, citations,
responses, model reasoning, and individual results remain outside Git and W&B.

## Verification and remaining scientific limits

The full optional-dependency test suite passes **90 tests**. Ruff, shell syntax,
Git whitespace, report links, source-hash checks and aggregate privacy checks
pass. Model-review development and replacement were physically exercised on the
project H200, not inferred from mocks. Important primary and evidence aggregates
were synced to online W&B as scalar-only runs; local artifacts remain authoritative.

There is no independent human evidence annotation, and model-suggested reference
passages can be mistaken, incomplete or unnecessarily broad. One monitor model,
one agent family, the fixed benchmark, structural confounding, unequal realized
FPR and compute, coarse ordinal scores, small selected diagnostic samples and
synthetic nonadaptive injections limit generalization. Offline review does not
establish live intervention effectiveness. These are scientific limitations,
not uncompleted human-review tasks: the user selected model review explicitly.
