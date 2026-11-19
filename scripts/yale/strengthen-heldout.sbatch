#!/usr/bin/env bash
#SBATCH --job-name=asm-review-controller
set -euo pipefail
umask 077
cd "${SLURM_SUBMIT_DIR:?}"
prior=${1:?Pass the mechanism workload job ID}
extra="$PWD/../agent-safety-monitoring-extra-check"
frozen="$PWD/../agent-safety-monitoring-frozen-prep"
export ASM_CLIENT_PYTHON="$extra/.venv/bin/python"
export PYTHONPATH="$PWD/src"
cmp uv.lock "$extra/uv.lock"
state=$(sacct -j "$prior" -X -n --parsable2 --format=State,ExitCode)
[[ "$state" == "COMPLETED|0:0" ]]
export ASM_DIAGNOSTIC_FREEZE="$PWD/runs/strengthen/think-heldout-freeze.json"
minutes=$("$ASM_CLIENT_PYTHON" - "$extra/runs/submissions.json" <<'PY'
import getpass
import math
import subprocess
import sys
from pathlib import Path

from agent_safety_monitoring.experiments.resources import allocation_usage, reconciled_accounting
from agent_safety_monitoring.io import atomic_json, digest, read_json

root = Path("runs/strengthen")
plan = read_json(root / "think-heldout-freeze.json")
if digest(plan["body"]) != plan["hash"]:
    raise SystemExit("Invalid held-out plan identity")
known = read_json(Path(sys.argv[1]))["submissions"]
records = reconciled_accounting(
    lambda args: subprocess.check_output(args, text=True), known,
    user=getpass.getuser(), since="2026-10-28", account="cpsc4710",
)
allocated = allocation_usage(records)["allocated_gpu_seconds"]
projected = plan["body"]["projected_remaining_seconds_with_contingency"]
reservation = 5 * math.ceil((projected + 120) / 300)
viable = allocated + reservation * 60 <= 125 * 3600
atomic_json(root / "heldout-budget-decision.json", {
    "freeze": plan["hash"],
    "consumed_gpu_seconds": allocated,
    "reserved_minutes": reservation,
    "cap_gpu_hours": 125,
    "state": "eligible_for_submission" if viable else "insufficient_headroom_under_measured_cap",
})
print(reservation if viable else 0)
PY
)
if [[ "$minutes" == 0 ]]; then exit 0; fi
export ASM_SCRATCH=/nfs/roberts/scratch/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring
export HF_HOME="$ASM_SCRATCH/huggingface" UV_CACHE_DIR="$ASM_SCRATCH/uv-cache"
export UV_OFFLINE=1 HF_HUB_OFFLINE=1
export ASM_IMAGE="$PWD/images/vllm-openai-v0.11.0.sif"
export ASM_IMAGE_SHA256=056a8f8f182b1652c88ecf567d11dfa18a5b0a7ddd33d17b3fcc5d5869731c03
export ASM_MODEL_REVISION=6cee5e81ee83917806bbde320786a8fb61efebee
export ASM_GPUS=1 ASM_TP=1 ASM_CONTEXT=131072 ASM_CONCURRENCY=1
export ASM_FREEZE="$frozen/runs/study-freeze.json"
export ASM_DATA="$PWD/data/prepared" ASM_TRACKING_MODE=online
export ASM_ACTION=development-diagnostic ASM_OUTPUT="$PWD/runs/strengthen/heldout"
export ASM_DIAGNOSTIC_CONFIG="$PWD/configs/followup/diagnostics.json"
export ASM_DIAGNOSTIC_IDS="$extra/runs/extra-check/screen-ids.json"
export ASM_DIAGNOSTIC_CONDITION=think-hundred
"$ASM_CLIENT_PYTHON" scripts/yale/submit.py \
    --ledger "$extra/runs/submissions.json" --identity strengthen-think-heldout-1 \
    --gpus 1 --minutes "$minutes" --cap-hours 125 --controller-self -- \
    --account=cpsc4710 --partition=gpu_h200 --signal=B:USR1@120 --mem=48G --cpus-per-task=4 \
    --output=logs/think-heldout-%j.out scripts/yale/inference.sbatch
