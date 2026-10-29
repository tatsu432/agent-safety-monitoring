# Yale execution runbook

## Verified status (October 28, 2026)

Interactive Duo login succeeded as `cpsc4710_ts2236` on Bouchet, via the authorized
`yale-hpc-cpsc4710` alias. Slurm association: account `cpsc4710`, QOS
`interactive,normal`; no partition restriction reported. Project root:
`/nfs/roberts/project/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring`.
Personal scratch root: `/nfs/roberts/scratch/cpsc4710/cpsc4710_ts2236`.
The feature branch is cloned at the project root. Group quota inspection succeeded.

A single 10-minute, one-H200 inventory job was accepted as **31239245**. It was
pending because nodes were down, drained or reserved when inspected. Reconcile with
`squeue` and `sacct` before submitting another job; do not create duplicates.
GPU execution, model compatibility and actual cost remain unverified.

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

## Job ledger (October 28, 2026)

- `31239245`: one H200, 10-minute GPU inventory; pending at last inspection,
  nodes down/drained/reserved. Does not test model inference.
- `31239250`: 30-minute CPU environment setup and pytest on `education`; pending
  for resources at last inspection. Log: `logs/cpu-setup-31239250.out`.

Both were submitted from the project-specific checkout at commit `1726573`. Check
job states and logs before any retries. These jobs have not yet validated execution.
- `31241189`: CPU preparation of the digest-pinned vLLM Apptainer image, pinned
  model snapshot and audited dataset; submitted from `c512526`, running when last checked.
- `31241259`: one-H200, one-hour representative single-review pilot, dependent on
  successful completion of `31241189`; submitted from `2d7ce5e`. Budget reservation:
  one GPU-hour, in addition to the one-second inventory job. The pilot has not yet run.
- `31242503`: one-H200, 2-hour-45-minute ten-configuration development benchmark,
  dependent on successful completion of `31241259`. The two reservations together
  total 3.75 GPU-hours plus the one-second inventory, within the four-hour pilot
  ceiling. Benchmark stops if every output in a workload is invalid.
- `31243770`: parallel CPU preload of the pinned model's vLLM-compatible files,
  independent of image conversion; running when last inspected. Its shared cache
  uses Hugging Face file locks and may be reused by preparation.
- `31243770` subsequently completed successfully in 28 seconds; the pinned model
  files are cached on project scratch.
- `31243971`: parallel locked download of the public benchmark logs; running when
  last inspected. Its destination is the ignored `data/raw` under the project root.
