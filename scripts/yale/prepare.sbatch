#!/usr/bin/env bash
#SBATCH --job-name=asm-prepare
set -euo pipefail
: "${SLURM_JOB_ID:?Must run under Slurm}"
: "${ASM_SCRATCH:?Set project-specific scratch directory}"
cd "${SLURM_SUBMIT_DIR:?}"
mkdir -p "$ASM_SCRATCH"/{apptainer-cache,apptainer-tmp,huggingface,uv-cache,tmp} images data
export APPTAINER_CACHEDIR="$ASM_SCRATCH/apptainer-cache"
export APPTAINER_TMPDIR="$ASM_SCRATCH/apptainer-tmp"
export APPTAINER_MKSQUASHFS_ARGS="${ASM_MKSQUASHFS_ARGS:--processors 4 -mem 8G}"
export HF_HOME="$ASM_SCRATCH/huggingface"
export UV_CACHE_DIR="$ASM_SCRATCH/uv-cache"
export TMPDIR="$ASM_SCRATCH/tmp"
image=images/vllm-openai-v0.11.0.sif
if [[ ! -f "$image" ]]; then
    apptainer pull "$image.partial" docker://docker.io/vllm/vllm-openai@sha256:014a95f21c9edf6abe0aea6b07353f96baa4ec291c427bb1176dc7c93a85845c
    mv "$image.partial" "$image"
fi
sha256sum "$image" > "$image.sha256"
uv run --locked --extra data --extra tokenizer python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(repo_id='openai/gpt-oss-20b', revision='6cee5e81ee83917806bbde320786a8fb61efebee',
                  ignore_patterns=['metal/*', 'original/*'])
print('Pinned model snapshot downloaded')
PY
uv run --locked --extra data --extra tokenizer asm data download
uv run --locked --extra data --extra tokenizer asm data import data/raw/honest.eval data/raw/attack.eval
uv run --locked --extra data --extra tokenizer asm data audit --model-config configs/model/gpt-oss-20b.json
uv run --locked --extra data --extra tokenizer asm data context --model-config configs/model/gpt-oss-20b.json
