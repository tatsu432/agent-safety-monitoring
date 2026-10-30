# Pre-main-experiment implementation plan

All readiness phases are complete; the main held-out study remains future work.

1. **Complete:** Diagnose development EaE failures and repair exact passage selection
   and quote-budget feedback without weakening validation.
2. **Complete:** Add validated recovery, shard ownership, progress and aggregate-only
   W&B, with local fallback and bounded Slurm shutdown.
3. **Complete:** Add comparable independent timing, GPU accounting, submission
   reconciliation, development selection and budget-aware reporting.
4. **Complete:** Verify scientific invariants, prompt fit, real H200 behavior,
   result-level restart, and online tracking on a compute node.
5. **Complete:** Record the measured resource plan, freeze the selected study and
   provide explicit launch and recovery instructions.

The secondary injection launcher is staged and syntax-checked; its physical GPU
execution remains part of the future secondary study. Results, limitations and
resource accounting are in the [readiness report](../reports/pre-main-experiment-readiness.md).
