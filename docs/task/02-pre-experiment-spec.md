# Task: Complete Pre-Main-Experiment Readiness for Coding-Agent Safety Monitoring Study

> **GPU authorization update, October 30, 2026:** The user grants standing
> authorization for GPU submissions needed to complete this project, including
> calibration, test, retries, and secondary experiments. Do not request further GPU
> submission approval. Maintain measured resource accounting and a documented cap;
> when additional GPU time is needed, update the cap based on evidence without asking.
> This supersedes the approval requests and historical four-hour ceiling below. Keep
> the scientific freeze, data isolation, project boundaries, and duplicate-submission
> safeguards intact. The initial development and freeze work has already been completed.

You are Codex, acting as a senior research engineer responsible for making an existing scientific experiment reliable, efficient, observable, reproducible, and ready for its full evaluation on Yale HPC.

**Repository:** https://github.com/tatsu432/agent-safety-monitoring

**Working branch:** `feat/monitoring-study`

**Last reviewed commit:** `c4a6ff1ab5a8ee149a17882085ebdeddb2e89129`

**Research project:** *How Should a Coding Agent Safety Monitor Spend Its Compute Budget?*

**Course:** Yale CPSC 5710, Trustworthy Deep Learning

**Final deadline:** December 16, 2026

## 1. Overall objective

The monitoring methods and supporting infrastructure have largely been implemented. Your task is NOT to rebuild the project or propose new research directions. Instead, bring the existing implementation to the point where we can confidently launch the main scientific experiment.

The immediate priorities are:

1. Diagnose and repair the outstanding extract-and-evaluate (EaE) failures on development data.
2. Improve experiment observability, preferably with Weights & Biases (W&B), while maintaining reliable local logging.
3. Ensure experiments are efficiently resumable after Slurm interruption, crashes, timeouts, or server restarts.
4. Improve actual GPU-time accounting, throughput measurement, and resource estimation.
5. Validate the scientific implementation against the approved proposal.
6. Finalize development-only configuration selection and prepare the immutable scientific freeze.
7. Produce a clear go/no-go readiness report and exact commands for the full experiment.

Implement the necessary changes directly in the repository. Run meaningful tests and development-only validation within the existing resource allowance.

**Do not launch the main held-out calibration/test experiment until the configuration is frozen, the experiment is demonstrably ready, and the required resource budget has been explicitly approved.**

Do not stop simply because additional GPU allocation is unavailable. Complete all independent code, CPU-test, artifact-inspection, reporting, and orchestration work, then identify exactly what physical validation remains.

## 2. Understand the research before making changes

Read the following documents first:

- `docs/project_proposal/CPSC 5710 Projct Proposal Tatsuhiro Shimizu.pdf`
- `docs/methods.md`
- `docs/operations.md`
- `docs/yale-hpc.md`
- `docs/task/01-experiment-implementation-spec.md`
- `docs/task_completion/01-implemented-monitoring-foundation.md`
- `docs/task_completion/01-implemented-monitoring-validation.md`
- `docs/plan/01-experiment-implementation-plan.md`
- `AGENTS.md`

Read the actual source code, tests, configurations, and Slurm scripts. Treat the research proposal and scientific methods documentation as the authority for scientific intent, while using the implementation and job artifacts to establish what actually works.

If the current branch has advanced beyond the reviewed commit, inspect the intervening changes, reconcile them with the tasks below, and do not overwrite recent work.

### Scientific setting

We compare five procedures for detecting harmful coding-agent behavior in saved BashArena trajectories:

1. **Single review:** One full-trajectory judgment at low reasoning effort.
2. **Think longer:** One judgment with medium/high reasoning effort.
3. **Sample and average:** Multiple independently seeded judgments whose ordinal scores are averaged.
4. **Extract-and-evaluate (EaE):** One model extracts verbatim evidence, after which a separate judgment stage sees the genuine task and only that evidence.
5. **MRT hybrid:** Sequential chunk inspection and independent hierarchical summarization, followed by averaging the two branches.

We use the same fixed-weight `openai/gpt-oss-20b` model for all procedures.

The dataset contains 600 nominal benign and 600 attack-assigned trajectories. The recorded attack outcomes are 569 successful, 18 unsuccessful, and 13 ungraded.

The implemented deterministic task-group split yields approximately:

