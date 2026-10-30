# Pre-main-experiment readiness

Assessment date: October 29, 2026. **Conditional NO-GO for main inference:**
real online W&B is not authenticated, and the frozen-runtime guard changes have
not yet been exercised on an allocated GPU. No held-out inference was performed.

The real scientific freeze was created in the clean Yale checkout
`/nfs/roberts/project/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring-frozen-prep`
at source commit `a0fd3fd19e7b64cd4b6a99f9ed8e2cec14d1ddbd` and Python 3.12.15.
Its SHA-256 content identity is
`b86533ed57f70956b55d8a5e26eac1f833dc622ef92b36060e1f71382c70ae5d`.
The frozen configuration, accepted pilot evidence and freeze are retained under
`runs/` in that checkout, and copied into the ignored local `runs/readiness/`.
The checkout is separate from the user's working tree and original Yale checkout.

The new checkout's locked environment setup stalled in Yale NFS I/O both on
project storage and scratch; both attempts were terminated without allocating a GPU.
The scratch environment is incomplete. The freeze was created using the existing
locked Python 3.12.15 environment with the clean checkout source on `PYTHONPATH`.
Complete the checkout environment setup before allocating a GPU.

To satisfy the project requirement for online monitoring, configure Yale's W&B
credentials through a secure interactive login or environment mechanism without
putting secrets in Git, Slurm arguments or chat, then verify aggregate-only online
telemetry. Perform a short Slurm development-only smoke check of the frozen-runtime
guards before any held-out inference. Keep the 90 GPU-hour total cap, including
all previous allocations; reconcile `sacct` again before submitting. The main
calibration and test jobs have not been submitted.

Engineering implementation and software tests do not by themselves establish
held-out scientific effectiveness.

## Update: completed cold screen and corrected selection

This update supersedes the earlier historical status and estimates below. Slurm H200
job `31312445` completed all five 40-record development screens in 8,634 allocated
seconds; dependent selection job `31312454` completed. Total reconciled project GPU
use is **22,526 seconds (6h 15m 26s)**, including earlier failures. No jobs were
active at the latest check. The five methods had respectively 0, 0, 0, 0 and 2 invalid
results in the order single, think, average, EaE 3K and MRT. Both MRT failures were
citation validation in summary merges and remain referral outcomes. The corrected
selection accepts MRT at the prespecified 5% limit: the original selection computed
`1 - 38/40` as slightly greater than 0.05. The fix compares integer counts, with
boundary tests for 2/40 and 3/40. The original selection artifact is preserved;
`runs/selection-corrected.json` on Yale records the corrected result.

All five configurations are available in the large budget; MRT exceeds the small
budget. Independent cold measured GPU seconds per trajectory were 15.30, 14.18,
26.77, 13.67 and 141.81 respectively. Development AUROC is a noisy selection
statistic for this 40-record sample, not a held-out effectiveness result. The EaE
3K AUROC was 0.524; assess its detection performance on the frozen held-out study,
not by adjusting it using held-out data. MRT is exactly at the feasibility limit.

The measured projection for the 448 calibration, 572 primary test, and 18
supplementary trajectories is 26.35, 33.64 and 1.06 GPU-hours, respectively,
with shared configurations deduplicated. Matched injections, up to 40 records ×
three families × two positions × attack/control × single/EaE, add 3.86 hours;
ten 90-second startups add 0.25 hours. The resulting **65.16 GPU-hour** central
remaining estimate and **81.45 GPU-hour** estimate with 25% contingency use the
40-record screen's observed rates; actual trajectory lengths, retry rates and
startup costs may differ. A conservative **90 GPU-hour total allocation cap**
(including the 6.26 hours already consumed) accommodates this estimate within the
user's authorization to continue GPU work. This is an agent-selected numeric cap,
not a number supplied by the user. No main-study job was launched.

The physical pilot used one NVIDIA H200, tensor parallelism and concurrency one,
model revision `6cee5e81ee83917806bbde320786a8fb61efebee`, vLLM 0.11.0 and
container SHA-256 `056a8f8f182b1652c88ecf567d11dfa18a5b0a7ddd33d17b3fcc5d5869731c03`.
The complete-cohort context audit still matches the current manifest and prompt
identity. The selection-only boundary correction did not change monitor prompts or
GPU inference code; the original benchmark source identity remains in its artifacts.
Local lint passed and the complete suite now has **57 passing tests**. Online W&B
still has no Yale API key or netrc credential; local artifacts remain authoritative.

