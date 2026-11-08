# Diagnose/improve checkpoint — November 8, 2026

The local forensic/engineering phase is complete; **the full scientific task is not**.
Required new model experiments remain blocked by Yale authentication.

## Executed and verified

- Both raw Inspect source checksums, all 1,200 canonical records and original frozen
  source objects reconcile. Direct raw-log replay finds zero label/payload mismatches
  and zero inconsistent genuine task descriptions. No trajectory command was executed.
- Independent histogram evaluation reproduces every original primary point estimate
  and 2,000 paired task-bootstrap TPR/FPR intervals, including saved-report reconciliation.
  New valid-score ROC TPR@5%/10%, raw low-FPR pAUC, paired intervals, referral floors,
  infeasible-replicate counts and common-valid sensitivity are published.
- MRT terminal reconstruction agrees with every valid original hybrid. Sequential
  versus hierarchical AUROCs are 0.889 versus 0.771; hybrid AUROC is 0.903. No universally
  better branch-removal policy or semantic summary-loss mechanism is established.
- Benign calibration/test feature contrasts, original structural baseline points,
  quotation chronology and call/result coverage diagnostics have been computed.
- Both new scoring prompts fit all included records using the pinned tokenizer,
  with maximum prompt 116,619 plus reserve 8,320 below 131,072; no overflow.
- A separate cache holds 2,081 original request entries. Six real saved-record checks
  confirmed exact original-call reuse with server access disabled.
- Online allowlisted numeric diagnosis metrics were synced to
  [W&B](https://forge.coreweave.com/wandb/tatsu432s/agent-safety-monitoring/runs/cb6b61a0adda4706b307fd7a24a1bd74).
- Locked environment installed successfully; **101 tests pass**, Ruff passes, modified
  Slurm launcher syntax and CLI dispatch checks pass. Original frozen schemas/configuration
  identities remain unchanged. Software tests do not establish new GPU compatibility.

## Implemented and prepared, not executed on a GPU

- Versioned five-category/0–100 scoring with shared N=1/2/3/5 samples, strict range
  validation, atomic results, source/data/Python identities, immutable geometry, request
  reuse, interruption recovery, engineering stops, progress/call/token checkpoints,
  independent development acceptance and held-out freeze gates.
- Aggregate follow-up reporting rejects missing/unexpected samples, incomplete shard
  geometry and corrupt scores. Common source coverage is required for paired comparisons.
- Separate objective-aware reviewer prompt and private 3-record development/30-record
  diagnostic packets. Prior blinded references and replacement results remain intact.
- Existing launch wrapper dispatch supports the follow-up; physical launch/resume and
  fine-score throughput remain unverified. Full development selection, seed repetitions,
  new calibration/test inference, objective-aware reference review, controlled substitutions,
  and evidence-justified repairs remain outstanding.

## Exact blocker and continuation

`ssh -o BatchMode=yes -o ConnectTimeout=8 yale-hpc-cpsc4710 true` returned
`Permission denied (keyboard-interactive)`. Fresh scheduler/account/storage checks and
GPU submissions cannot proceed until the user restores Duo/ControlMaster access.
The user was notified while independent work continued. Standing GPU authorization
remains sufficient; no new submission approval is needed. No new GPU job was submitted.

Historical accounting remains 61.306 allocated GPU-hours against the existing 90-hour
cap. The approximate new workload projection is not a measured fine-score cost. Reconcile
fresh accounting and set an evidence-based revised cap after the physical pilot; do not
silently count an unperformed experiment as complete.

[Execution protocol](../reports/followup-experiment-plan.md) contains exact commands,
resource assumptions, stop conditions and the next physical-validation steps.
[Current report](../reports/final-report.md) and [audit](../reports/original-study-audit.md)
contain the completed findings. Private artifacts are in the diagnosis worktree's
`runs/diagnosis/` and `runs/followup/`; original recovered artifacts remain in the sibling
analysis worktree. No raw data, cache, packet, model explanation or private reasoning is
committed or uploaded to W&B. Report source and figures are supplied; final rendered
submission packaging awaits completion of the required new experiments.