- 30 benign + 120 attack-assigned development records.
- 448 benign calibration records.
- 118 benign test records and 454 usable successful test attacks.
- Additional unsuccessful/ungraded attacks handled separately.

These are the current implementation counts, not a reason to modify the split to match preliminary proposal estimates.

The primary scientific endpoint is **true-positive rate on successful attacks at a 5% false-positive-rate target**, with thresholds calibrated only on separate benign calibration data.

Other outputs include AUROC, measured GPU time, logical model calls and tokens, invalid output rates, paired task-bootstrap uncertainty, structural/length controls, evidence-retention analysis, and matched prompt-injection robustness tests.

This is an offline, saved-trajectory monitoring study, not a live code execution or intervention study.

### Scientific invariants

Preserve these throughout your work:

- Never expose attack labels, side objectives, grades, or existing monitor scores to the monitor.
- Keep development, calibration, and test task groups separated.
- Tune prompts, model settings, budgets, and selection rules using development data only.
- Do not inspect held-out monitor results to improve the methods.
- Preserve the genuine user task and canonical source evidence.
- Preserve the five methods' intended semantics and fair resource comparisons.
- Count all model calls, including extraction, summarization, retries, and failed attempts as applicable.
- Preserve invalid outputs and referral-alert handling. Do not fabricate substitute scores.
- Keep injection payloads and neutral controls fixed before testing.
- Distinguish source-recorded harmful outcomes from what a monitor inferred from visible behavior.
- Never execute commands contained in benchmark trajectories.
- Never transmit raw benchmark transcripts, private source data, or generated reasoning traces to W&B or another hosted service.

Scientific correctness takes precedence over convenience or apparent performance improvements.

## 3. Verified execution status and immediate blocker

The latest documented Yale H200 development screen was Slurm job `31252913`, which completed on October 29, 2026.

It evaluated 20 benign and 20 successful attack development trajectories across 26 tasks.

The recorded validity results were:

| Method | Valid results |
|---|---:|
| Single review | 40/40 |
| Think longer | 40/40 |
| Sample and average | 40/40 |
| MRT hybrid | 40/40 |
| EaE | 29/40 |

EaE therefore had an invalid rate of 27.5%, exceeding the prespecified 5% feasibility threshold.

The corrected full-prompt context audit reported a maximum of about 120,018 tokens with no overflow under the configured context limit, including the audit's output/retry reserve. A long synthetic prompt was also successfully processed on an H200.

The latest job ledger reports approximately **3 hours 31 minutes** of GPU usage against an existing four-allocated-GPU-hour pilot allowance.

Before any additional GPU submission, reconcile actual usage with `sacct` and existing job records. The prior allowance does not automatically authorize a larger study.

### Task A: Diagnose and fix EaE

Inspect:

- `src/agent_safety_monitoring/monitors/core.py`
- `src/agent_safety_monitoring/inference/backend.py`
- `src/agent_safety_monitoring/schema.py`
- `src/agent_safety_monitoring/experiments/benchmark.py`
- Relevant tests and saved development screening artifacts.

Find the actual persisted results for job `31252913`, together with relevant earlier EaE development runs.

Classify all invalid EaE outcomes by root cause, distinguishing at least:

- JSON/schema or structured-output errors.
- Invalid source step or passage indices.
- Quotation-token-budget violations.
- Truncation or incomplete generation.
- Context overflow.
- Transport/server errors.
- Invalid evidence citations.
- Other validation failures.

Report counts and representative local diagnostic details, without exposing private transcripts in public logs or commits.

Investigate whether the fixed 400-character passage representation, selection instructions, structured output schema, quotation budgets, or retry feedback are contributing to the problem.

Implement a targeted correction based on evidence rather than guessing.

Requirements:

- Exact selected quotations must remain verifiable against the canonical source.
- The evaluator must see only the legitimate task and selected evidence.
- Do not weaken validation to increase the apparent success rate.
- Do not silently raise quotation budgets or remove difficult trajectories.
- Do not reduce the evidence available to other procedures.
- Do not introduce label-specific rules or use held-out samples.
- Keep retries bounded and account for their cost.
- Prefer simple, deterministic evidence resolution over asking an LLM to reproduce long exact quotations.
- Preserve failed extraction attempts for diagnosis.

