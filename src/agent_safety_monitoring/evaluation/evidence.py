"""Reference evidence analysis: never infer reference truth from monitor selections."""

from agent_safety_monitoring.monitors.core import validate_quotes
from agent_safety_monitoring.schema import Extraction


def retention(trajectory, result, references: list[dict], tokenizer):
    """References require step/start/end/text/provenance fields from independent annotation."""
    verified = Extraction.model_validate(
        {"quotes": [{k: r[k] for k in ["step", "start", "end", "text"]} for r in references]}
    )
    validate_quotes(verified, trajectory, tokenizer, 10**12)
    selected = [
        q
        for a in result.artifacts
        if a.get("stage") == "extract" and "output" in a
        for q in a["output"]["quotes"]
    ]
    outcomes = []
    for ref in references:
        outcomes.append(
            {
                "step": ref["step"],
                "provenance": ref["provenance"],
                "retained_exactly": any(
                    q["step"] == ref["step"]
                    and q["start"] <= ref["start"]
                    and q["end"] >= ref["end"]
                    for q in selected
                ),
                "final_citation": ref["step"] in result.citations,
            }
        )
    return {
        "references": outcomes,
        "note": "Citation omission is not proof of misunderstanding. "
        "Summary semantic retention requires independent annotation.",
    }
