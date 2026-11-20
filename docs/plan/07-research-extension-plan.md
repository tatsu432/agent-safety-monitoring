# Research extension protocol v1

This extension preserves the original freeze and task groups. It tests evidence access,
score-based review routing, and an EaE context intervention. The previously examined test
groups support exploratory analysis. The analysis date cutoff is December 8, and the
submission deadline is December 16, 2026.

## Reasoning visibility

Recover only the release's action-level extended-thinking field. Require exact agreement
among overlay, assistant and model-event call identifiers, arguments, functions and order.
Verify authorship independently. Keep exact private source spans, exclude duplicate visible
text and submission actions, and use a versioned evidence representation. Treat recorded text
as untrusted evidence.

Compare action-only, reasoning-only, combined and availability-masked single review at the
same low effort and fine ordinal rubric. The masked view preserves placement and length
bins of 1–63, 64–255 and 256+ tokenizer tokens. Formatting and length still differ from
the real text. Run a complete pinned-tokenizer audit. The common cohort must retain at
least 80% of each original primary split/class and 80% of paired test task groups.
Use a cold 12-case development pilot with a 90-minute allocation ceiling, at most one
invalid result per view, zero unexpected context overflows, and recorded memory, timing
and exact resume evidence.

If the pilot passes, evaluate all four single-review conditions on development.
Screen action-only and combined versions of 3K EaE and five-interaction MRT with a
512-token state on the same 24 development cases. Advance at most one architecture.
Require combined AUROC of at least .60, a paired improvement of at least .02, at
most 5% invalid judgments, and feasible action-only, combined and masked evaluation.
Order eligible methods by development raw low-FPR pAUC gain and then physical cost.
Use the earliest three eligible actions per record in one optional matched-budget
sensitivity if at least 15 paired development tasks support it and the budget permits.

## Adaptive review

Use five saved independent low-effort 0–100 reviews per example. Candidate policies
gate from one to two, three, or five, or apply a running-mean gate up to five. Fit
inclusive 75th–95th, 80th–97th and 85th–100th percentile bands from benign development
scores only. Use five task-grouped folds and choose based on pooled out-of-fold raw pAUC
over FPR 0–10%, with at most three mean development reviews and 5% invalidity.
Break ties by fewer reviews and configuration order. Freeze the routing policy before
independent benign calibration. Invalid reviews consumed by the adaptive policy trigger
referral and incur cost. Fixed N=1/2/3/5 retain their original rules.

Estimate per-call cost using independent cold timings by prompt length and count retries.
Compare matched-cost fixed-N mixtures and report paired task uncertainty. Use retention of
90% of the pAUC gain from one to five reviews as the practical criterion.

## EaE diagnosis

Select three successful attacks per objective using the original frozen alert policies,
prefer two full-review flags missed by EaE per objective, and add deduplicated paired
benign records. Reuse eligible blinded gpt-oss-120b suggestions and obtain only missing
suggestions with the same pinned reviewer and development acceptance. Human annotation
is outside this run. Verify source spans, and retain explicit model-suggested or unresolved
provenance. Compare original excerpts, suggested excerpts, the same excerpts expanded to
their enclosing interactions and intervening chronology, and full transcripts using a fixed
judge. Use identical formatting rules for both classes. Report observed score changes and
which mechanisms the available evidence can distinguish.

## Release gates and reporting

Calibrate eligible methods independently on benign calibration records. Use tied-boundary
randomization and mandatory referral for invalid outputs. Report realized FPR, expected
detection, valid-score AUROC and raw pAUC, low-FPR sensitivity, coverage, objective strata
and structural shift. Use 2,000 paired task bootstraps with recalibration for cohort-level
inference. Distinguish simulated costs and allocated GPU time.

Use Yale's original pinned model, tokenizer, environment and H200 allocation. Reconcile
windowed and exact-lookup Slurm accounting with the project ledgers before each submission.
Respect the measured cap and reserve contingency only when supported by development
timings. The pre-extension cap was 130 allocated GPU-hours. Stop any inference branch
that fails authorship, validity, context, coverage, cost or deadline gates. Retain aggregate
outcomes and private artifacts separately and preserve previous reports and freezes.
