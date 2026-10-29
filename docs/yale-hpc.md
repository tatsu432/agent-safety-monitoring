# Yale execution runbook

## Verified status (October 28, 2026)

The user authorizes existing SSH alias `yale-hpc-cpsc4710` for CPSC 5710 (same
course designation). Its local SSH configuration targets `bouchet.ycrc.yale.edu`
as `cpsc4710_ts2236`. A batch-mode read-only connection reached the host but was
rejected with `Permission denied (keyboard-interactive)`. No jobs were submitted.
Slurm account/QOS, partitions, quotas, writable roots, GPU fit, engine and container
compatibility remain **unverified**. Do not infer them from the username.

The original [transferable HPC handoff](reference/yale-hpc-handoff.md) is preserved
as historical operational knowledge. Its other account's paths, jobs and 24 GPU-hour
allowance do not transfer. This project has a four allocated GPU-hour pilot ceiling;
large-scale runs await a cap based on measured pilot cost.

## Authentication and inspection

```bash
ssh yale-hpc-cpsc4710
# Complete Duo in Terminal; keep the connection open for ControlMaster reuse.
```

Then run `bash scripts/yale/inspect.sh` on the cluster. Record the actual user,
Slurm association/QOS, GPU GRES/partition limits, existing jobs, quota, and writable
personal project/scratch roots. Use a new `agent-safety-monitoring` directory;
do not touch another project's files. No heavy jobs on login nodes.

## Reproducible inference

Use the checked-in lock for the client. On compute nodes, prefer an Apptainer
image of a verified Linux AMD64 vLLM container. Record its immutable registry
digest, SIF SHA-256, engine version, model/tokenizer commit, driver, GPU UUID,
precision, context size, concurrency and tensor-parallel size. The model config
pins a real Hugging Face revision; engine version stays UNVERIFIED until tested.
The serve script requires explicit verified model revision and image checksum.
A supported site environment may be used for the first pilot without claiming a
production container is validated. Never configure nested cgroups or execute
commands in benchmark transcripts.

Submit from the project checkout after creating logs:

```bash
mkdir -p logs
sbatch --account=VERIFIED_ACCOUNT --partition=VERIFIED_PARTITION --gpus=VERIFIED_GRES \
  --time=00:30:00 --mem=32G --cpus-per-task=4 \
  --output=logs/gpu-smoke-%j.out scripts/yale/gpu-smoke.sbatch
```

For inference use `scripts/yale/inference.sbatch`, passing the model-server/runtime
settings via protected environment/config files, plus `ASM_CONFIG` for development
or `ASM_FREEZE` for calibration/test. `ASM_SPLIT`, `ASM_SHARD`, `ASM_SHARDS`,
`ASM_DATA` and `ASM_OUTPUT` are configurable. GPU/memory/walltime/partition/account
are explicit sbatch arguments. Use `ASM_ACTION=benchmark` for measured development
workloads. Stop at four total allocated GPU-hours including initialization/failures.

The generic templates have only been syntax-checked locally. They are not evidence
of accepted Slurm resources, successful CUDA or real-model completion.

## Monitoring and recovery

Use `squeue --me`, `scontrol show job JOBID`, and `sacct -j JOBID -X` to reconcile
jobs before any retry. Never resubmit after an ambiguous SSH/submission response.
Saved per-trajectory results and exact-request caches support resume. Do not change
science or delete failed artifacts to recover. Preserve job IDs and startup/workload
measurements; GPU-seconds are GPU count times allocated duration, not summed latency.
Never kill other users' processes or copy their resource authorization.

Project storage and scratch are not backups. Verify current YCRC purge policy;
keep prepared data/results durable and copy deliverables off cluster before course
account expiration. Secrets stay in mode-600 files outside Git and Slurm arguments.

Sources: [Bouchet](https://docs.ycrc.yale.edu/clusters/bouchet/),
[Slurm](https://docs.ycrc.yale.edu/clusters-at-yale/job-scheduling/),
[containers](https://docs.ycrc.yale.edu/clusters-at-yale/guides/containers/),
[storage](https://docs.ycrc.yale.edu/data/hpc-storage/).