The corrected selection, reviewed pilot evidence, verified runtime details and measured
cap are now included in the immutable freeze described above. The selection-only
correction and final frozen-runtime checks have not been physically re-run on a GPU.
Online W&B remains unauthenticated; no held-out study has been run.

The remainder of this report records the earlier state and investigation; earlier
unqualified GPU totals, cost estimates, selection status and proposed next actions
are historical and superseded by this update.

## Verified evidence

The local starting commit was `c4a6ff1` on `feat/monitoring-study`. Supplied edits to
`AGENTS.md` and the new task specification were preserved. Yale's existing checkout
was at `00cef91`; implementation was staged in a separate sibling worktree,
`/nfs/roberts/project/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring-readiness`,
without replacing its previous job artifacts or source checkout.

Job `31252913` contains the documented 40 development records, balanced 20/20.
Pinned-tokenizer CPU replay against canonical source confirmed the following final
EaE failures:

| Final cause | Records |
| --- | ---: |
| Nonexistent source passage index | 4 |
| Quoted-token budget exceeded | 7 |
| Schema, truncation, context overflow, transport, citation, other | 0 |
| Total invalid | 11 / 40 (27.5%) |

Across **all extraction attempts**, including corrected attempts on otherwise valid
records, replay found 5 schema failures, 7 invalid-index failures, 13 quotation-budget
failures, and 1 truncated generation. Over-budget selections contained **1,230–2,827
quoted tokens against a 1,000-token limit**. These attempt counts overlap at the
trajectory level and must not be added to the final record counts.

Private diagnostic output is retained under `runs/readiness/eae-original.json` on
Yale and locally. It contains opaque sample IDs and diagnostic counts, not public
transcripts. The seven earlier EaE trials were also replayed: **28 records, 20 final invalids**
(5 exact-source-span mismatches, 9 schema failures, 4 truncations, 2 invalid indices).
Across their attempts: 9 source-span, 22 schema, 7 truncation, 4 index and 1 budget
failures. These tiny historical trials are diagnostic evidence, not feasibility screens.

The repaired complete-prompt tokenizer audit covered all **1,200 records**, with
**zero overflows**, maximum **121,593 prompt tokens**, and **8,320 tokens reserved**
for output/retry/headroom under the 131,072-token limit. Its prompt hash is
`8d50660386d9d4242f52c429c70e7cb917508bcf5432af647aaaffd4c8d0daa9`.
The fixed 40-record screen also passed: maximum 78,266 prompt tokens, zero overflows.
These are CPU context checks, not proof of GPU memory fit.

## Implemented changes

- EaE retains every original 400-character passage, segment role/type and canonical
  tool linkage. Each passage now has one global integer ID and exact token cost.
  Compact `id/token_cost: text` prefixes limit context overhead. A bounded structured
  schema and deterministic resolver replace model-generated step/index pairs.
  Exact spans, the unchanged 1K/3K caps, distinct selections and judge-only evidence
  remain validated. Corrective feedback includes actual selected cost and limit.
- Structured/transport failures retain diagnostic categories and private attempt
  records. Infrastructure failures are separate from completed invalid scientific
  judgments. Failed or interrupted calls never receive substitute scores.
- Immutable shard membership, process locks, saved-result identity validation,
  corrupt-file preservation, cached intermediate-call recovery, attempt journals,
  bounded signal draining and per-attempt summaries support recovery.
- Local status heartbeats and incremental progress counters avoid repeated full
  aggregation. They expose completion, validity, errors, calls, tokens, cache reuse,
  estimated remaining time and job lineage. GPU CSV sampling is read incrementally
  for safe utilization/memory aggregates; local allocation files retain device IDs.
- W&B uses scalar/metadata whitelists, unique attempt identities and stable scientific
  groups, with online/offline/disabled modes. Source upload, console capture and
  automatic system collection are disabled. Tracking failures preserve local work.
- Stable benchmark trial IDs distinguish recovery from new cold-cache measurement.
  Resumed or incomplete timing trials cannot establish independent cold cost.
  Submission intent and Slurm comments protect against ambiguous duplicate submission.
- Selection validates real trial provenance, cohort coverage and execution comparability.
  Budget-aware reports use measured development GPU-seconds, explicitly separate from
  logical tokens and actual job allocations. Freeze requires selected-method feasibility,
  matching accepted runtime/hardware, immutable container identities and actual approval.

## Tests actually executed

- Local lint, shell syntax, diff checks and package build passed; new modules were
  verified inside the distributable wheel.
