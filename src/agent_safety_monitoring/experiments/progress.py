"""Incremental local progress, independent of W&B and authoritative result files."""

import csv
import os
import time
from collections import Counter, deque
from pathlib import Path

from agent_safety_monitoring.io import atomic_json, now, read_json
from agent_safety_monitoring.monitors.core import costs


class Progress:
    def __init__(self, root, split, shard, attempt, expected, telemetry, job_id=None):
        self.path = root / f"{split}-shard-{shard}-status.json"
        self.telemetry = telemetry
        self.started = time.monotonic()
        self.recent = deque(maxlen=30)
        self.methods = {
            m: Counter(expected=n, completed=0, valid=0, invalid=0, resumed=0)
            for m, n in expected.items()
        }
        self.physical = Counter()
        self.errors = Counter()
        self.base = {
            "split": split,
            "shard": shard,
            "attempt": attempt,
            "job_id": job_id,
            "started": now(),
            "state": "running",
        }
        self.last_emit = 0
        self.gpu_offset = 0
        self.gpu_devices = {}
        self.gpu_peak_mib = 0

    def event(self, call):
        self.physical["cache_hits" if call.cached else "attempted_calls"] += 1
        if not call.cached:
            for key in [
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "reasoning_tokens_estimated",
            ]:
                self.physical[key] += getattr(call.usage, key) or 0
            self.physical["failed_calls"] += bool(call.error)
        self.physical["transport_retries"] += bool(call.attempt and not call.cached)
        self.emit()

    def result(self, method, result, resumed=False):
        counts = self.methods[method]
        counts["completed"] += 1
        counts["valid" if result.status == "valid" else "invalid"] += 1
        counts["resumed"] += resumed
        for key, value in costs([result]).items():
            if isinstance(value, (int, float)):
                counts[key] += value
        for artifact in result.artifacts:
            if "invalid_attempt" in artifact:
                self.errors[artifact.get("category", "legacy_validation")] += 1
                counts["output_retries"] += artifact["invalid_attempt"] > 0
        if not resumed:
            self.recent.append(time.monotonic())
        self.emit()

    def gpu_metrics(self):
        path = os.environ.get("ASM_GPU_METRICS")
        if not path or not Path(path).exists():
            return {}
        try:
            with Path(path).open() as stream:
                stream.seek(self.gpu_offset)
                lines = stream.readlines(65536)
                self.gpu_offset = stream.tell()
            for row in csv.reader(lines):
                if len(row) < 4 or row[0].strip() == "timestamp":
                    continue
                self.gpu_devices[row[1].strip()] = (
                    float(row[2].split()[0]),
                    float(row[3].split()[0]),
                )
            count = len(self.gpu_devices)
            memory = sum(v[1] for v in self.gpu_devices.values())
            self.gpu_peak_mib = max(self.gpu_peak_mib, memory)
            return {
                "gpu_count": count,
                "gpu_memory_mib": memory,
                "gpu_peak_memory_mib": self.gpu_peak_mib,
                "gpu_utilization_percent": sum(v[0] for v in self.gpu_devices.values())
                / max(1, count),
            }
        except (OSError, ValueError):
            return {}

    def emit(self, force=False, state=None):
        clock = time.monotonic()
        if not force and clock - self.last_emit < 30:
            return
        self.last_emit = clock
        if state:
            self.base["state"] = state
        rows = {}
        for method, counts in self.methods.items():
            row = dict(counts)
            row.update(
                remaining=counts["expected"] - counts["completed"],
                percent=100 * counts["completed"] / max(1, counts["expected"]),
                invalid_rate=counts["invalid"] / max(1, counts["completed"]),
            )
            rows[method] = row
        remaining = sum(r["remaining"] for r in rows.values())
        rate = (
            (len(self.recent) - 1) / (self.recent[-1] - self.recent[0])
            if len(self.recent) > 1 and self.recent[-1] > self.recent[0]
            else None
        )
        gpu = self.gpu_metrics()
        snapshot = {
            **self.base,
            "updated": now(),
            "elapsed_seconds": clock - self.started,
            "methods": rows,
            "physical_attempt": dict(self.physical),
            "gpu": gpu,
            "tracking": {
                "requested_mode": self.telemetry.mode,
                "active": self.telemetry.run is not None,
                "failure_type": self.telemetry.failure_type,
            },
            "error_categories": dict(self.errors),
            "judgments_per_hour_estimate": rate * 3600 if rate else None,
            "remaining_seconds_estimate": remaining / rate if rate else None,
            "estimate_note": "Recent completions; methods and lengths vary.",
        }
        atomic_json(self.path, snapshot)
        metrics = {
            f"{method}/{key}": value for method, row in rows.items() for key, value in row.items()
        }
        metrics.update({f"attempt/{key}": v for key, v in self.physical.items()})
        metrics.update({f"errors/{key}": v for key, v in self.errors.items()})
        metrics.update(gpu)
        metrics.update(elapsed_seconds=snapshot["elapsed_seconds"])
        if rate:
            metrics.update(
                judgments_per_hour_estimate=rate * 3600, remaining_seconds_estimate=remaining / rate
            )
        self.telemetry.log(**metrics)
        return snapshot


def status(root):
    study = read_json(root / "study.json")
    shards = [read_json(p) for p in sorted(root.glob("*-shard-*-status.json"))]
    totals = {}
    for snapshot in shards:
        for method, counts in snapshot["methods"].items():
            key = f"{snapshot['split']}/{method}"
            row = totals.setdefault(key, Counter())
            for name in ["expected", "completed", "valid", "invalid", "remaining"]:
                row[name] += counts.get(name, 0)
    for row in totals.values():
        row["percent"] = 100 * row["completed"] / max(1, row["expected"])
        row["invalid_rate"] = row["invalid"] / max(1, row["completed"])
    return {
        "run_identity": study["identity"],
        "totals": totals,
        "shards": shards,
        "note": "Snapshots are heartbeats, not proof a Slurm job is still running. "
        "Check squeue/sacct; complete state requires full persisted coverage.",
    }
