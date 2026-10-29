# Monitoring foundation — implementation milestone, not study completion

Date: October 28, 2026 (America/New_York). Branch: `feat/monitoring-study`.
Commit: the commit containing this record (resolve with `git log --follow --oneline -- docs/task_completion/01-implemented-monitoring-foundation.md`).

Implemented the locked Python package, raw downloader, incremental Inspect importer,
separate evidence/label types, deterministic task splits, five monitoring procedures,
strict judgments/exact quotations, caching/retries, frozen/resumable runs, calibration,
paired task bootstrap, mock workflow, and initial reports. Added secondary injection,
structural baseline/evidence utilities and unvalidated Yale templates. Preserved the
supplied proposal, setup spec and historical HPC notes; repaired stale instructions.

Actually run:

- Downloaded the raw honest and attack release (28,137,353 and 128,490,736 bytes),
  SHA-256 recorded locally under `data/raw/sources.json`.
- Imported all 1,200 samples with zero schema rejections. Reproduced 600 benign,
  569 successful, 18 failed, and 13 ungraded attacks; 150 per harmful objective.
- Eight empty behaviors and four additionally unpaired attacks excluded. Whole-task
  splits: 30 dev pairs, 118 test pairs, 448 calibration benign. Current fixed seed
  gives 454 usable successful test attacks, not the proposal's provisional 451;
  the seed has not been adjusted to force the provisional count.
- Real pinned model tokenizer audit completed. Source token counts differ from
  preliminary preprocessing; complete-prompt/context and physical fit remain distinct.
- Ruff passed; initial pytest suite: **17 passed**. Synthetic all-method workflow
  generated 60 held-out test judgments and aggregate figures with zero invalids.
- Mock backend processed one real development trajectory through all five methods.
- Freeze rejected an injection run after code changed, as intended.
- Shell templates syntax-checked; no Slurm/GPU validation or scientific inference.

Runnable: `uv run asm experiment demo`; see `docs/operations.md` for real-data import
and mock development commands. Synthetic scores are never scientific results.

Outstanding: expanded integration checks, physical Yale/backend validation, measured
budgets and frozen scientific configurations, all real-model comparisons, independent
evidence annotation, injection outcomes, sensitivity analysis, final report/reproduction.
Duo authentication is the current external prerequisite; user was asked to establish
the authorized existing SSH connection. No GPU-hours have been consumed by this project.