- Local CPU suite: **55 passed**, including 20 readiness cases.
- Yale Linux final readiness suite: **20 passed in 10.46 seconds**, including both
  final freeze-guard cases.
- Recovery tests cover a crash after cached extraction, interruption between records,
  compatible restart, corrupt results/cache, wrong method identity, changed limits/shard
  geometry, cross-process duplicate ownership, infrastructure failure and retry.
- Existing tests retain structured/HTTP retry, quote/citation isolation, MRT state bounds,
  task isolation, freeze mutation rejection, calibration ties/referrals and paired bootstrap.
- New benchmark tests distinguish resumed timings from cold trials and skip completed work.
  New report checks verify that the cost axis uses measured GPU-seconds, not token counts.
- A real **W&B 0.31.0 offline run** initialized, recorded scalar completion and closed.
  No cloud dashboard or online delivery has been verified. Disabled tracking and failure
  fallback were tested with software fixtures.

Real Slurm warning/draining and result-level GPU interruption recovery were exercised
successfully in the jobs below. The newest fast-child-exit shell fix, frozen-runtime checks and tracking-failure
status fields are CPU-tested changes made after the staged GPU snapshot; they are not
claimed physically validated. Successful online delivery, GPU interruption inside a
multistage call, and concurrency improvements remain unverified. Concurrency stays one.

## GPU resources and real development validation

Before this work, reconciled `sacct -X` usage was **12,635 allocated GPU-seconds =
3h 30m 35s**. Final usage is **13,892 GPU-seconds = 3h 51m 32s**, including failures
and the two new jobs. The four-hour allowance has **508 seconds = 8m 28s remaining**.
No jobs remained queued or running at final reconciliation. Typed and untyped GRES
entries were not double-counted.

Current association remains account `cpsc4710`, QOS `interactive,normal`. Explicit
course-group quota inspection succeeded. Scratch is not backed up and has a 30-day
purge policy; preserve final artifacts on project storage and export deliverables.

| Job | Physical allocation | Outcome |
| --- | ---: | --- |
| `31302433` | 1 H200 × 1,084 seconds | Slurm FAILED after controlled USR1 shutdown; 40 1K and 35 3K results preserved |
| `31304229` | 1 H200 × 173 seconds | COMPLETED; skipped the 35 persisted 3K results and completed only five missing records |

The first job requested 20 minutes, received its warning at 18 minutes, and drained
cleanly. A proposed extension was rejected by Slurm permissions and never took effect.
Only after terminal-state reconciliation was the four-minute resume allocation submitted.
Both jobs stayed within the original cap; no extra resource authorization was inferred.
The server log records `torch.bfloat16` compute, `mxfp4` quantization and tensor
parallel size one. Server startup was 56 and 106 seconds respectively. The second wrapper measured 169
seconds versus Slurm's 173; allocation accounting uses **Slurm**, not wrapper timing.

| Repaired EaE setting | Valid | Benign valid | Attack valid | Final failure causes | Feasibility |
| --- | ---: | ---: | ---: | --- | --- |
| 1K | 30/40 | 12/20 | 18/20 | 8 quotation-budget, 2 truncation | Infeasible: 25% invalid |
| 3K | 38/40 | 20/20 | 18/20 | 1 quotation-budget, 1 judge citation | Meets the prespecified limit: 5% invalid |

No final invalid-index failures remained in either setting. This is a small development
screen, not proof of detection effectiveness or of the held-out invalid rate. Preserve
both 3K failures as referral outcomes. The 1K setting remains unavailable; no validation
rule or budget was relaxed.

The 1K cold workload took 623.30 GPU-seconds (15.58 per trajectory). The 3K workload
segments totaled 459.83 GPU-seconds (11.50 per trajectory), retaining the interrupted
segment's costs. **3K is not an independent cold timing trial**, so the selection gate
correctly requires a new comparable measurement before acceptance. The 35 reused
results do not reduce its reported historical workload cost.

Online W&B initialization failed in real execution; computation, local heartbeats,
GPU utilization/memory sampling and private call journals continued. Successful online
tracking needs a working authenticated/network configuration. Offline events were
verified locally; the synthetic private marker was absent from all offline artifacts.

Yale logs are `logs/eae-repair-31302433.out` and
`logs/eae-repair-resume-31304229.out` in the readiness worktree. The authoritative
measurement ledger is `runs/eae-repair/trials/eae-repair-1/pilot-measurements.json`;
submission lineage is `runs/readiness/submissions.json`. Private result/diagnostic,
GPU/timing and allocation artifacts were copied locally under ignored `runs/readiness/`.

## Scientific review, selection and remaining cost

