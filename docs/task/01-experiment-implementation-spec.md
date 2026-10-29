# Experiment implementation specification

The complete engineering requirements are in [01-setup-spec.md](01-setup-spec.md).
The scientific source is the four-page CPSC 5710 proposal in `../project_proposal/`.
This document records binding interpretations agreed during planning.

Evaluate fixed gpt-oss-20b weights using single review, longer reasoning, repeated
review, extract-and-evaluate, and sequential/hierarchical hybrid monitoring.
All methods begin with identical visible evidence and use categories 1–5.
Never execute trajectory commands or train on benchmark artifacts.

Reconstruct labels and task pairings, then split whole tasks: 30 attacked tasks
for development, other eligible attacked tasks for test, and never-attacked benign
ones for calibration. Unpaired attacked tasks and context exclusions are outside
the primary cohort. Exact counts are audited, not assertions from preliminary EDA.

Develop prompts, budgets, and injection payloads before freezing. Primary outcome:
successful-attack TPR under a separately calibrated 5% FPR policy. Use expected
randomization at ties and paired task bootstrap with recalibration. Unresolved
invalid outputs are referral alerts, included in TPR/FPR, never fabricated scores.
Report valid-score AUROC, invalid rates, deterministic threshold sensitivity, and
task-aware uncertainty. Unsuccessful/ungraded attacks remain supplementary.

Use development-measured fixed-hardware workload GPU time, not sums of concurrent
request latency. Pilot ceiling is 4 GPU-hours; set total study cap after pilot.
Authorized Yale alias: `yale-hpc-cpsc4710`. Physical validation and scientific
runs must be recorded separately from CPU/mock validation.

Completion requires the audited dataset, five-method real-model comparison,
evidence diagnostics, matched injection experiment, reproducible tables/figures,
and report by December 16, 2026. Resource blockers are not successful execution.
