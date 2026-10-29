#!/usr/bin/env bash
#SBATCH --job-name=asm-benchmark
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
export ASM_GPUS=1 ASM_DATA=data/pilot ASM_OUTPUT=runs/pilot ASM_ACTION=benchmark ASM_LIMIT=4
mkdir -p runs
uv run --locked --extra tokenizer asm experiment configure --output runs/development-config.json
python3 - <<'PY'
import json
from pathlib import Path
p=Path('runs/development-config.json')
config=json.loads(p.read_text())
config['model']['engine_version']='0.11.0'
config['logging']={'mode':'offline','project':'agent-safety-monitoring'}
p.write_text(json.dumps(config,indent=2))
PY
export ASM_CONFIG=runs/development-config.json
exec bash scripts/yale/inference.sbatch