Code review and existing invariant tests preserve the intended five procedures:
low-effort single review; effort-only longer review; distinct repeated seeds and
complete averaging; quotation-only EaE judgment; ordered sequential MRT plus independent
hierarchical merges with equal branch weights. Full serialized summary caps and exact
source retention remain enforced. No benchmark commands are executed.

Labels/grades remain outside monitor-facing types. Whole-task splits, benign-only
calibration, successful attacks as primary positives, supplementary failed/ungraded
attacks, mandatory invalid referrals, randomized ties, valid-score AUROC coverage and
paired task bootstrap with recalibration remain unchanged. Structural fitting uses
only development data; injection payloads and neutral controls remain frozen inputs.

Development selection is **not finalized**. Prior screen settings for single, medium
thinking, two-sample averaging and five-interaction MRT were valid on all 40 records;
The repaired 3K EaE setting now meets development feasibility, while 1K remains
infeasible. Four-record trials cannot establish the ten-valid-per-class rule.
Accepted final settings still need consistent provenance and comparable real timings.
The strengthened selection gate may require fresh comparison workloads; repeating the
four unaffected screened workloads costs roughly **2.2 H200 GPU-hours plus startup**.
A concrete **2.5-GPU-hour additional development allowance** would cover that validation
plus a fresh 3K timing screen with modest overhead. On October 29 the user authorized continued GPU use without further approval requests.

Provisional remaining-cost projection uses the original four non-EaE screen rates
and the repaired 3K cumulative workload rate. The latter is explicitly resumed, not
cold selection proof. This projection does not finalize scientific configuration selection:

| Component | H200 GPU-hours |
| --- | ---: |
| Calibration: 448 records | 26.14 |
| Primary test: 572 records | 33.38 |
| Supplementary test: 18 records | 1.05 |
| Injections: up to 40 records, three families, two positions, matched controls | 3.47 |
| Further development assumption | 2.50 |
| Startup assumption: ten allocations × 90 seconds | 0.25 |
| Central remaining estimate | **66.78** |
| Conservative estimate: central + 25% contingency | **83.48** |

These estimates are not authorization or final selected-budget costs. MRT dominates
runtime. Invalid extractions omit judge calls; retain invalid coverage when interpreting costs.
Held-out lengths, final selected variants, concurrency and secondary analysis may
change cost. Shared budget configurations must be deduplicated. Recalculate using
repaired-method measurements before requesting a full-study cap.

## Go/no-go and exact remaining actions

**NO-GO for calibration/test inference.** The 3K screen meets feasibility, but accepted
comparable timing/selection proofs and finalized configurations remain outstanding.
The user has authorized GPU work without further approval requests; choose and record
a measured resource cap before substantial full-study jobs. No approval artifact or real scientific freeze was fabricated.

1. Review the saved jobs and private diagnostics; retain 1K as infeasible and the two
   3K referral outcomes. Reproduce status with `asm experiment status --run-root PATH`.
2. Complete the authorized five-method cold screen in Slurm job **31312445**, using
   a 6.5 GPU-hour project cap for the 150-minute allocation. Do not rerun the known-
   infeasible 1K configuration without a changed hypothesis.
3. Run `experiment select` on complete comparable trials, verify budget membership,
   and record accepted pilot/readiness evidence. Keep concurrency one unless an approved
   development measurement justifies changing it consistently across methods.
4. Repair W&B online authentication/network setup. Local monitoring remains authoritative
   if the service is unavailable; no benchmark text may be uploaded.
5. Refresh the full-study estimate and record a measured full-study cap within the user’s
   authorization. Commit reviewed
   implementation and supplied user changes before creating the real scientific freeze.
6. Verify container/hardware metadata, freeze the finalized cohort/settings and only then
   launch approved calibration/test shards. Complete diagnostics and final analysis afterward.

The staged GPU source snapshot was archived before updating the readiness worktree:
`runs/readiness/gpu-source-snapshot.tar.gz`, SHA-256
`347253bd798bd46d82b75f10c2c61680ba7ce3f0100cb71a3907fca01a9f56a6`.
This preserves the exact code used by both jobs alongside their source hashes.
The five-method cold screen was submitted as job **31312445** following the user’s
authorization to continue GPU work without further approval requests. CPU selection
job **31312454** depends on successful completion of the screen. The benchmark was
queued at submission; no new GPU time had been charged at that point.

Executable status, diagnosis, resume, submission, selection, freeze and report commands
are in [operations](../operations.md). Physical execution and final scientific analysis
remain distinct milestones.
