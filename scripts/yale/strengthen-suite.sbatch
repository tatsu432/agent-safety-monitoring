#!/usr/bin/env bash
#SBATCH --job-name=asm-review-controller
set -euo pipefail
umask 077
cd "${SLURM_SUBMIT_DIR:?}"
prior=${1:?Pass the completed fine-scale medium-effort pilot job ID}
prior_root="$PWD/../agent-safety-monitoring-strengthen/runs/strengthen"
extra="$PWD/../agent-safety-monitoring-extra-check"
frozen="$PWD/../agent-safety-monitoring-frozen-prep"
export ASM_CLIENT_PYTHON="$extra/.venv/bin/python"
export PYTHONPATH="$PWD/src"
cmp uv.lock "$extra/uv.lock"
state=$(sacct -j "$prior" -X -n --parsable2 --format=State,ExitCode)
[[ "$state" == "COMPLETED|0:0" ]]
"$ASM_CLIENT_PYTHON" - "$prior_root/think-hundred/summary.json" <<'PY'
import json
import sys
from pathlib import Path

saved = json.loads(Path(sys.argv[1]).read_text())
if saved["records"] != 40 or saved["invalid"] > 2:
    raise SystemExit("Physical pilot did not clear the complete-screen validity gate")
PY
[[ -s runs/strengthen/cache-import.json ]]
[[ -s runs/strengthen/evidence-intervention-packet.json ]]
export ASM_SCRATCH=/nfs/roberts/scratch/cpsc4710/cpsc4710_ts2236/agent-safety-monitoring
export HF_HOME="$ASM_SCRATCH/huggingface" UV_CACHE_DIR="$ASM_SCRATCH/uv-cache"
export UV_OFFLINE=1 HF_HUB_OFFLINE=1
export ASM_IMAGE="$PWD/images/vllm-openai-v0.11.0.sif"
export ASM_IMAGE_SHA256=056a8f8f182b1652c88ecf567d11dfa18a5b0a7ddd33d17b3fcc5d5869731c03
export ASM_MODEL_REVISION=6cee5e81ee83917806bbde320786a8fb61efebee
export ASM_GPUS=1 ASM_TP=1 ASM_CONTEXT=131072 ASM_CONCURRENCY=1
export ASM_FREEZE="$frozen/runs/study-freeze.json"
export ASM_DATA="$PWD/data/prepared" ASM_TRACKING_MODE=online
export ASM_ACTION=development-diagnostic ASM_OUTPUT="$PWD/runs/strengthen"
export ASM_DIAGNOSTIC_CONFIG="$PWD/configs/followup/diagnostics.json"
export ASM_DIAGNOSTIC_IDS="$extra/runs/extra-check/screen-ids.json"
export ASM_EVIDENCE_PACKET="$ASM_OUTPUT/evidence-intervention-packet.json"
export ASM_DIAGNOSTIC_CONDITION=eae-hundred,mrt-five-5-512,mrt-five-5-1024,mrt-five-10-512,mrt-hundred
"$ASM_CLIENT_PYTHON" scripts/yale/submit.py \
    --ledger "$extra/runs/submissions.json" \
    --identity strengthen-mechanisms-1 --gpus 1 --minutes 360 --cap-hours 125 \
    --controller-self -- --account=cpsc4710 --partition=gpu_h200 \
    --signal=B:USR1@120 --mem=48G --cpus-per-task=4 \
    --output=logs/mechanisms-%j.out scripts/yale/inference.sbatch
