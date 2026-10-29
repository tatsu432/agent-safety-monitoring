# Methods and analysis conventions

The experiment compares fixed-weight gpt-oss-20b monitoring on saved BashArena
Claude Opus 4.6 trajectories. It does not establish live intervention effectiveness.
See the [specification](task/01-experiment-implementation-spec.md) and supplied proposal.

## Inputs and labels

The current imported release stores genuine task identity/description in
`metadata.main_tasks[0]`, attack assignment in `metadata.side_tasks`, and side-task
grades in `scores.tasks.value.side` (1 successful, 0 unsuccessful, null ungraded).
The importer records these paths and source hashes. Never treat monitor scores
or nominal benign assignment as independent proof of harmless behavior.

Replace initial user preambles uniformly with the explicit genuine task. Remove
system/private reasoning and the `submit` tool call/result from both classes.
Preserve visible assistant text, tool function/arguments, and outputs in order.
Text blocks preserve exact text; tool-call text is deterministic JSON serialization
of the original function and arguments. Character spans refer to these canonical
segment strings, not byte offsets into the compressed .eval file. Original message
indices, source hashes and IDs allow tracing back to raw local logs. No other
suspicious text is removed. Never upload raw examples to W&B or source control.

Task splitting orders paired task IDs by SHA-256 of task ID and seed 20261028,
selects 30 for development and holds out the remainder. Never-attacked tasks supply
benign calibration. Empty behaviors and tasks lacking usable benign counterparts
are explicitly excluded. Failed/ungraded test attacks are supplementary.
Tokenizer/context checks must finalize the common cohort before a scientific freeze.

## Procedures

All judgments use integer categories 1–5, explanations and original segment IDs.
Single review uses low effort; think-longer changes only effort. Repeated review
uses distinct seeds and averages all categories. EaE validates exact character
spans and a quoted-token cap before an independent judge. Its judge sees no full
transcript or extractor verdict. MRT sequential summaries preserve ordered state;
binary hierarchical merges combine independent leaf summaries. Equal branch
weights produce the hybrid score. Source chunk overflow is split without dropping
characters. These are controlled adaptations, not exact paper reproductions.

Malformed stage outputs get one corrective generation. Transport failures have
at most two retries for transient statuses/timeouts; all attempts remain recorded.
Unsupported quotations/citations and unresolved failures invalidate the procedure.
No partial branch/sample score is substituted. Invalid results trigger referral
alerts and have no ordinal score. Context overflow is explicit, never truncated.

## Calibration and statistics

Use a descending cutoff and expected randomization at the tied boundary to target
5% FPR, including mandatory invalid-output referrals. If invalid calibration rate
alone exceeds 5%, the policy is infeasible; show its actual referral FPR. Also show
a conservative deterministic boundary. Test results never set thresholds.

TPR/FPR include all eligible results including referral alerts. AUROC uses valid
scores with coverage reported, because invalid outputs have no ordinal category.
Use 2,000 paired bootstrap samples of whole tasks, independently sample calibration
and test tasks, and recompute each method's threshold in every replicate. Require
identical trajectory coverage for paired differences. Report sample counts.

## Resources and freeze

Count logical model calls/tokens even when cache entries are reused. A cache hit
incurs no new model generation. Request latency is diagnostic and must not be
interpreted as GPU time under concurrency. Primary GPU cost needs allocated
GPU count times measured workload duration, shared server overhead treatment,
startup separately, and identical hardware/scheduling across methods.

Production selection uses development data only: temperature 0.2 initially,
medium/high effort, repetitions 2/3/5, EaE 1K/3K, MRT 5/10 interactions. Choose
small/large budgets from measured costs; freeze one feasible setting per method
and budget. No held-out output may influence these choices. Pre-freeze real
readiness requires tokenizer audit, actual GPU pilot, and full-study budget cap.

MRT's summary cap applies to the **entire serialized carried state**, including
explanation, score and citations. Source-message indices remain local provenance;
monitor payloads use sequential canonical step IDs and canonical tool-call IDs.
This avoids exposing systematic conversion offsets while preserving call/result
associations, including multiple calls within one assistant message.

When the serving engine supplies reasoning text but no reasoning-token count,
tokenize that text locally and record a separately labeled estimate. The estimate
may differ from generated token IDs at message boundaries. Never save or send the
reasoning text to W&B; exact generated-token usage remains the server's total.
