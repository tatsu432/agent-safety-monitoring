#!/usr/bin/env bash
#SBATCH --job-name=asm-pilot
#SBATCH --signal=B:USR1@120
set -euo pipefail
: "${SLURM_JOB_ID:?Must run under Slurm}"
: "${ASM_SCRATCH:?Set project scratch directory}"
cd "${SLURM_SUBMIT_DIR:?}"
export HF_HOME="$ASM_SCRATCH/huggingface"
export UV_CACHE_DIR="$ASM_SCRATCH/uv-cache"
export ASM_IMAGE="$PWD/images/vllm-openai-v0.11.0.sif"
export ASM_IMAGE_SHA256
ASM_IMAGE_SHA256=$(awk '{print $1}' "$ASM_IMAGE.sha256")
export ASM_MODEL_REVISION=6cee5e81ee83917806bbde320786a8fb61efebee
export ASM_GPUS=1 ASM_DATA=data/pilot ASM_OUTPUT=runs ASM_SPLIT=development
mkdir -p runs
uv run --locked --extra tokenizer asm experiment pilot-prep
uv run --locked --extra tokenizer python - <<'PY'
import json
from pathlib import Path
model=json.loads(Path('configs/model/gpt-oss-20b.json').read_text())
model['engine_version']='0.11.0'
config={'model':model,'methods':[{'method':'single'}],
        'execution':{'trajectory_concurrency':1},'logging':{'mode':'disabled'}}
Path('runs/pilot-config.json').write_text(json.dumps(config,indent=2))
PY
export ASM_CONFIG=runs/pilot-config.json
exec bash scripts/yale/inference.sbatch
