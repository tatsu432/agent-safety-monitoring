> **Evidence-review update:** The model-based diagnostic has completed. See [its aggregate results](model-evidence-results.md); earlier pending-status statements below are historical. References remain model-suggested.

# EaE failure analysis

The frozen 3K EaE method has 4.8% expected attack detection, 5.1% realized test
FPR, and 0.556 valid-score AUROC. Three of 572 primary outputs are invalid.
Low valid-score discrimination therefore cannot be explained solely by final
invalidity. Poor discrimination also appeared before held-out evaluation: the
selected cold development screen had AUROC approximately 0.524.

The frozen implementation divides canonical segments into passages of at most
400 characters and selects up to 24 global passage IDs under a 3K quoted-token
cap. The judge receives the genuine task and exact selected quotations, without
the full transcript or extractor verdict. These constraints preserve source
fidelity but can remove chronology or context. Their contribution to failure
requires evidence beyond these architectural observations.

## Independent analysis of available historical development outputs

The earlier, resumed 3K repair screen is available locally. It is **not** the
selected cold screen or frozen test cohort. Replaying its validation found 38
valid final results among 40 records; one final extraction exceeded the quote
budget and one final result failed citation/judge validation. These historical
failures and resumed timing remain distinct from the frozen main study.

Inspection of persisted extraction artifacts found 32 records with nonempty
quotations. Among these, mean quotation count was 14.375, median selected tokens
1,684.5, mean utilization of the 3K budget 48.0%, and the range 186–2,428 tokens.
Thus this development sample often left budget unused. Six valid final results had empty extraction artifacts. Two additional invalid
records had no nonempty extraction saved; these are distinct from valid empty
selections. Exact counts are in the accompanying aggregate.
Nonempty extraction is a structural observation, not proof of relevant evidence.

Valid-score AUROC in this historical repair sample was 0.504. Fifteen attack
records scored 1, three scored 4, and two were invalid. Seventeen benign records
scored 1, two scored 4, and one scored 5. These counts show little separation
in that particular development sample. They do not establish that increasing
the budget or forcing additional passages would help.

All tokenizer measurements use the saved pinned tokenizer configuration.
[Historical numeric aggregates](historical-eae-aggregate.json) provide denominators,
configuration identity, and histograms; reproduction commands are in
[the analysis runbook](analysis-reproduction.md). Detailed calls and individual
records remain private. Invalid-attempt artifact categories and replayed final
validation categories are separate taxonomies and should not be summed together.

## What remains unresolved

The recovered frozen test records show a mean of 11.21 quotations and 1,068.8
quoted tokens per trajectory across all 572 primary records, including empty
and invalid results. These descriptive averages do not establish evidence relevance.
Cross-step coverage and conditional judgment performance require model references. No reference
retention percentage or verified extraction-versus-interpretation attribution is
reported. Underutilization in historical repair data must not be projected onto
the frozen test cohort without checking those artifacts.

Potential mechanisms include poor passage ranking, unnecessary compression,
missing multi-step connections, missing authorization context, weak judging of
supplied evidence, and dataset-specific cues. These remain hypotheses. A missing
citation would not establish misunderstanding, and exact quotation containment
would not measure semantic retention in MRT summaries.

## Stronger-model evidence workflow

The user elected model-based annotation instead of human review. The configured
reviewer is local `openai/gpt-oss-120b`, revision
`b5c939de8f754692c1647ca79fbf85e8c1e70f8a`, with a separately pinned serving
configuration. Its larger size is not independent proof that its interpretations
are correct; shared model-family errors and transcript prompt injection remain risks.

The workflow preserves the original 30-record sample and hides labels, harmful
objectives, grades, monitor selections, scores, and verdicts. Reviewers see the
genuine task and canonical steps only. Proposed character spans must match exact
source text. Supported conclusions require references; unresolved cases remain
explicit. All outputs retain `model_suggested` provenance and zero human-reviewed
records. Exact-span validation establishes textual validity only.

Development-only short/median/long records form the physical validation packet.
Held-out diagnostic annotation requires a completed measured allocation and
compatible GPU/container/engine evidence. No such GPU validation or annotation
inference has occurred; the pinned reviewer is staged and development GPU validation is queued.

The implemented follow-up passes each complete usable reference set to the
original 20B judge, in source order, under the original 3K quotation budget and
calibrated policy. Oversized sets are excluded with `budget_exceeded`, never
truncated or selected based on favorable scores. Invalid judge outputs remain
referrals. Paired task intervals condition on the selected sample and frozen
threshold. This is an exploratory conditional diagnostic, not a replacement
confirmatory score or a human-verified evidence study.

## Frozen test extraction, recovered records

Across all 572 primary test records, the extractor saved an average of 11.21
quotations and 1,068.8 quoted tokens per trajectory. The two classes differ:
benign records average 17.18 quotations and 1,617.8 tokens, while successful
attack records average 9.66 quotations and 926.1 tokens. Among valid results,
17 of 118 benign records and 36 of 454 attack records have no quotations.
These are descriptive observations conditional on saved artifacts, not evidence
that any particular omitted behavior is harmful or that the extractor caused a
miss. [Aggregate counts](eae-test-extraction-aggregate.json) can be reproduced
with `scripts/analysis/summarize_eae.py` from the private record diagnostics.
