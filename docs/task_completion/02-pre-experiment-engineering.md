# Pre-main engineering work — not scientific experiment completion

October 29, 2026. Working-tree implementation on `feat/monitoring-study`, starting
at `c4a6ff1`; no new commit is claimed. The supplied instructions/spec were preserved.

Implemented exact global EaE passage selection with token-cost feedback, private
failure diagnostics, durable call/attempt journals, validated resume and shard locks,
local heartbeat/status, aggregate W&B modes and job lineage, GPU CSV aggregation,
stable benchmark trials, submission reconciliation and resource caps, comparable
selection checks, measured GPU-cost reporting, and stronger real-freeze prerequisites.

Actually verified: local lint, shell syntax, 55 CPU tests, all-method synthetic
end-to-end demo/report, W&B 0.31.0 offline event creation, corrected full-context audit
(1,200 records, zero overflow), pinned-tokenizer replay of the original screen and
seven earlier EaE trials. All 20 final readiness cases passed on Yale Linux in 10.46 seconds.

Real H200 development jobs `31302433` and `31304229` used 1,084 and 173 GPU-seconds.
A Slurm warning interrupted the first job; the second reused 35 complete results and
finished five missing records. EaE 1K: 30/40 valid, infeasible. EaE 3K: 38/40 valid,
meeting the 5% threshold; its resumed timing is not independent cold selection proof.
Final total usage is 3h 51m 32s, leaving 8m 28s under the original four-hour cap.

Online W&B initialization failed, while local monitoring and inference continued.
Successful online delivery, multistage GPU interruption, concurrency improvements and
shell/telemetry fixes made after the staged snapshot remain unverified physically.

Main inference, final development selection, accepted scientific freeze and full-study
budget approval remain separate gates. See the
[readiness report](../reports/pre-main-experiment-readiness.md) for measured results,
resource accounting, current go/no-go and exact remaining actions.
