# Yale Bouchet HPC — transferable project handoff

**Prepared:** 2026-10-28  |  **Audience:** a *different* Yale coursework/research-engineering project using Bouchet, a *new SSH alias*, and potentially a different authorized course account.  
**Sources:** inspected `tatsu432/self-play-opsd-coding-agent` (`main` as available 2026-10-28); Aakash Patel's *Yale HPC Cluster Setup and Use* (Spring 2026); current official YCRC SSH, course, storage, Slurm, GPU, container, and coding-agent documentation. See §16.

> **Executive rule:** Reuse *knowledge and operational patterns*, not permission, allocation, scientific settings, worker certificates, paths, checkpoints, or the old project's `selfplay hpc` commands. A new SSH alias is a local name for a connection, **not** a new YCRC account, grant, allocation, job queue, or security boundary.

## 1. What the previous project actually established

A previous coursework project, [self-play-opsd-coding-agent](https://github.com/tatsu432/self-play-opsd-coding-agent), used the **Bouchet** cluster and worked through actual CPU/GPU jobs, Slurm accounts, containers, and generated-Python safety.

| Observed/verified in that project | What a new project may reuse |
|---|---|
| Working SSH alias `yale-hpc-cpsc4880` to `bouchet.ycrc.yale.edu`, logging in as `cpsc4880_ts2236`; normal Duo MFA. | Same hostname and authentication pattern; **choose a different alias** and verify the account for the **new** project. |
| Slurm account `cpsc4880`, QOS values `interactive,normal`, no partition restriction in that particular account association at 2026-10-22 inspection. | Commands to inspect associations. These permissions **do not transfer** to another account/course. |
| Historical usable public GPU partitions `gpu_h100`, `gpu_h200`, `gpu_rtx6000`; actual one-H200 numerical training validation. | GPU types and scheduling approach, pending current account/partition/resource verification. |
| Durable workspace `/nfs/roberts/project/cpsc4880/cpsc4880_ts2236/selfplay-opsd-cpsc4880_ts2236/` and corresponding personal course scratch storage. | A directory layout pattern. **Never write the new project's files into this previous project's directory.** Discover the new account's writable directories. |
| Reproducible, digest-pinned trainer image, built as an Apptainer `.sif` on Yale CPU compute nodes. | Containerization and image-provenance recipe. Image is not guaranteed compatible with a new project. |
| Real YCRC support response 2026-10-27: ordinary users **cannot configure nested cgroups** on Bouchet; Slurm provides per-step CPU/memory limits; Apptainer can provide filesystem/network isolation; Slurm does **not** enforce an arbitrary 32-process limit. | A constraint to avoid rediscovering through repeated unsuccessful cgroup attempts. |
| Real worker isolation acceptance (Slurm job `31033392`, 19 checks): separately limited CPU/memory Slurm step, fresh Apptainer payload, early Linux seccomp single-process policy, cleanup, OOM/cancellation tests. | A *precedent* for untrusted generated-code execution if needed. Not an automatic safety certification for another implementation. |
| Real H200 backend tests, checkpoint/resume checks, resource accounting, four dry-run controller previews; main A–D science training still not authorized in the referenced records. | Engineering lessons on staged proof, logging, avoiding duplicate jobs, and checkpointing. **Do not copy the previous 24-GPU-hour readiness authorization.** |

Key reference files:

- [`AGENTS.md`](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/AGENTS.md) — operational memory and current/historical evidence (some historical rules explicitly superseded).
- [`docs/yale-launch-runbook.md`](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/yale-launch-runbook.md) — current launch sequence, read-only previews, monitoring and recovery.
- [`docs/operations.md`](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/operations.md) — full code/data/training workflow.
- [`docs/task_completion/02-implemented-yale-hpc-use.md`](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/task_completion/02-implemented-yale-hpc-use.md) — real SSH/account/storage inspection.
- [`docs/task_completion/07-implemented-yale-execution-blocked-readiness.md`](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/task_completion/07-implemented-yale-execution-blocked-readiness.md) — accepted isolation and GPU debugging lessons.
- [`docs/yale-worker-support.md`](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/yale-worker-support.md) — actual YCRC technical response and history.
- [`scripts/hpc_remote.py`](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/scripts/hpc_remote.py), [`scripts/hpc_job.py`](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/scripts/hpc_job.py), [`scripts/yale.slurm`](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/scripts/yale.slurm) — reference implementation (deeply coupled to that project; **not drop-in scripts**).

## 2. Access and accounts: do this first

**Connection:** `bouchet.ycrc.yale.edu`  
**Off campus:** connect to Yale VPN first; on-campus network works directly.  
**Authentication:** registered SSH public key plus normal Duo MFA. YCRC's SSH key uploader can propagate keys across authorized YCRC accounts. Do not store/share private keys or attempt to bypass Duo.  
**Course accounts:** the form is `<courseid>_<netid>`; for example the previous course account was `cpsc4880_ts2236`. A course login is distinct from a personal research account. YCRC states **course accounts must only be used for coursework**, not unrelated personal/research projects. A different course may require a different course account with its own username; the *SSH alias* does not change this.

**Choose one of these two valid configurations:**

1. **New authorized course/research account**: use its *actual* username in the new alias. Its Slurm account, project directories, storage, rules and job ceilings must be inspected independently.
2. **Same authorized account for an eligible task within that account's allowed scope**: use the same SSH `User` with a new alias and separate project directory. This does **not** create independent GPU quotas or new authorization.

The old repository mentions `yale-hpc-cpsc4710` and `yale-hpc-sds6190`, but their entitlement, quotas and noninteractive MFA were **not** verified there. Do not infer they are available simply from their names. Confirm any other course's current YCRC account and purpose with its instructor/YCRC.

### New macOS SSH alias (`~/.ssh/config`)

Keep the existing `yale-hpc-cpsc4880` entry unchanged. Add a **separate** stanza, using a descriptive name such as `yale-hpc-agent-monitoring` (or any name chosen by the new project):

```sshconfig
Host yale-hpc-NEWPROJECT
    HostName bouchet.ycrc.yale.edu
    User AUTHORIZED_COURSEID_ts2236
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    ControlMaster auto
    ControlPath ~/.ssh/cm-%C
    ControlPersist 2h
    ServerAliveInterval 30
    ServerAliveCountMax 4
```

Replace `AUTHORIZED_COURSEID_ts2236` with the **confirmed** YCRC username. Replace `IdentityFile` only if a different registered key is actually used; do not generate unnecessary new keys. `ControlMaster` and `ControlPersist` reuse a Duo-authenticated connection; they do **not** remove MFA. `%C` names the control socket using a hash of host/port/user, so aliases to the same server+user may share a connection (expected, not separate quotas).

On the Mac:

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/config
ssh -G yale-hpc-NEWPROJECT | grep -E '^(hostname|user|identityfile|controlpath) '
ssh yale-hpc-NEWPROJECT
# Complete Duo normally. On the cluster:
whoami; hostname -f; pwd; groups
```

Use `Remote-SSH: Connect to Host...` in VS Code with the **new alias**, and open the **new project's** remote directory. Editing on a login node is fine; do not execute CPU-intensive tests, GPU workloads, image builds, large inference, or coding-agent servers there.

If SSH returns `keyboard-interactive`/Duo required, authenticate interactively in Terminal. In the previous repository, the custom `uv run selfplay hpc login` command created a two-hour persistent control session; that command **exists only in the previous repository**. Standard `ssh yale-hpc-NEWPROJECT` is the portable method.

## 3. Read-only inspection to establish *current* permissions

Once logged in via the new alias, **before requesting GPUs**:

```bash
whoami; hostname -f; groups; pwd
ls -ld "$HOME" "$HOME"/project* "$HOME"/scratch* 2>/dev/null || true
getquota  # report home/project/scratch quotas; may require -g GROUP for a course
sacctmgr -nP show assoc where user="$(whoami)" format=User,Account,Partition,QOS
sinfo -o '%P | %a | %l | %G | %D'
scontrol show partition education_gpu 2>/dev/null || true
scontrol show partition gpu_h100 2>/dev/null || true
scontrol show partition gpu_h200 2>/dev/null || true
squeue --me
```

The bundled `templates/read_only_inspection.sh` provides an auditable, read-only version of this survey. Individual commands may be disabled or have site-specific output, so **a failing query is not proof of zero entitlement**; use the Slurm association and, if unclear, YCRC/instructor confirmation. Record the actual `User`, account, QOS, partition, GPU GRES type, CPU/GPU ratio, walltime and quota restrictions. Do not assume public partition limits equal your course-specific account limits.

For a real job, inspect `scontrol show job <JOBID>`, `sacct -j <JOBID> ...`, and relevant scheduler errors. `sinfo` is an instantaneous inventory/queue view, **not a GPU reservation**.

## 4. Bouchet GPU and partition selection (guidance, not permission)

As described in YCRC's 2026-10-28 online Bouchet/course documentation:

| Partition | Representative GPU | Published VRAM per GPU | Intended use / important caveat |
|---|---|---:|---|
| `education_gpu` | RTX 5000 Ada; A40 | 32 GB / 48 GB | Intended for coursework; currently max **2 GPUs per user**, **1 submitted job per user** in this partition, with 24h maximum jobs. Requests must explicitly include `--gpus` (often `--gpus=1`). |
| `gpu_h100` | NVIDIA H100 | 80 GB | Public GPU option; up to 48h per job shown in Bouchet docs. Request typed GPU `--gpus=h100:1`; actual account/QOS can be stricter. |
| `gpu_h200` | NVIDIA H200 | 141 GB | Public GPU option; up to 48h per job shown. Request `--gpus=h200:1`. Previous project successfully used one H200. |
| `gpu_rtx6000` | RTX Pro 6000 Blackwell | 96 GB | Public partition; request `--gpus=rtx_pro_6000_blackwell:1` where authorized. |
| `gpu_b200` | NVIDIA B200 | 193 GB | Public partition in current docs, **not** verified as permitted or compatible for previous/new project. |
| `devel`, `day`, `education` | CPU only | — | Lightweight CPU development, data preparation, trusted CPU tests. |
| `gpu_devel` | GPU debugging | varies | Short GPU interactive/debugging jobs; inspect actual limits. |
| `agent` | Usually a coding-agent session, **not training GPU** | — | YCRC-specific low-resource agent session. See §13. |

The *older Spring 2026 course handout* summarized RTX 5000, RTX 6000 and H200, and reported 60-day scratch clearing. **Use live Slurm plus the current YCRC pages, not the old handout, for updated partition lists, account limits and scratch policy.**

**Selection rule:** start with a small, permitted GPU that fits a representative model; compare empirical peak VRAM, full-step runtime (including model initialization, inference, optimizer, evaluator), queue practicality and GPU-hours. The previous project initially tried H100 but uncovered GPU allocation/occupancy problems unrelated to true model OOM. It later selected one H200 for documented scheduling and workload reasons. Do **not** deliberately induce an H100 OOM to justify using H200. If a new workload truly needs multiple GPUs, prove that distributed training is correct and faster per *allocated GPU-hour*.

**Real Slurm shape matters:** previous `cpsc4880` submission of nine CPUs alongside one H200 was rejected; an eight-CPU total allocation succeeded (seven trainer CPUs/128 GiB plus a separate one-CPU/1-GiB worker). That limit was *specific to that account/job shape*, not a universal Bouchet CPU/GPU rule. Inspect `MaxTRES`, association/QOS, and single-node capacity rather than requesting the node's entire CPU count.

## 5. Storage: use separate persistent and ephemeral paths

YCRC storage classes:

- **Home**: commonly 125 GiB/person, backed up. Best for small scripts, config and notes. Not large caches/checkpoints.
- **Project**: often 4 TiB per research/course group, **not backed up**, shared quota. Use for durable checkpoints, run outputs, curated datasets and model provenance. Keep independent off-cluster copies of vital results.
- **Scratch**: often 10 TiB per group and **not durable**. **On Bouchet files older than 30 days are automatically deleted.** Use for Hugging Face/cache/temp/image-building work, not sole copy of checkpoints. Do not defeat purge policy by touching timestamps.
- **Course account lifecycle**: YCRC says course account **and associated data** are removed **one month after the last day of exams** for the term; students may receive **no individual reminder**. Copy deliverables out in time or arrange an approved transfer with YCRC.

Previous specific root **for reference only**:

```text
/nfs/roberts/project/cpsc4880/cpsc4880_ts2236/selfplay-opsd-cpsc4880_ts2236/
```

New project must discover an **actually writable personal project subdirectory** (the group fileset root may be read-only), then keep at least this separation:

```text
<NEW_WRITABLE_PROJECT_ROOT>/<NEW_PROJECT_SLUG>/
  source/             # project checkout(s), preferably pinned to commits
  images/             # verified .sif files + SHA256/manifests if used
  data/               # immutable prepared data / fingerprints
  runs/               # durable run directories, checkpoints, events
  logs/               # Slurm stdout/stderr, diagnostic reports
  state/              # submission ledger, run metadata, budget tracking

<NEW_WRITABLE_SCRATCH_ROOT>/<NEW_PROJECT_SLUG>/
  huggingface/         # HF_HOME / transformers and datasets caches
  apptainer-cache/    # APPTAINER_CACHEDIR
  apptainer-tmp/      # image-build scratch
  tmp/                # generic temporary files
```

Create only after confirming the roots are writable and attributable to the correct course. Avoid assuming `$HOME/project` and `$HOME/scratch` resolve as in the previous account. The bundled template gives paths as variables, not hardcoded accounts.

Recommended environment variables set **inside a compute allocation or its batch script** (edit placeholders):

```bash
export HF_HOME="<NEW_WRITABLE_SCRATCH_ROOT>/<NEW_PROJECT_SLUG>/huggingface"
export APPTAINER_CACHEDIR="<NEW_WRITABLE_SCRATCH_ROOT>/<NEW_PROJECT_SLUG>/apptainer-cache"
export APPTAINER_TMPDIR="<NEW_WRITABLE_SCRATCH_ROOT>/<NEW_PROJECT_SLUG>/apptainer-tmp"
export TMPDIR="<NEW_WRITABLE_SCRATCH_ROOT>/<NEW_PROJECT_SLUG>/tmp"
mkdir -p "$HF_HOME" "$APPTAINER_CACHEDIR" "$APPTAINER_TMPDIR" "$TMPDIR"
```

## 6. Reproducible source deployment

For small repositories, cloning the new project's repository in its own project directory may suffice. For longer training, use the stronger approach proved in the previous project:

1. Keep source in Git with **clean commit**; record full SHA, dependencies (`uv.lock`, `requirements.txt`/Conda lock), container base digest, data revision, model/tokenizer revision and experiment settings.
2. Transfer a Git bundle or otherwise publish an immutable checkout to the *new account's* project storage. The old controller transferred a Git bundle and checked out into a `<commit-SHA>` directory.
3. Store prepared datasets in a separately versioned/hash-named directory. Make input data read-only to jobs. Never mix main data with mutable scratch or another project's hidden evaluation data.
4. Keep each submitted run's resolved config, full source/data hashes, account, partition, GPU type/count, Slurm ID, timestamps, outputs and latest verified checkpoint.
5. Test with one bounded CPU or GPU smoke before a long training job. Check that inference, optimizer, filesystem, imports, data loading, and restart paths **actually run**, not merely pass imports.

If transfer is large, YCRC recommends `transfer-bouchet.ycrc.yale.edu` (with Yale network/VPN and authorized username) for `rsync`/`scp`, or Globus for high-volume transfers. Avoid bulk transfer/load from login nodes. YCRC's GitHub and staging guidance also applies.

**Important:** `uv run selfplay hpc login/doctor/inspect/sync/submit/status/logs/fetch/watch` is a custom CLI from the *old* repository. The new repository has **no such commands** until you implement an adapter. Borrow its *design*, not the invocation. It may be excessive to port the entire 70k-lineage controller for a two-GPU experiment.

## 7. A minimal, working Slurm workflow

Submit **only once an account, partition, resource request, storage path and small test are verified**. The included `templates/gpu_smoke.sbatch` intentionally omits `--partition`, `--account`, and GPU request from file directives: the caller supplies them explicitly, preventing a hardcoded course account from leaking into a new project.

On the remote login node, from the new project checkout (`logs/` must exist **before submission**):

```bash
mkdir -p logs
# Intended course GPU partition; confirm that the account is permitted:
sbatch --account=<CONFIRMED_SLURM_ACCOUNT> --partition=education_gpu --gpus=1 \
  templates/gpu_smoke.sbatch

# OR use a publicly available typed GPU, if actually authorized:
sbatch --account=<CONFIRMED_SLURM_ACCOUNT> --partition=gpu_h100 --gpus=h100:1 \
  templates/gpu_smoke.sbatch
# For H200: --partition=gpu_h200 --gpus=h200:1
```

For a first GPU smoke, the example uses 4 CPUs, 24 GiB host RAM, 20 minutes; **adjust to fit your association limits**. This smoke imports Torch, checks CUDA devices, does a small matrix multiplication and records GPU visibility; it does not establish full model fit. The script respects `SLURM_SUBMIT_DIR` and does not require Apptainer. If your real project needs a container, test `apptainer exec --nv --cleanenv ...` in a separate allocated trial.

**Useful monitoring and recovery commands:**

```bash
squeue --me
squeue -j <JOBID> --start
scontrol show job <JOBID>
sacct -j <JOBID> -X -o JobID,JobName,State,ExitCode,Elapsed,AllocCPUS,AllocTRES,MaxRSS
jobstats <JOBID>            # if installed by YCRC
scancel <JOBID>              # intentional cancellation only
# Slurm log filename: logs/<job-name>-<JOBID>.out (from example script)
```

Submission scripts must put all `#SBATCH` directives before executable shell commands. Directives are parsed by Slurm rather than expanded as ordinary shell variables; do not assume `#SBATCH --account=$ACCOUNT` expands. For workload launches, set resources via explicit `sbatch` flags or template a job file before submission.

For a short interactive compute session, use `salloc -p education --time=00:30:00 --mem=8G` (or `gpu_devel`/`education_gpu` **with an explicit `--gpus=...` request** if authorized). Check `hostname` after allocation; it must be a compute node. End allocations promptly. Large/long tasks should be submitted as `sbatch` jobs so they survive loss of the SSH session.

## 8. Apptainer and environment builds on Bouchet

YCRC states **Apptainer is available on compute nodes, not login nodes**. It is the normal container runtime for Yale jobs. The essential form for trusted GPU code is:

```bash
# Run only inside a Slurm-allocated compute node and with valid .sif/binds:
apptainer exec --nv --cleanenv \
  --bind <PROJECT_ROOT>:<PROJECT_ROOT> \
  --bind <SCRATCH_ROOT>:<SCRATCH_ROOT> \
  <VERIFIED_TRAINER_IMAGE>.sif \
  python -m <YOUR_PACKAGE> <ARGS>
```

`--nv` supplies NVIDIA host GPU support; `--cleanenv` reduces inherited variable surprises, but **is not itself complete sandboxing**. Mounts need to be scoped to the project and not expose credentials. Ordinary Apptainer default mounts can include home unless isolation options/binds are correctly configured; for untrusted code see §9.

The previous project built a trainer from a pinned Dockerfile via a CPU-only Yale build, then verified SIF SHA-256 *inside an allocation* before execution. A real build produced an **11.02-GiB image** and observed about **56.68 GiB logical temporary scratch** use. Those numbers are **evidence for that image only**, not universal requirements. The build encountered Python version pin mismatches, compression memory spikes and unhelpfully large local archives; building on Yale CPU resources with scratch/caches sized appropriately resolved it. Favor simple module/`uv` environments for small jobs; add containers when portability, package dependencies or isolation justify the added overhead.

Reproducibility recommendation: use pinned `uv.lock` or equivalent dependency lock, immutable image definition/base digest, SIF checksum, Git commit and model revision. Validate versions/CPU imports on a CPU allocation; validate CUDA, vLLM, training and memory **on the actual GPU type** before declaring readiness.

## 9. If the new project runs **untrusted generated code**

This section matters for coding-agent evaluation, model-generated Python, generated tools, repository execution, and red-team environments. It **does not apply automatically** to ordinary trusted training scripts or inference on a fixed dataset.

**Confirmed YCRC guidance received 2026-10-27:** ordinary users cannot configure cgroups; use Slurm **job steps or arrays** for per-task CPU/memory and Apptainer for filesystem/network isolation. Slurm **does not give a configurable arbitrary per-task process-count cap**. Attempts to pass Apptainer `--apply-cgroups`/`--pids-limit` without delegation repeatedly failed. Do not keep retrying them or claim they work.

**What the previous project eventually proved on Bouchet:** it launched an authenticated loopback broker in an allocated compute host; each generated-Python candidate ran in a separately limited CPU/memory no-GRES Slurm step, with a fresh Apptainer filesystem/network namespace, no network egress/GPU/trainer/oracle/credential mounts, private bounded temporary storage, bounded time/output, and an early **Linux AMD64 seccomp policy prohibiting candidate-created processes/threads**. The worker accepted 19 actual CPU checks including kernel CPU/memory enforcement, intentional worker OOM, recovery, scheduler cancellation and process cleanup. Thus the former arbitrary **32-process** requirement was replaced by a **verified single-process** policy. This is a documented working design **for that code/host configuration**, not a guarantee that any copied Python sandbox is safe.

**For the new project, choose proportionate safeguards:**

- If no untrusted code execution occurs: skip specialized worker broker/seccomp complexity and use ordinary Slurm+Apptainer/venv.
- If untrusted code *does* execute: reuse the high-level accepted pattern, but implement and **prove on real Bouchet compute allocations** CPU, host memory, process/thread creation, filesystem, network, GPU access, temp storage, timeout/output, cleanup and recovery before large-scale jobs. Keep secrets/evaluation oracles outside candidate mounts. Never launch untrusted candidate code on login nodes, from the trusted trainer process, or with the Docker socket/host credentials accessible.
- Be aware that one-process prohibition **changes what candidate programs can do** (e.g., code that needs Python multiprocessing or spawned test processes). Define scientific validity and compatibility with your benchmark; do not blindly reuse if the experiment requires subprocesses. If required functionality cannot be safely supported, ask YCRC for a supported mechanism rather than removing safety checks.
- A plain subprocess timeout, Python `resource`/`RLIMIT_NPROC`, or unprivileged cgroup flag alone is **not a proved hostile-code boundary**. Likewise, Slurm CPU/memory alone does not address fork bombs or network/data exfiltration.

The old code references are `src/selfplay_opsd/worker_runtime.py`, `src/selfplay_opsd/worker_policy.py`, `src/selfplay_opsd/hpc.py`, `scripts/hpc_remote.py`, and the Task 07 completion record. Only copy after understanding and testing the security assumptions for the new project.

## 10. GPU/LLM-specific failure modes learned the hard way

| Symptom | What was learned / practical response |
|---|---|
| GPU looks full before model loads or an H100 attempt reports OOM | It can be a **foreign/leftover vLLM process or GPU index mapping**, not your model's memory needs. Capture Slurm GPU allocation, device cgroup, actual CUDA UUID and *initial* occupancy. Never terminate other users' processes. Report unexpected occupancy to YCRC. |
| `nvidia-smi --query-gpu=minor_number` fails | That CSV field was unsupported on the inspected driver. The prior project used supported CSV fields plus `nvidia-smi -q -x` UUID-based matching for Linux minors. Do not equate NVIDIA index with Linux minor number. |
| Multi-GPU job is pending/rejected | Check account/QOS TRES and CPUs per GPU, number of nodes, memory, walltime and whether GPUs must be on the same node. Starting with one GPU often reduces failure modes and GPU-hours. |
| vLLM process-group initialization fails under `torchrun` | Child vLLM engine inherited `RANK`/`WORLD_SIZE`/elastic rendezvous variables. Sanitize rank/rendezvous environment for truly independent engine processes and test actual multi-process startup. |
| LoRA adapter-copy check fails despite matching layers | BF16 proposer vs FP32 student adapter master weights were an actual mismatch in the old code. Confirm precision, parameter ordering/storage and version equality; test copies independently. |
| GPU job returns COMPLETED but scientific work is missing | Slurm's state is **not** proof that dataset yield, optimizer updates, output files, target iterations or evaluation were completed. Use explicit acceptance metrics and checkpoint manifests. |
| Run restarts and doubles jobs | Never blindly re-`sbatch` on network disconnect, ambiguous response or stale controller. Reconcile `squeue`, `sacct` and a durable run/submission ledger first. |
| Worker isolation test fails due to cgroup/D-Bus | YCRC does not give user cgroup delegation. See §9; do not run an identical failed probe repeatedly. |
| `uv` or packages fail on login/CPU but GPU backend worked locally | Distinguish platform/architecture, pinned Python version, CUDA support, package ABI and image build environment. ARM Mac Docker builds must explicitly target Linux AMD64 if used for Bouchet. |

## 11. Job budgets, efficiency and checkpoint recovery

Define a budget **for the new project**. As an accounting convention, a job requesting `N` GPUs for `H` elapsed allocated hours consumes approximately `N × H` **GPU-hours** (include startup and idle time), independent of whether GPUs were fully utilized. Record both requested walltime reservations and actual charged elapsed time; do not equate an H200 hour with a market-dollar cost unless a priced allocation is explicitly provided.

The previous project's **24 allocated GPU-hours** was a **user-approved allowance for its own readiness checks**, with a specific durable ledger and restricted purpose. **It does not grant 24 GPU-hours to another project**, nor does a new SSH alias reset group accounting. Current official partitions have scheduling ceilings; your own allocation policy may be more restrictive.

Recommended long-job discipline:

- Short CPU setup → one small real GPU backend smoke → representative multi-step/pilot with measured VRAM, step time, output yield, checkpoint size and resume → full training only after **authorized** resource scope is known.
- Leave enough walltime buffer to write a complete, checksummed checkpoint before Slurm time limit. In the old project, `#SBATCH --signal=B:USR1@300` and a controlled stop point supported safe restart; adjust lead time to measured worst-case checkpoint cost.
- Save **all** state required to continue (model/adapters, optimizer, scheduler, dataloader/sampler cursor, RNG state and experimental context). Never resume from a half-written checkpoint or a different scientific configuration. For large models, measure checkpoint write time.
- Recover automatically only from explicitly recognized infrastructure interruptions with a verified complete checkpoint; do **not** auto-retry scientific validation errors, numerical divergence, OOM or unknown submission outcomes.
- Compare methods at declared budgets and monitor allocated GPU-hours, not just steps/sec or throughput; too much diagnostic instrumentation can erase performance gains.
- Preserve log/manifest lineage of failed attempts rather than deleting them to give an appearance of clean success.

For model training, W&B can run in `offline` mode on compute nodes and later sync. For `online` mode, confirm cluster egress and the project's approved data classification. Keep `WANDB_API_KEY`/HF tokens in user-owned files with `chmod 600` **outside Git**, not YAML, command-line flags or Slurm job metadata. Treat local JSONL/events/checkpoints as the authoritative record even if tracking delivery drops.

## 12. New-project readiness: useful, not needlessly rigid

Avoid the old project's over-conservative early bottleneck of requiring **exactly 32 processes via nested user cgroups**. Design checks around *actual risks and measured acceptance*, not a prescribed unavailable mechanism. A GPU job need not be blocked by generated-code isolation if the job executes only trusted data and imports. Conversely, never waive execution isolation where attacker-supplied or model-generated executable code runs.

A practical acceptance set for a new **trusted** 1–2 GPU ML project is: verified SSH/Duo/account; writable roots/quotas; CPU environment; accepted GPU allocation; actual CUDA+model/inference/optimizer work; bounded runtime/memory; checkpoint and resume; output artifact validation; no duplicate jobs; reproducible manifest. Add an independent worker containment test **only if** untrusted executable data is used. Match the rigor to the project's risk, without making every research experiment inherit the older project's elaborate A–D science gates and frozen-study IDs.

## 13. Optional: coding agent working *on* Bouchet versus using a local Codex over SSH

For the new project there are two different patterns:

- **Recommended for an existing Mac-based Codex workflow**: run your normal coding agent locally, edit via Git/VS Code Remote-SSH, and have it use the new SSH alias for **lightweight read-only Slurm inspection**. Submit heavy tests/inference/training as compute-node Slurm jobs. Do not make a full local agent workload run on the login node.
- **YCRC's own local coding-agent service** (current 2026 YCRC docs): start an allocation on the `agent` partition, then `module load local-coding-agents` and run `pi`, `codex`, `copilot` or `claude`. These are *interfaces to a YCRC-hosted model*, **not the commercial OpenAI/Anthropic models**. The `agent` partition is for lightweight agent sessions (1 CPU, up to 8 GiB, at most two running sessions) rather than GPU training. YCRC documents `salloc -p agent --mem=8G -t 8:00:00`, and explicitly prohibits running coding agents on login nodes. Availability and permissions must be checked for the intended account. Jobs invoked by an agent still use their regular Slurm resources.

The YCRC `local-coding-agents` service has a constrained filesystem/credential boundary; use its docs rather than assuming an ordinary remote Codex CLI has the same protections. External commercial models have different data handling requirements.

## 14. Fast troubleshooting decision tree

**Cannot SSH:** check Yale VPN/on-campus network, alias `ssh -G`, registered *public* key, correct course-specific `User`, Duo prompt; try interactive Terminal before automating. A username with course prefix is not the same as personal NetID.

**Cannot submit:** inspect `sacctmgr` association/QOS, live partition, GPU GRES name, account, maximum submitted jobs, walltime, CPU/memory/GPU TRES, existing jobs; don't use `sinfo` alone. `education_gpu` often has a strict per-user submission limit.

**Pending forever:** `squeue -j JOBID --start`, `scontrol show job JOBID` reason, current queue/priority; consider a permitted smaller request, not uncontrolled duplicate submissions.

**Container command unavailable:** `apptainer` belongs on a compute node; allocate CPU or GPU first. Check image and `--nv` bindings; image builds may need substantial scratch/host memory.

**OOM or incorrect GPU:** capture `nvidia-smi`, UUID/mapping, PyTorch CUDA devices, Slurm allocated devices, initial occupancy, host memory vs VRAM; diagnose before changing model size or switching GPU class.

**Job completed with no results:** inspect Slurm stdout/stderr, exit code and explicit scientific outputs. Confirm source commit, input data, valid-task yield, actual optimizer steps, checkpoint checksums and complete manifest.

**Credentials/logging:** never print secrets to job output. Use existing registered key/Duo and separate mode-600 files; no credentials in repositories or Slurm scripts.

**Policy/support ambiguity:** ask course instructor/TF first for course scope; email `research.computing@yale.edu` for YCRC technical permission and unexpected node/device behavior. Give exact Slurm job ID, partition, command, observed error and what you tried, rather than a vague request.

## 15. What the other project's coding agent should implement

Create a small `docs/yale-hpc.md` and add a concise `AGENTS.md` section with the **new SSH alias**, authorized user/account and verified paths. Build an environment-specific adapter that:

1. Performs read-only introspection without allocating GPUs.
2. Uses Git-pinned source and a project-specific remote directory; records science and environment versions.
3. Validates resources and prepares a small CPU/GPU smoke, then submits **only authorized** jobs with unique run IDs and durable logs.
4. Gives `status`, `logs`, `fetch`, `cancel` and optional `resume` actions with clear human-readable error handling.
5. Never guesses current queue availability, impersonates another account, duplicates an ambiguous submission, or spins on a known site-level limitation.
6. Implements checkpoint-safe time limits and explicit output validation. Adds measured GPU/memory/cost summaries after pilots.
7. Introduces an isolated execution worker only if its research method genuinely executes untrusted generated code.

The entire old `selfplay hpc` framework is unnecessary unless the new project also demands multi-method frozen studies, long-run orchestration, stringent artifact identity and automated retries. Reusing small tested engineering patterns is preferable to copying hundreds of project-specific options or scientific blockers.

## 16. Direct sources / future verification

### Official YCRC (prefer live YCRC information over historical handouts)

- [Bouchet cluster: partitions, GPU types and limits](https://docs.ycrc.yale.edu/clusters/bouchet/)
- [Course accounts, education partitions, account expiry and permitted scope](https://docs.ycrc.yale.edu/clusters-at-yale/access/courses/)
- [SSH setup](https://docs.ycrc.yale.edu/clusters-at-yale/access/ssh/)
- [Advanced SSH config / connection multiplexing](https://docs.ycrc.yale.edu/clusters-at-yale/access/advanced-config/)
- [MFA (Duo)](https://docs.ycrc.yale.edu/clusters-at-yale/access/mfa/)
- [Yale VPN](https://docs.ycrc.yale.edu/clusters-at-yale/access/vpn/)
- [Slurm job scheduling](https://docs.ycrc.yale.edu/clusters-at-yale/job-scheduling/)
- [HPC storage and **Bouchet's 30-day scratch purge**](https://docs.ycrc.yale.edu/data/hpc-storage/)
- [Transfer node / rsync / scp](https://docs.ycrc.yale.edu/data/transfer/)
- [Apptainer containers](https://docs.ycrc.yale.edu/clusters-at-yale/guides/containers/)
- [Coding agents on Bouchet](https://docs.ycrc.yale.edu/ai/aicodingtools/)
- [YCRC-hosted coding-agent interfaces](https://docs.ycrc.yale.edu/ai/local-coding-agents/)

### Previous project (verified real operational history; not general YCRC policy)

- [Operations](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/operations.md)
- [Yale runbook](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/yale-launch-runbook.md)
- [Worker support correspondence and YCRC response](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/yale-worker-support.md)
- [Task 07 accepted resource-isolation fixes](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/task_completion/07-implemented-yale-execution-blocked-readiness.md)
- [Task 08 frozen readiness results](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/task_completion/08-implemented-task-learnability-probe.md)
- [Task 09 latest efficiency/launch caveats](https://github.com/tatsu432/self-play-opsd-coding-agent/blob/main/docs/task_completion/09-implemented-efficiency-learnability.md)

**Record status when used in the next project:** `SSH_ALIAS=<new alias>`, `REMOTE_USER=<verified>`, `SLURM_ACCOUNT=<verified>`, `PARTITION=<verified>`, `GPU_GRES=<verified>`, `PROJECT_ROOT=<verified>`, `SCRATCH_ROOT=<verified>`, `QUOTAS=<verified>`, `DATE=<inspection date>`, `TEST_JOB_ID=<actual ID>`. Until confirmed, these are **unknowns**, not blockers to writing the new project's code or designing lightweight CPU tests.
