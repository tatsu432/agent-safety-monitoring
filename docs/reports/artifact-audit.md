# Artifact audit

Verified locally on November 1, 2026. Cluster authentication is unavailable;
full result-record reconciliation and current Slurm accounting remain unverified.

- Scientific freeze: `b86533ed57f70956b55d8a5e26eac1f833dc622ef92b36060e1f71382c70ae5d`.
- Frozen source: `a0fd3fd19e7b64cd4b6a99f9ed8e2cec14d1ddbd`; 47 source objects checked,
  zero mismatches against recorded Git objects.
- Prepared manifest matches the freeze. All 1200 canonical files
  match recorded hashes; zero missing or changed records. No task-level split leakage.
- Local `runs/full-study/` supplies saved primary, structural and injection summaries.
  These are aggregate evidence, not independent proof of full inference coverage.
- Full per-trajectory results, the completion/controller record, original annotation
  sample, selected-cold timing source, and current accounting remain on Yale.
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
at their published precision. This agreement does not replace a recomputation from
full records. The reported 60.61 allocated GPU-hours and 90-hour cap are historical
claims pending current project-filtered Slurm accounting, not newly measured totals.

Both locally available prerequisite proofs—the complete-prompt cohort audit and
accepted pilot record—match the SHA-256 values embedded in the freeze. The
underlying selected-cold trial/timing and current accounting still need recovery.
Structural baseline TPR, FPR, and AUROC were independently recomputed from local
development-only fits and agree with all three saved baseline point estimates.
