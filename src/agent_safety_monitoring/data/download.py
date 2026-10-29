"""Pinned raw source URLs from the upstream data table, never monitored variants."""

import hashlib
from pathlib import Path

import httpx

from agent_safety_monitoring.io import atomic_json, file_hash, now, read_json

SOURCES = {
    "honest": "https://data.linuxarena.ai/api/runs/de437937709f493dafe549b10b4505cf/eval",
    "attack": "https://data.linuxarena.ai/api/runs/792967b92d37439ca0b12a5bce9dfa90/eval",
}


def download(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "sources.json"
    manifest = (
        read_json(manifest_path)
        if manifest_path.exists()
        else {
            "dataset": "BashArena/bashbench2_v1; Claude Opus 4.6",
            "source_page": "https://control-leaderboard.redwoodresearch.org/data",
            "usage": "Evaluation only. No training or uploads of raw transcripts.",
            "files": {},
        }
    )
    for name, url in SOURCES.items():
        path = root / f"{name}.eval"
        if path.exists():
            previous = manifest["files"].get(name)
            if not previous or file_hash(path) != previous["sha256"]:
                raise ValueError(f"Unverified existing file: {path}")
            continue
        temporary = path.with_suffix(".partial")
        h = hashlib.sha256()
        try:
            with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
                response.raise_for_status()
                with temporary.open("wb") as f:
                    for block in response.iter_bytes():
                        f.write(block)
                        h.update(block)
            # Inspect .eval is a ZIP, not a viewer login page.
            with temporary.open("rb") as stream:
                if stream.read(2) != b"PK":
                    raise ValueError("Download is not an Inspect ZIP log")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        manifest["files"][name] = {
            "url": url,
            "sha256": h.hexdigest(),
            "retrieved": now(),
            "path": path.name,
            "bytes": path.stat().st_size,
        }
        atomic_json(manifest_path, manifest)
    return manifest
