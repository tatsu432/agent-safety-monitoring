"""Probe long-context inference using synthetic text, not held-out trajectories."""

import asyncio
import json
import os
from pathlib import Path

from agent_safety_monitoring.inference.backend import Backend, ModelConfig
from agent_safety_monitoring.io import atomic_json, read_json
from agent_safety_monitoring.monitors.core import MethodConfig, Monitor
from agent_safety_monitoring.schema import CanonicalTrajectory, Segment


async def main():
    config = ModelConfig.model_validate(read_json(Path(os.environ["ASM_CONFIG"]))["model"])
    backend = Backend(config, Path("runs/cache/long-context"))
    # Calibrate repeat count using the exact tokenizer. The source is entirely synthetic.
    unit = "status ok. "
    sample_tokens = backend.tokens.count(unit * 1000)
    text = unit * (115000 * 1000 // sample_tokens)
    count = backend.tokens.count(text)
    trajectory = CanonicalTrajectory(
        id="synthetic-long-context",
        task="Review the synthetic status log.",
        segments=[
            Segment(
                id="s0",
                role="tool",
                kind="tool_result",
                text=text,
                source_message=0,
                source_end=len(text),
                interaction=0,
            )
        ],
    )
    try:
        result = await Monitor(backend).run(trajectory, MethodConfig(method="single"))
    finally:
        await backend.close()
    output = Path("runs/jobs") / f"{os.environ['SLURM_JOB_ID']}-long-context.json"
    atomic_json(output, {"synthetic": True, "source_tokens": count, "result": result.model_dump()})
    print(
        json.dumps(
            {
                "synthetic": True,
                "source_tokens": count,
                "status": result.status,
                "output": str(output),
            }
        )
    )
    if result.status != "valid":
        raise SystemExit("Synthetic long-context monitor did not return a valid judgment")


if __name__ == "__main__":
    asyncio.run(main())
