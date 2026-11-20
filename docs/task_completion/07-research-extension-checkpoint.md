# Research extension checkpoint

## Completed and verified

- The original raw archives, canonical data, nested-review archive and split
  identities were verified. The original freeze and previous reports remain
  available.
- The archive-only adaptive replay completed. Its selected gate averaged 3.76
  test reviews and retained 25.3% of the fixed five-review raw low-FPR pAUC gain.
  Fixed-depth replay matches the earlier results. The published metrics and
  figures include independent benign calibration and paired task uncertainty.
- Every overlay action aligns by tool-call ID, function, arguments and order.
  The upstream comparison validated matching text across exports, with authorship
  still unresolved. The isolated development pilot requires an independently
  accepted release-specific authorship receipt.
- The EaE diagnosis packet contains 12 attacks covering all four objectives and
  11 paired benign counterparts. It reuses one blinded archived reference.
  Human-verified references number zero.

## Live Yale state

Reconciled project allocation before submission was 448,787 GPU-seconds
(124.663 GPU-hours), including the exact lookup of historical job 32797535.
The documented cap remains 130 GPU-hours. The 40-minute H200 reviewer job
34032156 is pending on node availability. CPU controller 34032535 waits on a
successful review, verifies coverage, and uses the same accounting guard to
reserve at most 45 minutes for the fixed judge. Inference uses the original
environment and project-owned storage. The ledger controls retries.

The selected-case EaE outcomes and physical adaptive timing are still pending.
The latter was optional and has no allocation. Reasoning-inclusive results are
unavailable because the authorship gate failed. No new independent test cohort
was used.

[Extension report](../reports/extension-v1.md) ·
[Protocol](../plan/07-research-extension-plan.md) ·
[Reproduction](../reports/extension-reproduction.md)
