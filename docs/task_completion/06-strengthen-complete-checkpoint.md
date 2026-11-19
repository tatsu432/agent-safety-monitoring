# Strengthening checkpoint

## Verified results

- The original freeze and all 1,200 canonical source hashes pass the replay
  audit. The follow-up at `5806d2a` has eight completed H200 timing conditions,
  1,500 development reviews, two 400-review seed repeats, and all 16 held-out
  shards. The 4,480 calibration and 5,900 test review artifacts match the
  archive hash inventory. Primary estimates use 448 benign calibration records,
  118 nominal benign test records, and 454 successful attacks.
- The objective-aware review has 3/3 development and 30/30 diagnostic records.
  Its 22 valid replacement comparisons show a −6.1 percentage point expected
  alert change, with a paired interval of −15.2 to 0.0 points. References have
  model-suggested provenance and zero human reviews. Six exceed the original
  budget and two remain unresolved.
- The aggregate includes paired 5% and exploratory 1% calibration, score
  resolution and nested N, seed variability, length strata, and saved-stage
  diagnostics. All held-out follow-ups reuse previously examined task groups.
- Raw hashes match both source archives. The released overlay includes readable
  extended-thinking strings, with large differences in per-action availability.
  The frozen monitor saw canonical visible evidence. Overlay contents stay
  private. The public artifact contains counts and field structure.
- The historical Slurm union includes 411,101 GPU-seconds (114.195 hours), before
  the new development attempts. Direct lookup recovered job `32797535`, omitted
  by the date-filtered query. The ledger wrapper now reconciles both paths under
  the recorded 125-hour cap.
- The aggregate scoring metrics are available in
  [W&B](https://forge.coreweave.com/wandb/tatsu432s/agent-safety-monitoring/runs/d87e3dc5fe4b4020a51cd6934fe59369).

## New work

The fine-scale medium-effort development screen is separate from the completed
scoring freeze. First attempt `33869975` reached vLLM and wrote a fine judgment,
then failed at local deserialization through the legacy 1–5 result class after
190 allocated GPU-seconds. A targeted regression verifies persistence of a fine
score above 5. The retry imports the exact first model request from the shared
cache. The case result directory for the failed attempt is retained.
Retry `33870206` passed serving startup and is writing fine-scale records. CPU
controller `33870866` will check exact completion before reserving the bounded
mechanism suite. The separate mechanism snapshot seeded 83 EaE and 588 MRT
requests from the previously completed matching development screen.

The diagnostic configurations for common-scale EaE/MRT and the MRT 512/1,024
state comparison are development-only. The objective-aware highlights packet
uses up to three source-checked cases per objective. It supports a matched
availability experiment with the fixed judge. Human-semantic verification and a
causal attribution of EaE errors remain open.

[Final report](../reports/final-report.md) ·
[Scoring aggregates](../reports/strengthened-scoring.json) ·
[Stage diagnostics](../reports/strengthened-evidence.json) ·
[Reproduction](../reports/analysis-reproduction.md)

## November 19 continuation

Job 33871161 completed the evidence and MRT development suite in 14,897 allocated
GPU-seconds. All five conditions completed 40 records. The fine-scale EaE and MRT
AUROCs were .515 and .916. Coarse MRT AUROC was .928 for 5 interactions and 512
tokens, .890 for 5 and 1,024, and .884 for 10 and 512. This small screen does not
establish a benefit from the larger state. Eleven highlighted full transcripts
were valid, including eight cases with all four intervention conditions. Source
spans were checked, while semantic sufficiency has not been human-verified.

The fine medium-effort pilot produced 40 valid reviews and development AUROC .939.
Its physical proof and a complete medium-effort tokenizer audit support a separate
exploratory held-out freeze. The measured projection including contingency is 5.82
GPU-hours. Submission is guarded by fresh accounting and the 125-hour cap.

## Completed medium-effort held-out comparison

Job 33902046 reached its checkpoint with six test records remaining. Retry
33943361 completed those records and exited successfully. All 448 calibration and
590 test results match the accepted identities and freeze. One calibration and
two test results were invalid and receive mandatory referrals. Test analysis
includes 118 benign and 454 successful attack records.

At the separately calibrated 5% target, medium-effort 0–100 review achieves
89.9% expected detection, 10.5% realized FPR and .916 valid-score AUROC.
Low-effort fine single review reaches 31.0%, 5.0% and .925 respectively.
The paired detection difference is +58.9 points [25.9, 68.4], while the
AUROC difference is inconclusive. At the 1% target, medium effort reaches
14.3% detection at 3.1% realized FPR. Five fine reviews have AUROC .953 and
a paired advantage over medium effort of .037 [.002, .072]. These are
exploratory comparisons on previously examined task groups.

Reconciled project accounting through both allocations is 448,787 GPU-seconds
(124.663 GPU-hours), including startup and failures. The internal cap was
amended from 125 to 130 hours for a 30-minute retry based on six missing reviews.
The full result and paired intervals are in [the aggregate](../reports/medium-holdout.json).
