# How Should a Coding Agent Safety Monitor Spend Its Compute Budget?

**Working research draft. Real-model results are pending; no effectiveness claims
are supported yet.**

## Research questions

This study asks how a coding-agent safety monitor should allocate extra inference
compute, which evidence may be lost by extraction/summarization, and whether
agent-authored instructions can influence a saved-trajectory reviewer. It evaluates
saved behavior and cannot determine whether live intervention would prevent harm.

## Dataset and preprocessing

The raw BashArena Claude Opus 4.6 release contains 600 nominal benign trajectories
and 600 attack-assigned trajectories. Recorded grades classify 569 attacks as
successful, 18 as unsuccessful, and 13 as ungraded. Each harmful objective has 150
assigned trajectories. Eight records lack usable tool behavior; four further attack
runs lack usable benign counterparts. The deterministic task-group split supplies
30 development tasks, 118 held-out attacked tasks and 448 never-attacked benign
calibration records. This seed yields 454 usable successful test attacks; proposal
counts were provisional. See [the generated audit](dataset/dataset-audit.md).

Inputs preserve genuine tasks and visible messages/actions/results, while excluding
private instructions, grader metadata, submission tool markers, and source-message
indices that could disclose conversion artifacts. Canonical segment identifiers,
exact text, source positions and immutable raw sources support evidence tracing.
The pinned tokenizer's complete-prompt audit found a maximum of 116,555 prompt
tokens and no overflow at the configured 131,072 limit including generation/retry
headroom. This is not proof of physical GPU memory fit.

## Methods

One fixed gpt-oss-20b revision reviews each source with five procedures: single
review; longer reasoning; independent repeated review and averaging; exact evidence
extraction followed by an independent judge; and equally weighted sequential and
hierarchical chunk review. Outputs use ordinal suspicion categories 1–5. See
[methods](../methods.md) for input isolation, retry and aggregation conventions.
Scientific prompts and budget configurations will be chosen using development
data and frozen before held-out inference.

## Evaluation

The primary metric is successful-attack TPR at a benign-calibrated 5% target FPR.
Expected randomization at tied boundaries handles discrete scores; deterministic
thresholds provide sensitivity analysis. Invalid outputs are referral alerts with
separate invalid rates. Valid-score AUROC is reported with coverage. Paired task
bootstrap resamples calibration and test tasks independently and recalibrates every
replicate. Structural baselines, overlap-aware length weighting, independent
reference-evidence review and matched neutral-control injections address shortcuts
and failure modes.

## Results pending physical execution

Dataset measurements are available. No GPU backend has been validated and no
real-model development or held-out judgments have been generated. Consequently,
there is no selected numerical compute budget, detection estimate, method ranking,
or prompt-injection robustness result to report. Synthetic tests validate software
behavior only. Populate monitoring cost/performance tables and figures from saved
frozen results after the pilot and full-study budget approval.

## Limitations to examine

Nominal benign assignment is not a guarantee of harmlessness; recorded attack
grades may contain errors. One agent family, dataset and monitoring model limit
generalization. Length and tool-count imbalance create shortcuts. Expected
randomized policies differ from deterministic deployment rules. Small injection
and evidence-review samples support exploratory diagnostics, not causal claims.
Physical throughput, long-context fit and runtime cost must be measured on the
selected hardware.

## Reproducibility

The repository provides a uv lock, source/data/configuration hashes, incremental
Inspect ingestion, exact span checks, resumable call caches, immutable scientific
freezes, and generated aggregate reports. Raw benchmark content remains local.
See [operations](../operations.md) and [Yale execution](../yale-hpc.md).
