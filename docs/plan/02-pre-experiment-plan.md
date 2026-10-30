# Pre-main-experiment implementation plan

Implement the approved pre-experiment spec without held-out inference.

1. Diagnose saved development EaE failures and repair exact passage selection and budget feedback.
2. Add durable attempt journals, validated resume, shard ownership, progress heartbeats,
   aggregate-only online/offline/disabled W&B, and bounded Slurm shutdown.
3. Add stable benchmark trials, safe submission reconciliation, allocation accounting,
   comparable development selection, measured GPU-cost reporting and resource estimates.
4. Verify CPU recovery/scientific invariants and complete-prompt context fit. Use only
   the remaining four-GPU-hour pilot allowance for bounded development validation.
5. Record verified outcomes separately from implementation and pending physical checks;
   provide operating commands, budget estimate and explicit go/no-go report.

Freeze and held-out execution require accepted representative development feasibility,
verified runtime/container/hardware, finalized cohort/settings and explicit full-study
resource approval. Never substitute passing mocks for these prerequisites.

Results and remaining actions: [readiness report](../reports/pre-main-experiment-readiness.md).
