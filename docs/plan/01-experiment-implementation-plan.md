# Implementation and execution plan

1. **Foundation / vertical slice (Oct 28–Nov 4):** repository repair, uv package,
   downloader, Inspect importer, canonical evidence, task split/audit, single
   review, parser, mock and physical smoke when accessible.
2. **Methods / development (Nov 5–14):** all five methods, exact quotations,
   traceable chunks, caching/resume, GPU pilot, development selection, freeze.
3. **Held-out inference (Nov 15–25):** frozen calibration/test, coverage and
   resource reconciliation, supplementary unsuccessful/ungraded results.
4. **Analysis (Nov 26–Dec 5):** paired task bootstrap, structural baselines,
   length sensitivity, evidence review, matched injections, tables/figures, draft.
5. **Reproduction (Dec 6–16):** clean-environment replay, archive, final report.

Keep labels out of monitor interfaces; preserve evidence and offsets. Reject
context overflow without truncation. Cache successes atomically; separate logical
procedure costs from physical allocation time. Freeze data/cohort, code, prompts,
methods, budgets, retries, statistics, and payloads before held-out inference.

Use authorized existing alias `yale-hpc-cpsc4710`. Initial read-only SSH reached
Bouchet but required keyboard-interactive/Duo authentication. Inspect permissions,
storage and GPU availability after login. Pilot ceiling: 4 allocated GPU-hours.
Full-study allowance follows measured pilot estimates.

Progress and exact checks appear in `../task_completion/`. No planned physical
experiment counts as completed without an actual job and validated artifacts.

## Current execution status

- Foundation, importer and source/tokenizer audits: implemented and exercised on the real release.
- Five methods, freeze/resume, calibration/statistics, structure/injection diagnostics:
  implemented and tested with deterministic software fixtures.
- Yale compatibility, measured method budgets and scientific freeze: awaiting Duo
  authentication and a physical pilot; no GPU use so far.
- Held-out real-model evaluation, independent evidence annotations, scientific
  figures/results and final report: pending the pilot and full-study resource cap.

See [validation milestone](../task_completion/01-implemented-monitoring-validation.md).
