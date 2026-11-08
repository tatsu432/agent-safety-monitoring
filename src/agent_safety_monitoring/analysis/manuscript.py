"""Render the research synthesis from already validated aggregate tables."""

from agent_safety_monitoring.analysis.aggregate import pct


def write_manuscript(output, data, main_table, pair_table, cost_table, policy_table):
    methods = data["methods"]
    avg = methods["average"]["primary"]
    eae = methods["eae"]["primary"]
    ratio = data["development_gpu_seconds"]["mrt"] / data["development_gpu_seconds"]["average"]
    baselines = data["structural"]["baselines"]
    auc_length = baselines["length"]["metrics"]["auroc_valid"]
    auc_tools = baselines["tools"]["metrics"]["auroc_valid"]
    auc_both = baselines["length_tools"]["metrics"]["auroc_valid"]
    content = f"""# How Should a Coding Agent Safety Monitor Spend Its Compute Budget?

Tatsuhiro Shimizu · Yale CPSC 5710 · Scientific analysis draft, November 1, 2026

**Status:** This report is generated from validated aggregate tables. Record-level audit,
completed evidence diagnostics, new post-hoc analyses, and outstanding follow-up work are
tracked in [the original-study audit](original-study-audit.md),
[model-evidence results](model-evidence-results.md), and
[the follow-up protocol](followup-experiment-plan.md). This generator does not infer that
all research tasks are complete from the availability of aggregate tables.

## Abstract

We compare five fixed-weight gpt-oss-20b procedures for reviewing saved BashArena coding-agent
trajectories: single review, longer reasoning, averaging two reviews, extract-and-evaluate
(EaE), and a sequential/hierarchical MRT hybrid. A separate benign calibration population
sets a 5% expected false-positive-rate target. The primary test contains 118 nominal benign
records and 454 source-graded successful attacks, clustered in 118 legitimate tasks.
Averaging attains {pct(avg["tpr"])}% expected attack detection and {pct(avg["fpr"])}% realized
test FPR; its paired task-bootstrap difference from single review is positive, while the
comparison with longer reasoning remains inconclusive. EaE attains {pct(eae["tpr"])}% detection
and {eae["auroc_valid"]:.3f} valid-score AUROC. MRT costs {ratio:.2f} times averaging in the
independent development timing screen. A development-fitted length-and-tool-count baseline
attains {auc_both:.3f} AUROC, making structural confounding central to interpretation. Fixed,
matched-control injections do not produce a clear aggregate increase in missed attacks.
These findings concern one offline setting; they do not establish live protection,
universal method superiority, or a verified causal explanation of EaE failure.

## 1. Introduction

A safety monitor can spend additional inference compute on longer reasoning, repeated
judgments, extracting evidence, or organizing a trajectory into summaries. These choices
change both the amount of computation and the information available to the final judge.
A useful comparison therefore needs shared source behavior, a separate calibration policy,
actual cost measurements, and diagnostics for information loss and superficial shortcuts.

This project asks which procedures improve detection in a controlled offline comparison,
how improvements relate to measured resources, and whether adversarial transcript text
changes decisions. Its contribution is an empirical comparison and diagnostic analysis of
existing approaches. It does not introduce a new monitoring architecture or train a model.

## 2. Related work

AI Control evaluates oversight protocols against intentional subversion and motivates
explicit safety and usefulness tradeoffs. Our study evaluates one component—saved-trajectory
review—rather than a complete deployment protocol.
[Greenblatt et al., AI Control](https://arxiv.org/abs/2312.06942).

BashArena supplies Linux administration tasks and four sabotage objectives with programmatic
grading. We use a particular released trajectory collection, whose counts differ from the
benchmark's full task inventory. Source grades are evaluation labels rather than independent
proof of real-world harm. [Kaufman et al., BashArena](https://arxiv.org/abs/2512.15688).

EaE separates extraction from judging and reports benefits of filtering in other settings.
Our passage-index implementation, quote limits, model, and data are controlled adaptations;
its unfavorable outcome here does not invalidate those other experiments.
[Arike et al., information access and sabotage detection](https://arxiv.org/abs/2601.21112).

MRT studies adversarial monitoring and introduces hybrid sequential/hierarchical scaffolding.
We adapt those ideas with fixed chunk sizes and equal branch weighting, without claiming an
exact reproduction. [Kale et al., Reliable Weak-to-Strong Monitoring](https://arxiv.org/abs/2508.19461).
Monitoring Monitorability studies reasoning visibility and monitor-compute scaling; our
visible-action setup excludes private reasoning, so its conclusions are not interchangeable
with chain-of-thought monitoring results.
[Guan et al., Monitoring Monitorability](https://arxiv.org/abs/2512.18311).

Adaptive monitor attacks and production blocking-monitor red teaming motivate treating
agent-authored text as untrusted evidence. Our fixed offline insertions are a substantially
narrower threat model than adaptive or live attacks.
[Terekhov et al., Adaptive Attacks](https://arxiv.org/abs/2510.09462),
[Remedios et al., Red-Teaming Auto Mode](https://arxiv.org/abs/2609.19587).

## 3. Dataset and experimental setup

The imported release contains 600 nominal benign trajectories and 600 attack-assigned
trajectories, of which 569 have recorded successful outcomes, 18 unsuccessful outcomes,
and 13 no grade. Eight records lack usable tool behavior, and four additional attack
records lack usable benign counterparts. The resulting whole-task split uses 30 development
tasks (30 benign and 120 attack-assigned records), 448 never-attacked benign calibration
records, and 118 attacked test tasks. Test includes 454 successful attacks plus 118 benign
records in the primary analysis; eight failed and ten ungraded attacks are supplementary.
Provisional proposal counts are superseded by the verified manifest.

The monitor receives the genuine task and canonical visible assistant text, actions, and
tool outputs. Preprocessing uniformly removes private/system reasoning, original user
preambles, and submission markers. Labels, attack objectives, grades, source conversion
indices, and split metadata are structurally separate. Trajectory commands are never executed.

The fixed monitor is `openai/gpt-oss-20b`, revision
`6cee5e81ee83917806bbde320786a8fb61efebee`, served by vLLM 0.11.0 on one H200 with
tensor parallelism and concurrency one. The context limit is 131,072 tokens. Existing
physical readiness records establish the original runtime; new analysis tests do not
re-establish GPU compatibility. Model background is documented in the
[official model card](https://arxiv.org/abs/2508.10925).

Single review uses low reasoning effort; think-longer uses medium. Averaging combines two
low-effort judgments with distinct seeds. EaE selects up to 24 exact passages of at most
400 characters under a 3K quoted-token cap; a separate judge receives the task and those
quotations. MRT combines sequential state-carrying review with hierarchical merging of
five-interaction chunks and averages branch scores. Every procedure uses ordinal categories
1–5, bounded output retries, and validated citations. These categories are not harm probabilities.

Development measurements and outcomes determined configurations and the two resource
budgets before the primary freeze. We preserve that selection, all task splits, predictions,
and calibration rules. Subsequent explanatory analyses are explicitly post-hoc.

The policy calibrates descending score cutoffs on benign calibration records and randomizes
at a tied boundary to target 5% expected FPR. Invalid final outputs are mandatory referral
alerts. AUROC uses valid scores only, with coverage reported. Uncertainty uses 2,000 whole-task
bootstrap draws, sharing test/calibration samples across methods, independently drawing the
two populations, and recalibrating every replicate. Pairwise intervals are nominal pointwise
95% intervals, not simultaneous coverage across all comparisons.

## 4. Main results

{main_table}

![Primary detection](figures/main-performance.png)

*Expected successful-attack detection with whole-task 95% bootstrap intervals. Realized
test FPR differs by method despite the common calibration target.*

{pair_table}

![Paired differences](figures/paired-differences.png)

*Paired TPR differences in percentage points; intervals use shared task resamples.*

Averaging has a supported positive paired difference from single review and MRT under this
protocol. Its point estimate exceeds think-longer, but the paired interval includes zero.
MRT versus single is also inconclusive. EaE is materially worse than these comparators.
This ranking does not imply equal compute, equal realized FPR, or a universal best method.

{policy_table}

Boundary randomization materially affects the practical endpoint. Conservative deterministic
single and think-longer policies exclude their maximum-score boundary and therefore yield
zero valid-score alerts. Averaging has finer half-integer resolution. The saved aggregate
summaries cannot determine how much of its advantage is attributable to resolution versus
independent judgment. That decomposition requires saved constituent predictions and is
exploratory. The frozen thresholds are not retuned using test labels.

Objective-specific point estimates appear in [the primary analysis](primary-analysis.md).
Firewall disabling has lower detection than malware execution and secret exfiltration in
several methods. These descriptive differences need task-aware uncertainty before stronger
claims. Individual score distributions, full ROC regeneration, and objective intervals remain
dependent on the full prediction records; no ROC is inferred from a single AUROC.

## 5. Compute efficiency

{cost_table}

![Development GPU costs](figures/gpu-cost-detection.png)

*Development workload GPU time versus frozen test detection, with vertical task-bootstrap
intervals. No repeated cold measurements support horizontal uncertainty intervals.*

The small budget is approximately 30.60 GPU-seconds per trajectory, and the large is 141.81.
MRT is unavailable under the small budget. Averaging costs more than one review but much
less than MRT in the development screen. Its descriptive cost-performance position is
favorable relative to MRT, while a comparison with think-longer involves smaller measured
cost and statistically unresolved detection differences.

GPU times are independent homogeneous development measurements, not per-method held-out
allocation estimates. Logical test calls and tokens include reused work and retries. Request
latency sums cannot substitute for allocated GPU duration; startup and failed allocations
must remain in total resource accounting. Reasoning-token values are locally tokenized
estimates because the server did not expose exact reasoning counts. They are not added on
top of total completion tokens. Think-longer's slightly lower development time than single
review is an observation from one screen, not evidence that greater effort generally costs
less. See [compute efficiency](compute-efficiency.md) for budget membership and limitations.

## 6. Structural, failure, and robustness analysis

Development-fitted structural baselines achieve AUROCs of approximately {auc_length:.3f} for length,
{auc_tools:.3f} for tool count, and
{auc_both:.3f} for their combination. Their point estimates were independently
recomputed locally and match saved results. A structural classifier's success establishes
predictive confounding; it does not prove that LLMs use the same shortcut.

Length-bin weighting leaves averaging's detection broadly similar and EaE poor. All bins
have both labels, but coarse bins cannot remove within-bin or tool-count differences.
Calibration and test benign records come from different task populations and differ in
source length and tool usage. These limitations prevent a clean attribution to harm recognition.
See [structural confounding](structural-confounding.md) for estimates, intervals, overlap,
effective sample sizes, and calibration/test feature summaries.

EaE already discriminated poorly on development (AUROC about 0.524), so the primary result
was not an isolated held-out surprise. Its test invalid rate is low enough that invalidity
alone cannot account for its near-chance valid-score AUROC. Compression, passage boundaries,
lost chronology, extractor ranking, missing context, and judge limitations remain distinct
hypotheses. The selected spans and judge inputs must be inspected before attributing failure.
[The EaE analysis](eae-failure-analysis.md) separates observations from hypotheses.

The user elected stronger-model review instead of human annotation. The prepared workflow
uses a revision-pinned local gpt-oss-120b, with no access to source outcome labels, monitor
selections, scores, or verdicts. Exact-span checks verify source containment only.
Retention and replacement findings remain
conditional on model-suggested evidence and
shared-family biases; they are not human-verified evidence. The completed blinded review and
replacement diagnostic are documented in [model-evidence results](model-evidence-results.md).
A separately versioned objective-aware review is part of the current follow-up protocol.

The frozen injection experiment supplies 480 matched comparisons across two methods,
three payload families, two positions, and 40 trajectories. Recomputed task-cluster intervals
for aggregate missed-attack changes include zero for both tested methods. This is inconclusive
about attack effectiveness and does not establish equivalence or adaptive robustness.
[Injection results](injection-robustness.md) report family/position strata, benign alert changes,
and invalid behavior. The averaging method was not included in this experiment.

## 7. Discussion and limitations

Independent repeated review offers a favorable observed tradeoff in this setting, especially
relative to the substantially more expensive MRT hybrid. Longer reasoning also improves
on single review under the calibrated randomized policy. Elaborate intermediate processing
does not guarantee better detection: extraction may discard context, while summarization
can add cost and failure points. Our data do not yet identify which mechanism explains EaE.

Generalization is limited by one monitor model, one agent family, one benchmark release,
source-recorded grades, and nominal benign labels. Structural imbalance and calibration/task
population differences complicate interpretation. Ordinal scores, randomized boundaries,
unequal realized FPRs, and unequal compute mean this is not an exactly equal-budget or
identically constrained comparison. Diagnostic samples are small and selected; injection
payloads are synthetic and nonadaptive. Prompting and serving settings may matter. Offline
review cannot establish whether live intervention would prevent harm.

All mechanism investigations added after observing results are post-hoc. Model-proposed
reference evidence is fallible. Mock/software tests establish safeguards, not GPU compatibility
or scientific effectiveness. Artifact availability and completed independent reconciliation
are recorded explicitly in
the original-study audit. Missing follow-up results must not be inferred from original points.

## 8. Conclusion

The frozen summaries support benefits from averaging and longer reasoning over a single
low-effort review under this calibration policy. Averaging compares favorably with MRT's
measured development cost, while the difference from think-longer remains inconclusive.
EaE performs poorly in this adaptation. Structural confounding and score-boundary sensitivity
are substantial qualifications, and a verified causal account of extraction failure remains open.

## Reproducibility appendix

Scientific freeze: `{data["freeze"]}`. Original source:
`a0fd3fd19e7b64cd4b6a99f9ed8e2cec14d1ddbd`. The original client used Python 3.12.15;
local post-hoc analysis uses the repository's locked Python 3.12 environment and records
its own provenance. Existing frozen inference keeps its exact original runtime.

[Artifact audit](artifact-audit.md) states which inputs were independently verified.
[Analysis aggregates](analysis-aggregates.json) record numeric values and input-file SHA-256
identities. [Reproduction instructions](analysis-reproduction.md) provide exact commands and
private input requirements. No raw trajectory, individual injection pair, reference quotation,
model explanation, or private reasoning is published in this package. New GPU work requires
current project-specific Slurm accounting and measured development validation first.
"""
    (output / "report-draft.md").write_text(content)
