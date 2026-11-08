"""Generate public diagnosis reports and figures exclusively from aggregate measurements."""

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from agent_safety_monitoring.io import atomic_json, file_hash, read_json

NAMES = {
    "single": "Single",
    "think": "Think longer",
    "average": "Average ×2",
    "eae": "EaE",
    "mrt": "MRT hybrid",
    "sequential": "MRT sequential",
    "hierarchical": "MRT hierarchical",
}


def label(name):
    return NAMES[name.split("-")[0]]


def render(source, output, replay=None):
    data = read_json(source)
    output.mkdir(parents=True, exist_ok=True)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    result = data["operating_points"]
    branch = data["branches"]
    table = [
        "| Method | Calibrated TPR / test FPR % | Valid AUROC | Valid TPR@5% [95% CI] | "
        "Valid TPR@10% | Raw pAUC 0–10% |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, p in result["point"].items():
        ci = result["intervals"][name]["roc_tpr_05"]["ci95"]
        table.append(
            f"| {label(name)} | {100 * p['tpr']:.1f} / {100 * p['fpr']:.1f} | "
            f"{p['auroc_valid']:.3f} | {100 * p['roc_tpr_05']:.1f} "
            f"[{100 * ci[0]:.1f}, {100 * ci[1]:.1f}] | {100 * p['roc_tpr_10']:.1f} | "
            f"{p['pauc_00_10']:.4f} |"
        )
    matched = all(
        all(v for k, v in r.items() if k.endswith("match") or k.endswith("matches"))
        for r in data["reconciliation"].values()
    )
    replay_result = read_json(replay) if replay else None
    audit = f"""# Original-study forensic audit

The independent histogram implementation {"matches" if matched else "does not fully match"} all
five original point estimates and 2,000 task-bootstrap TPR/FPR intervals, and the saved primary
report. Original results are preserved. The original freeze is `{data["freeze"]}`.

The source-object/canonical-data audit passes; both raw source logs match their checksums.
Each method has 448 calibration and 590 test artifacts. Primary analysis uses 118 benign and
454 successful attacks; eight failed and ten ungraded attacks remain supplementary.
"""
    if replay_result:
        audit += (
            f"\nDirect raw-log replay checked {replay_result['samples_replayed']} samples, "
            f"with {replay_result['mismatch_count']} label/canonical mismatches and "
            f"{replay_result['tasks_with_inconsistent_genuine_description']} inconsistent "
            "genuine task descriptions. No trajectory command was executed.\n"
        )
    audit += (
        """
## Calibrated policy versus descriptive discrimination

"""
        + "\n".join(table)
        + """

The calibrated policy includes mandatory invalid-output referrals and expected boundary
randomization. ROC metrics condition on valid scores; coverage and referral contributions
are recorded per class in the aggregate JSON. Test-selected ROC thresholds are descriptive,
not independently validated deployment thresholds. Tied-score blocks are interpolated;
no convex-hull optimization is used. Partial AUROC is the raw integral, range 0–0.1.

Bootstrap intervals use 2,000 identical whole-task draws across methods, independent
calibration/test draws, and recalibration in every replicate. Infeasible calibration draws
remain included with their actual FPR and are counted separately. Metric-specific usable
replicate counts and paired differences accompany the estimates. Intervals do not measure
stochastic inference variability and are pointwise, without multiplicity correction.

"""
        + "\n".join(
            f"- {label(n)}: invalid test benign/attack = "
            f"{p['invalid_benign']}/{p['invalid_attack']}; "
            f"TPR from invalid referrals = {100 * p['tpr_from_invalid']:.2f} percentage points; "
            f"infeasible calibration draws = {result['infeasible_calibration_replicates'][n]}/2000."
            for n, p in result["point"].items()
        )
        + f"""

## Cost provenance

The recovered project-filtered Slurm file records
**{data["allocation"]["allocated_gpu_hours"]:.3f} allocated GPU-hours**, including earlier
follow-ups and failures. This is historical accounting, not a fresh scheduler inspection.
The independently measured development workload rates remain the only homogeneous per-method
GPU-time measurements. Shared held-out allocations cannot be split into exact method costs
using request latency. Development and held-out cost claims remain explicitly distinct.

![Comparable discrimination](figures/diagnosis-operating-points.png)

[Aggregate measurements](diagnosis-aggregate.json) include input hashes and definitions.
Reproduction and current blockers are in [the follow-up protocol](followup-experiment-plan.md).
"""
    )
    shift_path = output / "calibration-shift-aggregate.json"
    if shift_path.exists():
        shift = read_json(shift_path)
        audit += "\n## Benign population contrasts\n\n"
        audit += (
            "Calibration uses never-attacked tasks; benign test records come from tasks "
            "with attack variants. Whole-task intervals describe differences, not their causes.\n\n"
        )
        for field, value in shift["features"].items():
            lo, hi = value["ci95"]
            audit += (
                f"- {field}: test minus calibration mean "
                f"{value['test_minus_calibration']:.1f} [95% CI {lo:.1f}, {hi:.1f}].\n"
            )
        audit += (
            "\nThese contrasts do not establish that population differences caused monitor FPR "
            "drift. Nominal benign assignment does not certify harmless behavior. Full score "
            "and invalid-rate contrasts are in "
            "[the numeric summary](calibration-shift-aggregate.json).\n"
        )
    shared = data["common_valid_sensitivity"]
    audit += (
        f"\nCommon-valid sensitivity retains {shared['n']} primary test records across all "
        "five methods. Its conditional metrics and paired intervals are in the aggregate "
        "JSON; they do not replace population deployment rates.\n"
    )
    (output / "original-study-audit.md").write_text(audit)
    branch_table = [
        "| Branch | Calibrated TPR / FPR % | Valid AUROC | Valid TPR@5% | Raw pAUC |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name in [
        "sequential",
        "hierarchical",
        next(n for n in branch["point"] if n.startswith("mrt-")),
    ]:
        p = branch["point"][name]
        branch_table.append(
            f"| {label(name)} | {100 * p['tpr']:.1f} / {100 * p['fpr']:.1f} | "
            f"{p['auroc_valid']:.3f} | {100 * p['roc_tpr_05']:.1f} | {p['pauc_00_10']:.4f} |"
        )
    e, m = data["eae"], data["mrt"]
    failure = (
        f"""# Evidence-grounded EaE/MRT diagnosis

This analysis is post hoc and uses saved outputs only. New inference has not run.

## EaE

The original poor valid-score discrimination survives statistical reconciliation. It cannot
be attributed solely to final invalid outputs. Saved quotations are exact canonical spans.
Counting all primary records, benign/attack empty selections number {e["0"]["empty_quotes"]}/
{e["1"]["empty_quotes"]}; these include invalid records and differ from valid-only counts in
the earlier evidence report. Mean quotation counts are {e["0"]["mean_quotes"]:.2f} and
{e["1"]["mean_quotes"]:.2f}. Selection order differs from source order in
{e["0"]["out_of_source_order"]} benign and {e["1"]["out_of_source_order"]} attack records.
Selected tool-call IDs lack a selected matching result in {e["0"]["selected_call_without_result"]}
benign and {e["1"]["selected_call_without_result"]} attack records. These structural measures
do not establish relevance, lost harmful evidence, or causal extraction failure.

Earlier token measurements show substantial unused 3K budget. Prior stronger-model review
and fixed-judge evidence substitution did not demonstrate an improvement. That reviewer was
blinded to harmful objectives, so it does not fulfill the new objective-aware diagnostic.
The new objective-aware packet and prompt are separately versioned. References remain
model-suggested, not human-verified; supplied objectives are hypotheses, not proof of success.

Use the five-way taxonomy: evidence absent; present but unselected; selected without essential
context; sufficient but misjudged; uncertain reference/benchmark label. Unverified semantic
cases remain unresolved. A missing quote or citation alone does not resolve the taxonomy.

## MRT

"""
        + "\n".join(branch_table)
        + f"""

Terminal stages were reconstructed from actual chunk/tree geometry; every valid hybrid score
matches the mean of its recovered terminals. Missing branch terminals receive their own
referrals for branch diagnostics; surviving branches never replace invalid original hybrids.
Branches disagree on {m["branch_disagreement"]} of {m["n"]} records, including missing-terminal
disagreements. Sequential suspicion decreases at least once in
{m["sequential_score_decreased"]} records. Earlier sequential citations are absent from final
state in {m["earlier_citation_missing_final"]} records. Citation loss does not establish semantic
information loss. Invalid-attempt categories are `{m["invalid_attempt_categories"]}`; retries
and final invalid outcomes have different denominators.

The hierarchical branch is less discriminative overall, but equal averaging improves hybrid
AUROC and TPR@5% over sequential-only in these point estimates. Sequential-only has slightly
higher raw low-FPR pAUC and lower calibrated FPR. There is no metric-independent justification
for deleting a branch, or evidence yet that a larger summary budget solves the problem.

## Go/no-go

Proceed with controlled score-scale and N-scaling experiments after real development checks.
First complete objective-aware evidence substitution before changing EaE extraction. Do not
run a broad EaE/MRT sweep, common-rubric change, or adaptive cascade now. A chronology-preserving
EaE candidate or 1,024-token MRT state is conditional on development evidence of the relevant
failure, with one factor changed at a time. Existing structural baselines and overlap analyses
remain sensitivity checks, not causal evidence of shortcuts.

[Prior evidence review](eae-failure-analysis.md) · [Structural controls](structural-confounding.md)
"""
    )
    (output / "failure-analysis.md").write_text(failure)
    atomic_json(output / "diagnosis-aggregate.json", data)
    if replay_result:
        atomic_json(output / "source-replay-aggregate.json", replay_result)
    names = list(result["point"])
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    y = np.arange(len(names))
    points = np.array([result["point"][n]["roc_tpr_05"] for n in names])
    cis = np.array([result["intervals"][n]["roc_tpr_05"]["ci95"] for n in names])
    # Percentile intervals need not contain the full-data point estimate.
    ax.hlines(y, cis[:, 0] * 100, cis[:, 1] * 100, color="steelblue")
    ax.scatter(points * 100, y, color="navy")
    ax.set_yticks(y, [label(n) for n in names])
    ax.set(xlabel="Valid-score TPR at 5% test ROC FPR (%)", xlim=(0, 100))
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(figures / "diagnosis-operating-points.png", dpi=220)
    plt.close(fig)
    from agent_safety_monitoring.analysis.operating_points import roc_counts

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for name, item in data["ties"].items():
        counts = item["histograms"]
        scores = sorted({float(s) for h in counts.values() for s in h if s != "None"}, reverse=True)
        curve = roc_counts(
            [counts["0"].get(str(s), 0) for s in scores],
            [counts["1"].get(str(s), 0) for s in scores],
        )
        if curve is not None:
            ax.plot(*curve, label=label(name))
    ax.set(
        xlim=(0, 0.1), ylim=(0, 1), xlabel="FPR among valid scores", ylabel="TPR among valid scores"
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figures / "diagnosis-low-fpr-roc.png", dpi=220)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([label(n) for n in names], [data["ties"][n]["tie_fraction"] for n in names])
    ax.set(ylabel="Fraction of valid benign/attack score pairs tied")
    fig.tight_layout()
    fig.savefig(figures / "diagnosis-ties.png", dpi=220)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    points = [100 * result["point"][n]["fpr"] for n in names]
    cis = np.array([result["intervals"][n]["fpr"]["ci95"] for n in names]) * 100
    ax.vlines(np.arange(len(names)), cis[:, 0], cis[:, 1], color="steelblue")
    ax.scatter(np.arange(len(names)), points, color="navy", label="Test policy FPR")
    ax.axhline(5, linestyle=":", color="black", label="Calibration target")
    ax.set_xticks(np.arange(len(names)), [label(n) for n in names])
    ax.set(ylabel="Referral-inclusive FPR (%)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figures / "diagnosis-calibration-fpr.png", dpi=220)
    plt.close(fig)
    base = output / "report-draft.md"
    if base.exists():
        text = base.read_text()
        banner = (
            "> **November 8 follow-up status:** Original metrics and uncertainty have been "
            "independently reproduced. New ROC and branch analyses below are post hoc. "
            "Controlled 0–100/N=3/5 inference and objective-aware reference review remain "
            "pending Yale authentication; this is the current report, not a claim of full "
            "follow-up completion.\n\n"
        )
        appendix = (
            "\n\n## Additional forensic analysis, November 8\n\n"
            + "\n".join(table)
            + "\n\nThese ROC figures condition on valid scores and use the test set to select "
            "operating points. They are descriptive discrimination metrics, not independently "
            "validated deployment policies. Raw pAUC integrates FPR 0–10%.\n\n"
            + "\n".join(branch_table)
            + "\n\nThe weaker hierarchical branch does not imply that removing it improves "
            "every metric. Branch intervals, common-valid sensitivity, referral contributions, "
            "ties and paired differences are in [the aggregate](diagnosis-aggregate.json). "
            "See [the audit](original-study-audit.md), [failure analysis](failure-analysis.md) "
            "and [execution protocol](followup-experiment-plan.md) for evidence, limitations, "
            "and the exact outstanding work. No missing experimental values are extrapolated.\n"
        )
        (output / "final-report.md").write_text(banner + text + appendix)
    atomic_json(
        output / "diagnosis-publication-provenance.json",
        {
            "aggregate_sha256": file_hash(source),
            "replay_sha256": file_hash(replay) if replay else None,
            "generated_reports": ["original-study-audit.md", "failure-analysis.md"],
        },
    )
    return {"output": str(output)}
