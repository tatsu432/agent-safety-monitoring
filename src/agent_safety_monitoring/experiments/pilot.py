"""Select a small development-only cohort for hardware readiness checks."""

from pathlib import Path

from agent_safety_monitoring.io import atomic_json, read_json


def prepare_pilot(data: Path, output: Path):
    manifest = read_json(data / "manifest.json")
    audit = read_json(data / "audit.json")
    features = {r["trajectory_id"]: r for r in audit["features"]}
    eligible = [
        r for r in manifest["records"] if r["split"] == "development" and not r["exclusion"]
    ]
    if not eligible or not audit["tokenizer_audited"]:
        raise ValueError("Development records and actual tokenizer audit are required")

    def length(r):
        return (features[r["trajectory_id"]]["source_tokens"], r["trajectory_id"])

    benign = sorted((r for r in eligible if r["assignment"] == "benign"), key=length)
    attack = sorted((r for r in eligible if r["outcome"] == "success"), key=length)
    ordered = sorted(eligible, key=length)
    if not benign or not attack:
        raise ValueError("Pilot requires both benign and successful attack development examples")
    candidates = [benign[0], attack[0], ordered[len(ordered) // 2], ordered[-1]]
    selected = {r["trajectory_id"]: r for r in candidates}
    if len(selected) != 4:
        raise ValueError("Pilot representatives overlap; select distinct records")
    (output / "trajectories").mkdir(parents=True, exist_ok=True)
    for uid in selected:
        source = data / "trajectories" / f"{uid}.json"
        target = output / "trajectories" / f"{uid}.json"
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError("Existing pilot trajectory differs")
        if not target.exists():
            target.hardlink_to(source)
    pilot = {
        **manifest,
        "records": list(selected.values()),
        "pilot_only": True,
        "selection": "short benign, short successful attack, median and longest development",
    }
    atomic_json(output / "manifest.json", pilot)
    return {"records": len(selected), "source_tokens": [length(r)[0] for r in candidates]}
