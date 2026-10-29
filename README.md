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
outside Git. Real GPU validation and held-out scientific runs are still pending.
