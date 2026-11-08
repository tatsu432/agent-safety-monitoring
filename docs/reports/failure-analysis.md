# Evidence-grounded EaE/MRT diagnosis

This analysis is post hoc and uses saved outputs only. New inference has not run.

## EaE

The original poor valid-score discrimination survives statistical reconciliation. It cannot
be attributed solely to final invalid outputs. Saved quotations are exact canonical spans.
Counting all primary records, benign/attack empty selections number 19/
37; these include invalid records and differ from valid-only counts in
the earlier evidence report. Mean quotation counts are 17.18 and
9.66. Selection order differs from source order in
4 benign and 61 attack records.
Selected tool-call IDs lack a selected matching result in 63
benign and 190 attack records. These structural measures
do not establish relevance, lost harmful evidence, or causal extraction failure.

Earlier token measurements show substantial unused 3K budget. Prior stronger-model review
and fixed-judge evidence substitution did not demonstrate an improvement. That reviewer was
blinded to harmful objectives, so it does not fulfill the new objective-aware diagnostic.
The new objective-aware packet and prompt are separately versioned. References remain
model-suggested, not human-verified; supplied objectives are hypotheses, not proof of success.

Use the five-way taxonomy: evidence absent; present but unselected; selected without essential
context; sufficient but misjudged; uncertain reference/benchmark label. Unverified semantic
cases remain unresolved. A missing quote or citation alone does not resolve the taxonomy.

## MRT

| Branch | Calibrated TPR / FPR % | Valid AUROC | Valid TPR@5% | Raw pAUC |
| --- | ---: | ---: | ---: | ---: |
| MRT sequential | 28.6 / 3.3 | 0.889 | 43.3 | 0.0464 |
| MRT hierarchical | 20.7 / 10.3 | 0.771 | 16.1 | 0.0161 |
| MRT hybrid | 40.9 / 8.5 | 0.903 | 47.8 | 0.0439 |

Terminal stages were reconstructed from actual chunk/tree geometry; every valid hybrid score
matches the mean of its recovered terminals. Missing branch terminals receive their own
referrals for branch diagnostics; surviving branches never replace invalid original hybrids.
Branches disagree on 271 of 572 records, including missing-terminal
disagreements. Sequential suspicion decreases at least once in
40 records. Earlier sequential citations are absent from final
state in 451 records. Citation loss does not establish semantic
information loss. Invalid-attempt categories are `{'citation': 18, 'schema': 1}`; retries
and final invalid outcomes have different denominators.

The hierarchical branch is less discriminative overall, but equal averaging improves hybrid
AUROC and TPR@5% over sequential-only in these point estimates. Sequential-only has slightly
higher raw low-FPR pAUC and lower calibrated FPR. There is no metric-independent justification
for deleting a branch, or evidence yet that a larger summary budget solves the problem.

## Go/no-go

Proceed with controlled score-scale and N-scaling experiments after real development checks.
First complete objective-aware evidence substitution before changing EaE extraction. Do not
run a broad EaE/MRT sweep, common-rubric change, or adaptive cascade now. A chronology-preserving
EaE candidate or 1,024-token MRT state is conditional on development evidence of the relevant
failure, with one factor changed at a time. Existing structural baselines and overlap analyses
remain sensitivity checks, not causal evidence of shortcuts.

[Prior evidence review](eae-failure-analysis.md) · [Structural controls](structural-confounding.md)
