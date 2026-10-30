# Pre-main engineering completion

October 29, 2026. The implementation is committed at `a0fd3fd` on
`feat/monitoring-study`; documentation updates follow separately. The supplied
instruction and task-spec edits remain preserved. No held-out inference was launched.

Completed: exact EaE passage resolution and diagnosis; durable attempt journals,
validated recovery and shard ownership; local progress and aggregate-only W&B;
measured GPU timing, allocation accounting and submission reconciliation; fair
selection and budget reporting; and a real freeze with verified prerequisites. A
selection-boundary error at exactly 5% invalid was corrected with integer counting.

Verified: 57 local CPU tests; Yale Linux readiness tests; prompt context audit on
1,200 records; a 40-record-per-method independent cold development screen;
real Slurm drain/resume; an H200 frozen-runtime smoke across all five methods and
independent freeze verification; and synthetic aggregate-only online W&B from a
Slurm compute node. These checks do not prove held-out detection effectiveness.
The separately staged injection launcher is syntax-checked, not GPU-validated.

The study is ready for frozen primary execution within the agent-selected 90 total
GPU-hour cap authorized by the user. GPU usage, selection, scientific caveats,
remaining costs and instructions are in the [readiness report](../reports/pre-main-experiment-readiness.md)
and [operations](../operations.md). The full evaluation remains future work.