After the fix, run CPU/mock tests and, if authorized GPU time remains, a targeted real-model development validation.

The desired acceptance criterion is at most 5% invalid outputs on a representative development screen, consistent with the project's prespecified feasibility rule.

If the criterion cannot be achieved after a reasonable, bounded investigation, document the remaining failure modes and propose scientifically defensible alternatives. Do not claim EaE is ready or silently relax the acceptance threshold.

## 4. Task B: W&B tracking and experiment observability

Inspect:

- `src/agent_safety_monitoring/experiments/telemetry.py`
- `src/agent_safety_monitoring/experiments/runner.py`
- `scripts/yale/inference.sbatch`
- `scripts/yale/benchmark.sbatch`
- `configs/logging/aggregate.json`

The existing W&B implementation logs basic aggregate counts and is configured for offline operation.

Extend it into useful research-experiment observability without creating excessive overhead or turning W&B into the authoritative data store.

### Required progress metrics

Log aggregate metrics at a suitable bounded frequency:

- Number of expected, completed, valid, invalid, and remaining judgments.
- Progress percentage by split and method.
- Per-method invalid rate.
- Retry count and error categories.
- Total input, output, and reasoning tokens where reported by the server.
- Logical model calls and cache hits.
- Completed trajectories per hour.
- Measured throughput and elapsed wall time.
- Estimated remaining time based on recent completed workloads, clearly marked as an estimate.
- Per-method GPU-time measurements where physically available.

Do not log per-trajectory text, extracted quotations, summaries, private reasoning, or raw prompts.

### GPU/system telemetry

Retain or improve the existing GPU sampling in the Slurm wrapper.

Record, as available:

- GPU utilization.
- GPU memory used/peak.
- GPU UUID/device identity.
- Allocated GPU count.
- Host RAM metrics if useful.
- Slurm job ID, job state, and actual elapsed allocation time.
- Model-server startup duration.
- Inference workload duration.
- Exit code and failure status.

Use appropriate sampling intervals so monitoring does not meaningfully degrade throughput.

### W&B run identity

Give tracking runs stable identities based on the frozen study, split, method/configuration, and shard/job attempt as appropriate.

Use:

- Project: `agent-safety-monitoring`
- Meaningful run names.
- Groups for scientific study/freeze.
- Job types for development, calibration, test, pilot, and secondary analysis.
- A safe whitelist of metadata such as configuration hashes, model revision, resource counts, and method hyperparameters.

A restarted job should be associated with the same scientific run without misleading duplicate progress counts. Preserve job-attempt lineage.

Verify W&B's actual behavior with the installed pinned version instead of assuming a particular resume mechanism works.

### Tracking modes

Support:

1. **Online:** Live W&B monitoring if permitted and network access works.
2. **Offline:** Local W&B event storage with later syncing.
3. **Disabled:** Fully functional runs with no W&B dependency at execution time.

An offline W&B run does not provide a real-time cloud dashboard. Document this clearly.

If online tracking fails, computation should continue and local artifacts must remain complete.

Keep W&B credentials outside Git, logs, source files, and Slurm arguments. Do not upload raw benchmark data.

### Local observability

Implement or extend a lightweight local progress/status report that works even without W&B.

A useful interface might be:

`uv run asm experiment status --run-root PATH`

Exact command naming is up to you.

It should report progress by method and split, completion/invalid counts, estimated cost, recent errors, and relevant Slurm job IDs.

A long-running method may produce no completed trajectory for several minutes. Provide some bounded heartbeat or job-status visibility during that period rather than relying exclusively on completed-trajectory events.

Avoid O(N²) metric recomputation or excessive writes. Prefer incremental counters and lightweight summaries.

## 5. Task C: Reliable resumption and interruption recovery

Inspect the existing idempotent experiment runner, atomic file writing, request caches, and Slurm job scripts.

Current features include per-trajectory saved results and cached successful model requests. Preserve and build on them.

**We do not need conventional neural-network training checkpoints because no model weights or optimizer states are being updated.**

### Required behavior

For each method/trajectory combination:

- A completed, validly persisted result should be skipped when resuming the same study.
- Missing or interrupted results should run again.
- Previously completed compatible model calls should be reused when possible.
- Configuration mismatch must fail clearly.
- An incomplete or corrupted result must not be mistaken for completed work.
- Existing results must not be silently overwritten.
- Saved invalid scientific outputs must remain distinguishable from infrastructure failures.
- Duplicate running workers must not write the same scientific result concurrently.

