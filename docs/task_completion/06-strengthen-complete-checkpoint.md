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
