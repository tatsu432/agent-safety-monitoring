> **November 1 reconciliation update:** Yale authentication succeeded. Full frozen records passed coverage, evaluation-metadata and identity checks for all five methods (448 calibration and 572 primary test records each). Recomputed metrics and bootstrap uncertainty match saved results exactly. Project Slurm accounting confirms 218,212 allocated GPU-seconds (60.614 GPU-hours). Original 30-record annotations are all unreviewed.

# Artifact audit

Verified locally and against Yale records on November 1, 2026.

- Scientific freeze: `b86533ed57f70956b55d8a5e26eac1f833dc622ef92b36060e1f71382c70ae5d`.
- Frozen source: `a0fd3fd19e7b64cd4b6a99f9ed8e2cec14d1ddbd`; 47 source objects checked,
  zero mismatches against recorded Git objects.
- Prepared manifest matches the freeze. All 1200 canonical files
  match recorded hashes; zero missing or changed records. No task-level split leakage.
- Local `runs/full-study/` supplies saved primary, structural and injection summaries.
  Full per-record coverage has now also been independently checked.
- Full per-trajectory results, completion record, annotation sample and Slurm
  accounting were recovered or inspected. The selected-cold timing source was recovered and matched its accepted checksum.
- The saved primary and injection summaries name the expected freeze and selected
  method hashes. Public numerical provenance is recorded in `analysis-aggregates.json`.
  The structural summary has no embedded freeze identifier; matching method hashes
  establish compatibility, but full structural provenance still requires reconciliation.

| Split / assignment / outcome | Records |
| --- | --- |
| calibration/benign/not_applicable | 448 |
| development/attack/failure | 6 |
| development/attack/success | 111 |
| development/attack/ungraded | 3 |
| development/benign/not_applicable | 30 |
| excluded/attack/failure | 4 |
| excluded/attack/success | 4 |
| excluded/benign/not_applicable | 4 |
| test/attack/failure | 8 |
| test/attack/success | 454 |
| test/attack/ungraded | 10 |
| test/benign/not_applicable | 118 |

Primary test therefore contains 118 benign plus 454 successful attacks. Eight failed
and ten ungraded test attacks remain supplementary; they are not primary positives.
No successful shard was rerun, no frozen configuration was modified, and no GPU
submission was attempted while job/accounting state was inaccessible.

The initial public results agree with saved primary point estimates and intervals
at their published precision. Recomputation from the recovered full records matched every saved primary metric and
bootstrap interval. Slurm accounting confirms the 60.614 allocated GPU-hour total.

Both locally available prerequisite proofs—the complete-prompt cohort audit and
accepted pilot record—match the SHA-256 values embedded in the freeze. The
selected-cold trial and current Slurm accounting were subsequently recovered.
Structural baseline TPR, FPR, and AUROC were independently recomputed from local
development-only fits and agree with all three saved baseline point estimates.


On November 3, project-filtered Slurm accounting totaled **61.306 allocated GPU-hours**
(220,700 GPU-seconds), including failed and successful jobs, against the 90-hour cap.
The five evidence-review and replacement GPU allocations used 2,488 GPU-seconds
(0.691 GPU-hours), including both unsuccessful development attempts.
