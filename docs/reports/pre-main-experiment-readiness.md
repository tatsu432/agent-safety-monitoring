# Pre-main-experiment readiness

Assessment: October 29, 2026. **GO for the frozen primary study within the 90
allocated GPU-hour total cap.** No calibration or test inference has been launched.
This is engineering and feasibility readiness, not evidence of held-out performance.

## Frozen study and development selection

The immutable freeze in the clean Yale checkout
`/nfs/roberts/project/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring-frozen-prep`
is `runs/study-freeze.json`, hash
`b86533ed57f70956b55d8a5e26eac1f833dc622ef92b36060e1f71382c70ae5d`.
Its source commit is `a0fd3fd19e7b64cd4b6a99f9ed8e2cec14d1ddbd`, with Python
3.12.15. Configuration, proof artifacts and a local copy of the freeze are retained
outside Git. The user's pre-existing instruction and task-spec changes were preserved.

The independent cold H200 screen (job 31312445) evaluated 40 balanced development
records per method. The corrected selector uses integer counts at the 5% boundary;
the original selector mistakenly classified 2/40 as greater than 5% because of
floating-point subtraction. The original and corrected artifacts are preserved.

| Method | Invalid | GPU seconds / trajectory | Development AUROC | Budget |
| --- | ---: | ---: | ---: | --- |
| Single | 0/40 | 15.30 | 0.898 | Small, large |
| Think, medium | 0/40 | 14.18 | 0.898 | Small, large |
| Average, 2 | 0/40 | 26.77 | 0.906 | Small, large |
| EaE, 3K tokens | 0/40 | 13.67 | 0.524 | Small, large |
| MRT, 5 interactions | 2/40 | 141.81 | 0.928 | Large only |

Both MRT invalids were citation failures in summary merges and remain referrals.
The small budget is 30.60 GPU-seconds per trajectory; the large is 141.81. Shared
configurations run once. Development AUROC is a noisy selection statistic, not a
held-out result. EaE's weak development AUROC and MRT's 5% boundary are risks to
report, not reasons to tune on held-out results.

Original EaE job 31252913 had 11 final invalid results: four nonexistent passage
indices and seven quotation-budget violations. Deterministic global passage IDs,
exact token-cost hints, bounded retries and error feedback corrected the failure
modes while retaining exact source verification and the unchanged quotation caps.
In the earlier repair screen 1K remained infeasible (30/40 valid), while 3K was
38/40 valid; resumed timing was not used for cold selection. Private diagnostics
and full intermediate outputs stay outside Git and W&B.

## Verification

- Local suite: 57 tests passed; lint, build and shell checks passed. A later
  launcher for the secondary injection experiment passed shell syntax checks but
  has not yet been exercised on a GPU.
- Full-cohort prompt audit: 1,200 records, no overflows, maximum 121,593 tokens,
  with 8,320 tokens reserved for output, retries and headroom. It matches the
  frozen data manifest and prompt hash. Existing real H200 long-context testing
  validates a large synthetic prompt, not every possible held-out memory shape.
- Pilot job 31312445 used one NVIDIA H200, tensor parallelism and concurrency one,
  vLLM 0.11.0, model/tokenizer revision `6cee5e81ee83917806bbde320786a8fb61efebee`,
  and SIF SHA-256 `056a8f8f182b1652c88ecf567d11dfa18a5b0a7ddd33d17b3fcc5d5869731c03`.
  The registry digest is `sha256:014a95f21c9edf6abe0aea6b07353f96baa4ec291c427bb1176dc7c93a85845c`.
- Real warning/drain and restart jobs 31302433 and 31304229 preserved 35 EaE results
  and completed the five missing results. Intermediate-call GPU interruption
  recovery has software coverage but has not been physically demonstrated.
- Frozen-runtime H200 smoke 31344058 completed all five development methods, one
  valid result each. Dependent CPU job 31344065 verified the freeze, complete cold
  measurements and saved outcomes. The locked inference environment installed 72
  cached packages; the apparent setup stall was slow per-file NFS processing.
- W&B login was verified. CPU Slurm job 31345287 successfully synced a synthetic
  allowlisted-scalar run from a compute node; no source text or private reasoning
  was sent. Its [verification run](https://forge.coreweave.com/wandb/tatsu432s/agent-safety-monitoring/runs/8d1d0f1767914626bdc34f53fe3f0236)
  is separate from the earlier GPU smoke, whose tracking had fallen back locally.
  Local progress and results remain authoritative if tracking fails.

## Resource plan and remaining work

Reconciled `sacct -X` usage including failures is **22,810 GPU-seconds, 6h 20m 10s**;
there are no active jobs. A **90 GPU-hour total cap** includes this consumption.
The user authorized continued GPU use without further approval requests; the 90-hour
number is an agent-selected cap based on the measured pilot, not a user-specified value.

The cold rates project calibration (448 records) at 26.35 GPU-hours, primary test
(572) at 33.64, supplementary test (18) at 1.06, and matched injection variants at
up to 3.86. With 17 startup allowances of 147 seconds, the central remaining estimate
is **65.61 GPU-hours**, or **82.01** with 25% contingency. Eight shards per primary
split plus one injection allocation motivate the startup assumption; retries may
need additional startups. Actual held-out lengths, failures and scheduling can differ.
This contingency plus consumed time is approximately 88.35 GPU-hours; monitor the cap
and do not assume it guarantees completion. Failed/ungraded attacks are never primary
positives, and invalid judgments remain referral alerts.

The actionable, serial, cap-checked Slurm commands are in
[operations](../operations.md). Use the frozen checkout and preserve shard geometry;
never execute trajectory commands. Run calibration and test, check complete coverage,
then compute the report and secondary analyses. The injection Slurm launcher is a
syntax-checked, separately checksummed operational artifact; its actual GPU behavior
remains unverified until the secondary study is run. No training, held-out inference,
or scientific results are implied by this readiness assessment.
