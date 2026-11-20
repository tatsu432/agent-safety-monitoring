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
- The pinned tokenizer audit found that the combined prompt reached 557,816
  tokens. The shared four-view test cohort retains 50 of 454 successful attacks
  and 39 of 118 paired tasks. The context coverage gate failed. A classifier
  using reasoning availability alone reached 1.000 AUROC on the original test
  cohort, exposing a strong structural shortcut.
- The EaE diagnosis packet contains 12 attacks covering all four objectives and
  11 paired benign counterparts. It reuses one blinded archived reference.
  Human-verified references number zero.

## Live Yale state

Reconciled project allocation before submission was 448,787 GPU-seconds
(124.663 GPU-hours), including the exact lookup of historical job 32797535.
The documented cap remains 130 GPU-hours. Reviewer job 34032156 completed all 22
new cases in 726 allocated GPU-seconds. CPU controller 34032535 passed the packet
checks but its job name did not match the accounting guard. It stopped before
submission. The corrected continuation verified the same accepted packet and
submitted fixed-judge job 34035701 once. It completed all 92 condition records
in 916 allocated GPU-seconds. An independent replay verified the judgment
and span-coverage inventories. Expanded context raised attack suspicion by
2.20 points [1.20, 3.00] across ten valid pairs. References are model-suggested.
Diagnostics of source sufficiency and judge error remain unresolved.

Adaptive timing job 34038037 completed in 1,169 allocated GPU-seconds.
The matched cold review archive contains all six development trajectories per
condition, with 22 adaptive and 30 fixed-five calls and zero cache hits or
invalid results. Measured workload time was 69.7 versus 114.3 H200 seconds per
trajectory, with startup excluded. Reconciled project accounting totals
451,598 GPU-seconds (125.444 GPU-hours), and no extension jobs remain active.
Reasoning-inclusive results are unavailable because the authorship and context
coverage gates failed. No new independent test cohort was used.

[Extension report](../reports/extension-v1.md) ·
[Protocol](../plan/07-research-extension-plan.md) ·
[Reproduction](../reports/extension-reproduction.md)