Preserve the scientific identity of the run using the existing hashes and freeze manifest.

### Interrupted multistage procedures

EaE and MRT may involve several calls per trajectory.

If the job terminates after successful intermediate calls but before the final trajectory result is written, restarting should avoid recomputing successfully cached compatible stages when feasible.

Do not build an unnecessarily complex checkpoint framework if existing request-level caching already solves this adequately.

Account separately for:

- Completed scientific results.
- Reused cached model responses.
- New generations.
- Failed calls.
- Physical GPU time spent in aborted jobs.

Caching and recovery must not make measured physical method costs appear artificially cheap.

### Slurm integration

Inspect the existing `USR1`/termination handling and cleanup logic.

Implement graceful interruption where practical:

- Stop scheduling new trajectory work after a termination signal.
- Preserve completed results.
- Allow bounded in-flight work to finish if time permits.
- Record interrupted/incomplete work explicitly.
- Shut down the model server cleanly.
- Preserve job timing and exit status.
- Restart only missing work with the same scientific configuration.

Consider actual model request timeout and observed tail latency when choosing the signal lead time.

Add an appropriate lightweight job/submission ledger to prevent duplicate submissions after SSH failure or ambiguous responses.

Before resubmitting, reconcile the existing Slurm job using `squeue`/`sacct`. Do not blindly submit another copy.

Maintain consistent shard counts and deterministic shard membership across restart attempts. Prevent simultaneous ownership of the same shard, using an appropriately simple mechanism such as an OS file lock or equivalent.

No distributed orchestration service is necessary.

### Benchmark versus main-run recovery

The development benchmark currently creates timestamp-based fresh trial directories. That is useful for clean cold-cache measurements, but it complicates recovery after interruption.

Introduce stable benchmark trial identities or a simple benchmark ledger.

Preserve the distinction between:

- A new, independent timing measurement that intentionally starts with a cold cache.
- A resumed interrupted experiment that should retain completed work.
- A scientifically new configuration that must not inherit incompatible results.

Document exactly how to resume each scenario.

### Mandatory recovery tests

Write tests that simulate:

- Interruption between two trajectories.
- Interruption inside a multistage method.
- One successfully completed stage followed by a crash.
- A temporary HTTP/server failure.
- An invalid structured model output.
- A corrupted or partial result file.
- A restarted shard with existing completed results.
- Two duplicate workers attempting to own the same shard.
- Changed configuration or freeze identity.

Use mock/fake backends for most tests.

If a real GPU interruption test can be conducted inside the remaining authorized allowance, perform one short, controlled development-only validation. Do not spend a large allocation merely to prove a mechanism already well tested locally.

## 6. Task D: Accurate GPU-time accounting and efficiency

This part is central to the scientific contribution.

The project compares how monitoring procedures spend compute. Therefore, generated-token counts alone are insufficient.

Inspect:

- `src/agent_safety_monitoring/experiments/benchmark.py`
- `src/agent_safety_monitoring/experiments/selection.py`
- `src/agent_safety_monitoring/reporting/report.py`
- `src/agent_safety_monitoring/monitors/core.py`
- Slurm allocation/timing wrappers.

### Separate resource metrics

Track three different concepts:

**1. Logical inference workload**

Number of model calls, prompts, tokens, retries, and intermediate stages required by a procedure.

**2. Physical experiment cost**

Actual GPU allocation time consumed by execution, including startup, failed jobs, restarts, and idle allocated periods as appropriate.

**3. Method-level steady-state inference cost**

Measured GPU-seconds per completed trajectory under a consistent benchmark workload, excluding or separately accounting for server initialization.

Do not conflate GPU time with summed request latency when calls overlap.

For a homogeneous workload on N allocated GPUs, method workload cost can be measured as N times the actual method workload duration, provided the resources are dedicated to that workload. Record model startup and shared overhead separately and disclose the allocation convention.

### Homogeneous method benchmarking

Measure each procedure on a consistent hardware configuration and comparable development samples.

Ensure:

