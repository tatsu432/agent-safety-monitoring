# Post-hoc scientific analysis implementation plan

Preserve primary freeze `b86533ed57f70956b55d8a5e26eac1f833dc622ef92b36060e1f71382c70ae5d`
and source `a0fd3fd19e7b64cd4b6a99f9ed8e2cec14d1ddbd`. Work in the separate
`feat/posthoc-scientific-analysis` worktree. Original artifacts remain read-only.

1. Reconcile source objects, canonical records, splits, full result coverage, saved
   aggregates, cluster completion and allocation accounting. Clearly distinguish
   local verification from cluster-dependent checks.
2. Reuse paired task bootstrap and frozen calibration rules. Publish primary and
   signed paired comparisons, objective uncertainty where available, score/cost
   diagnostics, structural controls and matched injection strata.
3. Diagnose saved EaE stages. Preserve the existing 30-record diagnostic sample.
   Use a pinned stronger local model, blinded to labels and monitor results, to
   propose exact evidence spans. All annotations remain model-suggested; exact
   span validity does not verify harmfulness. Run focused evidence replacement
   only for complete reference sets fitting the original 3K quoted-token budget.
4. Produce reproducible aggregate reports and figures; update the README, report
   draft, methods/operations, and an honest completion checkpoint. Keep numerical
   claims traceable to private input hashes. Commit coherent milestones.
5. Test coverage, pairing, leakage, calibration, uncertainty, blinded annotation,
   provenance, exact spans and export safety. Physically validate new GPU work
   separately; use online scalar-only W&B and existing allocation safeguards.

No broad new search, primary rerun, or optional average-injection extension is
included. Missing Yale authentication or model validation blocks only dependent
work. The user elected model-based annotation instead of human review.
