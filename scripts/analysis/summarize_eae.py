"""Summarize private record diagnostics without exporting individual results."""

import argparse
from collections import defaultdict
from pathlib import Path
from statistics import mean

from agent_safety_monitoring.io import atomic_json, read_json


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["label"]].append(row)
    return {
        str(label): {
            "n": len(group),
            "without_quotations": sum(row["quotes"] == 0 for row in group),
            "valid_without_quotations": sum(
                row["quotes"] == 0 and row["status"] == "valid" for row in group
            ),
            "mean_quote_count": mean(row["quotes"] for row in group),
            "mean_quoted_tokens": mean(row["quoted_tokens"] for row in group),
        }
        for label, group in groups.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    atomic_json(args.output, summarize(read_json(args.input)["eae"]))


if __name__ == "__main__":
    main()