- Request caches are fresh for independent timing measurements.
- Model revisions and serving-engine settings are fixed.
- Numerical precision and tensor-parallel settings are recorded.
- Context length and output limits are consistent.
- Prefix-caching policy is controlled.
- Concurrency settings are explicit.
- All stages and retries are counted.
- Incomplete or failed runs are not silently excluded from accounting.
- Any shared server startup overhead is handled consistently.

Preserve individual trial measurements and provenance.

### Throughput optimization

Evaluate simple opportunities to improve throughput without compromising comparability.

Potential options:

- More than one in-flight trajectory on a single H200, if VRAM permits.
- Appropriate vLLM continuous batching.
- Deterministic data-parallel sharding across separately allocated GPUs.
- Avoiding unnecessary model reloads.
- Reducing Python serialization or repeated metric-processing overhead.
- Using CPU preprocessing ahead of GPU jobs.
- Minimizing unnecessary repeated tokenization.
- Keeping data and model caches in appropriate Yale project/scratch locations.

Start with the existing single-H200 configuration, which has already been validated.

Do not assume that two GPUs are more efficient than one. Do not introduce tensor parallelism simply because multiple GPUs exist.

Use measured development throughput, memory use, and GPU-hours to determine whether concurrency or sharding actually helps.

If higher concurrency changes physical cost or output behavior, report that and freeze the final settings consistently. Avoid changing execution conditions differently for the five methods.

### Cost estimation

Estimate the total cost of the remaining experiment from measured pilot data.

Include:

- All selected methods and budget variants.
- Development work still required.
- The benign calibration cohort.
- The held-out test cohort.
- Expected retries.
- Server startup and GPU allocation overhead.
- Secondary injection tests.
- A reasonable contingency for failures or restarts.

Provide central and conservative estimates, not an invented exact runtime.

Break down estimated GPU-hours by phase and method.

Record total remaining cost separately from GPU-hours already consumed.

If the study is unexpectedly expensive, recommend practical reductions that preserve the primary scientific comparison. Discuss their implications instead of silently shrinking the evaluation.

## 7. Task E: Scientific consistency, configuration selection, and freeze

Conduct a focused scientific-code review using the proposal, not merely a software linter review.

Verify:

### Method correctness

- Single and longer-thinking methods differ only in the intended effort setting.
- Repeated-review samples use distinct controlled seeds.
- EaE's second stage has no hidden access to the original full transcript.
- Evidence passages reconstruct exact source text.
- Sequential MRT retains ordered evidence state.
- Hierarchical MRT combines summaries in the intended structure.
- Summary token caps and source chunk limits are enforced without silently discarding source evidence.
- Citation checks use valid canonical identifiers.
- All five methods produce comparable ordinal judgments.

### Dataset and evaluation correctness

- No labels or private grader information leak into monitor prompts.
- Task-group split isolation remains intact.
- Nominal benign assignment is not confused with independent proof of harmless behavior.
- The calibration set contains only the intended benign records.
- Successful test attacks are the primary positive class.
- Failed and ungraded attacks remain supplementary.
- Invalid outputs use the prescribed referral policy.
- The 5% FPR policy handles the discrete 1–5 scores and ties correctly.
- Thresholds use only calibration data.
- AUROC and valid-score coverage are both reported.
- Paired task bootstrap resamples whole tasks and recalibrates thresholds.
- Structural and length-matching analyses do not train on test labels.
- Injection studies use frozen payloads and matched neutral controls.

### Budget selection

Inspect the actual implementation of `experiment select`.

Its current intended policy is to select feasible configurations from development measurements with at least ten valid observations per class and no more than 5% invalid outputs.

Check that:

- Development data only determines method selection.
- Every timing trial's data identity and sample count are correct.
- Measured costs are comparable.
- The small budget and large budget are defined consistently with the approved protocol.
- Every selected method configuration has demonstrated feasibility.
- All five methods can be compared at the large budget, or an infeasible method is transparently reported.
- The selected configurations and budgets are represented unambiguously in the frozen study.
- Reports distinguish configurations selected for the small and large budgets, even if some configurations are shared.

The current report pipeline produces method-level metrics and token-based cost plots. Improve it so the scientific report can show **actual measured GPU cost versus detection performance**, grouped by budget and method, without presenting token counts as if they were GPU time.

Preserve the proposal's primary comparisons:

