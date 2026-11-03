# Agent safety monitoring

Offline comparison of five coding-agent monitoring procedures using fixed
`openai/gpt-oss-20b` weights and saved BashArena trajectories.

```bash
uv sync --locked --extra data --extra tokenizer
uv run pytest -q
uv run asm experiment demo
```

The demo uses synthetic judgments and does not measure monitor effectiveness.

- [Scientific specification](docs/task/01-experiment-implementation-spec.md)
- [Implementation plan](docs/plan/01-experiment-implementation-plan.md)
- [Methods](docs/methods.md) · [Operations](docs/operations.md) · [Yale](docs/yale-hpc.md)
- [Implementation records](docs/task_completion/)

Benchmark commands are never executed. Data, caches and private run artifacts stay
outside Git. The frozen GPU study is reported complete. Local post-hoc analysis
verifies frozen source/input hashes and reconciles full prediction records. The
exploratory model-based evidence review and its replacement diagnostic are complete.

Current findings: [research report](docs/reports/report-draft.md) ·
[artifact audit](docs/reports/artifact-audit.md) ·
[reproduction and remaining work](docs/reports/analysis-reproduction.md).
Historical launch evidence: [readiness report](docs/reports/pre-main-experiment-readiness.md).
