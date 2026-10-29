#!/usr/bin/env bash
#SBATCH --job-name=asm-model-preload
set -euo pipefail
: "${SLURM_JOB_ID:?Must run under Slurm}"
: "${ASM_SCRATCH:?Set project scratch directory}"
cd "${SLURM_SUBMIT_DIR:?}"
export HF_HOME="$ASM_SCRATCH/huggingface"
export UV_CACHE_DIR="$ASM_SCRATCH/uv-cache"
mkdir -p "$HF_HOME" "$UV_CACHE_DIR"
uv run --locked --extra tokenizer python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(repo_id='openai/gpt-oss-20b', revision='6cee5e81ee83917806bbde320786a8fb61efebee',
                  ignore_patterns=['metal/*', 'original/*'])
print('Pinned vLLM model files downloaded')
PY