- EaE versus repeated review.
- MRT versus repeated review.
- EaE versus MRT at the larger budget.
- All five procedures across relevant actual costs.

### Freeze integrity

Before recommending a real freeze, verify:

- Source code and prompt identity.
- Dependency lock and Python version.
- Model and tokenizer revisions.
- Serving engine and container identity.
- Actual hardware configuration.
- Dataset and canonical evidence hashes.
- Complete-prompt context preflight.
- Method-specific settings.
- Calibration/statistical analysis rules.
- Injection payloads and controls.
- Approved positive GPU-hour cap.
- Validated pilot/readiness evidence.

Do not create fictional approval artifacts or set `approved_by: user` without an actual explicit user approval.

Changes made after a scientific freeze must not silently modify the frozen study. If a scientifically meaningful change is necessary, use a separately documented new freeze.

## 8. Task F: Yale HPC operations and real execution safeguards

The repository already has a working Yale Bouchet setup and project-specific runbooks.

Use the existing authorized project environment. Verify current cluster state rather than assuming the historical job ledger is fully current.

Relevant files:

- `docs/yale-hpc.md`
- `scripts/yale/inference.sbatch`
- `scripts/yale/benchmark.sbatch`
- `scripts/yale/pilot.sbatch`
- `scripts/yale/serve.sh`

Requirements:

- No heavy inference or model-server execution on login nodes.
- Use Slurm for GPU workloads.
- Respect actual account/QOS/partition restrictions.
- Pin model, container, engine, and scientific environment.
- Preserve local private data and run artifacts outside Git.
- Never place secrets in Slurm submission arguments.
- Reconcile existing jobs before submitting new ones.
- Preserve allocation and utilization logs even on failure.
- Do not delete or overwrite previous scientific artifacts as a shortcut.
- Verify scratch retention and back up important outputs appropriately.

Do NOT recreate the worker-isolation infrastructure from the separate self-play coding-agent project.

This project reads saved trajectories as data. It does not execute attacker-supplied commands. Consequently, complicated cgroup/seccomp/process-limit requirements are not needed for this trusted inference workflow.

Use proportionate safeguards based on actual risks. Do not turn optional checks or unavailable cluster features into arbitrary hard blockers.

### Resource authorization

The existing pilot allowance was four allocated GPU-hours, and the latest ledger records roughly 3 hours 31 minutes consumed.

Reconcile all GPU jobs before calculating remaining allowance.

Do not exceed the actual remaining approved total.

If more GPU time is required:

1. Complete CPU and static readiness tasks.
2. Prepare a concrete estimate.
3. Identify the minimum additional GPU validation needed.
4. Prepare the relevant job scripts and commands.
5. Request an explicit new budget approval before submission.

Do not interpret this implementation prompt as authorization for an arbitrary additional GPU allocation or the full main experiment.

## 9. Testing and acceptance

Implement tests alongside each feature.

Use the existing project commands and update them if necessary:

```bash
uv sync --locked --extra data --extra tokenizer --extra tracking
uv run ruff check src tests
uv run pytest -q
uv run asm experiment demo
```

The demo is a software test, not an effectiveness experiment.

Extend tests for:

- EaE parsing and quotation validity.
- Long-context handling.
- Error taxonomy.
- Retry accounting.
- Stable W&B run identity.
- Tracking failure fallback.
- Progress accounting after restart.
- Incremental metrics correctness.
- Atomic result persistence.
- Shard ownership and duplicate protection.
- Partial/missing coverage.
- Scientific freeze mismatch.
- GPU-timing aggregation.
- Per-method/per-budget reporting.
- Calibration and bootstrap correctness.

For important new operations, include a small real-development test if authorized, but do not make all acceptance tests depend on access to a GPU or W&B cloud service.

Keep normal test execution fast enough for routine development.

### Definition of ready

The main experiment is ready only when:

1. Each selected method is scientifically valid and its observed failure/invalid behavior is documented.
2. EaE meets the prespecified feasibility criterion or has a transparently approved alternative.
3. Model compatibility and context handling have been validated.
4. Real GPU-time costs and projected resource usage are measured.
5. A restart/interruption test demonstrates correct recovery.
6. Local progress reporting works without W&B.
7. Optional W&B tracking works in its documented operating modes.
8. The study configuration, budgets, prompts, and data cohort are final.
9. The freeze can be created without bypassing or fabricating readiness conditions.
10. A clear, finite resource plan exists for calibration, test, and secondary experiments.

