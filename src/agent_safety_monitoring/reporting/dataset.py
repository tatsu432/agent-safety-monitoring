"""Shareable aggregate audit, without raw benchmark text or per-record identifiers."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from agent_safety_monitoring.io import atomic_json, digest, read_json


def dataset_report(data: Path, output: Path):
    manifest, audit = read_json(data / "manifest.json"), read_json(data / "audit.json")
    by_id = {r["trajectory_id"]: r for r in manifest["records"]}
    output.mkdir(parents=True, exist_ok=True)
    summary = {k: v for k, v in audit.items() if k != "features"}
    context_path = data / "context-audit.json"
    if context_path.exists():
        context = read_json(context_path)
        if context["manifest_hash"] == digest(manifest):
            summary["context"] = {
                k: context[k]
                for k in ["total", "overflow", "max_prompt_tokens", "physical_backend_validated"]
            }
    summary["lengths"] = {}
    length_key = "source_tokens" if audit["tokenizer_audited"] else "characters"
    groups = {}
    for assignment in ["benign", "attack"]:
        features = [
            f for f in audit["features"] if by_id[f["trajectory_id"]]["assignment"] == assignment
        ]
        lengths = [f[length_key] for f in features]
        tools = [f["tool_calls"] for f in features]
        groups[assignment] = lengths
        summary["lengths"][assignment] = {
            "measure": length_key,
            "min": int(min(lengths)),
            "median": float(np.median(lengths)),
            "p95": float(np.quantile(lengths, 0.95)),
            "max": int(max(lengths)),
            "median_tool_calls": float(np.median(tools)),
        }
    summary["test_successful_attacks"] = sum(
        r["split"] == "test" and r["outcome"] == "success" and not r["exclusion"]
        for r in manifest["records"]
    )
    atomic_json(output / "dataset-summary.json", summary)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].bar(
        ["Benign", "Attack success", "Attack failed", "Ungraded"],
        [
            audit["counts"].get(k, 0)
            for k in [
                "benign/not_applicable",
                "attack/success",
                "attack/failure",
                "attack/ungraded",
            ]
        ],
    )
    axes[0].tick_params(axis="x", rotation=25)
    axes[0].set_ylabel("Released trajectories")
    for assignment, lengths in groups.items():
        x = np.sort(lengths)
        axes[1].step(x, np.arange(1, len(x) + 1) / len(x), label=assignment)
    axes[1].set(
        xlabel="Visible source tokens" if length_key == "source_tokens" else "Visible characters",
        ylabel="Empirical cumulative fraction",
    )
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(output / "dataset-characteristics.png", dpi=180)
    plt.close(fig)
    rows = [
        "# Dataset audit",
        "",
        "Real source measurements; no monitor effectiveness results.",
        "",
        "| Quantity | Count |",
        "|---|---:|",
        *[f"| {k} | {v} |" for k, v in audit["counts"].items()],
        *[f"| {k} | {v} |" for k, v in audit["splits"].items()],
        f"| Test successful attacks, usable | {summary['test_successful_attacks']} |",
        "",
        "Eight records have no usable tool behavior. Four additional attacks lack a usable",
        "benign counterpart. Counts are before physical backend context validation.",
        "",
        "Full source URLs and SHA-256 checksums are in the ignored raw source manifest.",
        "The current normalized-source token counts omit chat-format/instruction overhead;",
        "the complete-prompt context audit is a separate artifact.",
        "",
        "| Class | Length measure | Median | Maximum | Median tool calls |",
        "|---|---|---:|---:|---:|",
    ]
    for cls, values in summary["lengths"].items():
        rows.append(
            f"| {cls} | {values['measure']} | {values['median']:.0f} | "
            f"{values['max']} | {values['median_tool_calls']:.0f} |"
        )
    (output / "dataset-audit.md").write_text("\n".join(rows) + "\n")
    return summary
