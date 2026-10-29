# Project and operating instructions

This repository studies controlled experiments on the effectiveness of different monitoring for agent safety. The authoritative scientific
specification is `docs/task/01-experiment-implementation-spec.md`; early proposal
documents are historical. Read `README.md`, `docs/methods.md` and
`docs/operations.md` before changing experiments. Related papers are in
`docs/papers`.
`docs/project_proposal/final_agent_monitoring_proposal.pdf` provides the concrete contents of the project.

## Engineering invariants

- Use the `uv.lock`, digest-pinned Docker images for reproducibility, and
  Apptainer for the trainer on Yale. Use W&B for online training and inference tracking; never put keys in
  YAML, Git, scheduler arguments or logs.
- Keep science, hardware, environment and logging settings separate. 
- Keep `README.md` short and link detailed material from `docs/`. For each task
  spec under `docs/task/NN-...-spec.md`, create the matching plan under
  `docs/plan/NN-...-plan.md` and a completion record under
  `docs/task_completion/NN-implemented-....md` after implementation.
- Keep implementation modular and DRY. Fix code errors and run relevant tests
  before declaring readiness. CPU tests do not establish GPU backend, memory fit
  or generated-code isolation on Yale.

## Yale HPC
Whenever working with Yale HPC, read `docs/yale-hpc.md`
before configuring SSH, submitting Slurm jobs, managing
GPUs, or troubleshooting cluster issues.

Reuse the documented operational knowledge and lessons
from the previous project. Use this project's own SSH
alias, authorized account, storage, and configurations.
Do not repeat previously resolved investigations unless
the current environment differs.