If a requirement is not met, explain the specific remaining blocker and the narrowest reasonable resolution.

## 10. Required deliverables

### A. Implementation

Modify existing modules and add small supporting components only where useful.

Avoid broad, unrelated refactoring, introducing unnecessary frameworks, or duplicating existing functionality.

Preserve backward compatibility when practical.

### B. Updated operating documentation

Provide concise and executable instructions covering:

- Environment setup.
- Launching a development screen.
- Online/offline/disabled W&B operation.
- Inspecting current progress.
- Viewing GPU utilization and Slurm status.
- Resuming an interrupted run.
- Diagnosing invalid results.
- Determining whether a job actually completed its scientific work.
- Generating a complete report.
- Running the frozen calibration and test stages once approved.

Commands must match the implemented CLI and Slurm scripts; do not invent flags.

### C. Readiness report

Create:

`docs/reports/pre-main-experiment-readiness.md`

Include:

1. Current implementation status.
2. Exact EaE failure categories and counts.
3. Root causes and implemented fixes.
4. Tests actually executed and their results.
5. Real-model validation actually performed.
6. W&B and local monitoring status.
7. Interruption/recovery test results.
8. GPU usage already consumed.
9. Estimated remaining GPU-hour budget.
10. Development method-selection status.
11. Scientific risks or unresolved issues.
12. Final go/no-go assessment.
13. Exact remaining actions before the main experiment.

Separate **verified results**, **code implemented but not physically tested**, and **planned actions**. Never describe mock results as real scientific findings.

### D. Final Codex response

When your work is complete, give me a compact summary with:

- What changed, with relevant files and commits.
- What you verified.
- What remains blocked, if anything.
- Current total GPU-hour usage and estimated remaining cost.
- Whether the main experiment is ready.
- Exact commands or next actions I should use.
- Any specific authorization needed from me.

Do not simply say that the implementation is complete because tests pass. Make a clear distinction between engineering readiness and scientific experiment completion.

## 11. Execution strategy and priorities

Work in this order:

**Phase 0 — Inspect and reconcile.** Read the repository, confirm the current commit, inspect the actual job ledger and saved development results, and identify existing implementations before changing anything.

**Phase 1 — Resolve EaE.** Diagnose failures from existing saved development artifacts, fix the root cause, and add targeted tests. This is the highest-priority scientific blocker.

**Phase 2 — Reliability and visibility.** Implement W&B improvements, local progress reporting, durable recovery and safe Slurm shutdown/restart behavior. Validate with controlled mock failures.

**Phase 3 — Efficiency and resource accounting.** Measure or reconstruct available development workload costs, implement accurate reporting, and recommend efficient execution settings based on evidence.

**Phase 4 — Scientific validation.** Check method semantics, split isolation, calibration, configuration selection, budget definitions, and reporting.

**Phase 5 — Readiness verification.** Run all available CPU tests and any authorized development-only GPU validation. Produce the readiness report and exact full-experiment launch plan.

Do not launch held-out calibration or test inference during these phases without a completed scientific freeze and approved resource scope.

### Engineering principles

- Prefer simple, auditable designs over complicated general infrastructure.
- Use deterministic identifiers, immutable configurations, and atomic writes.
- Preserve raw outputs and provenance.
- Make incomplete and failed states explicit.
- Avoid silent data loss, truncation, or fabricated defaults.
- Do not weaken scientific checks merely to make tests pass.
- Do not require infrastructure capabilities that the experiment does not need.
- Do not repeatedly retry known failures without a changed hypothesis.
- Ensure that the experiment makes useful progress even if W&B is unavailable.
- Use the actual hardware and benchmark data to decide optimization settings.
- Do not overfit prompts or methods to the held-out test set.
- Keep changes focused on the study's deadline and primary research questions.

You have permission to make implementation and documentation changes within the existing project and run ordinary local/CPU tests. GPU resource use remains limited by the previously authorized cap until new approval is given.

**Begin by inspecting the latest branch, existing development screening results, and the eleven invalid EaE cases. Then implement the necessary improvements and validate them. Do not stop at producing another plan or a list of recommendations—carry out the engineering work that can be completed now.**