#!/usr/bin/env bash
#SBATCH --job-name=asm-data-stage
set -euo pipefail
: "${SLURM_JOB_ID:?Must run under Slurm}"
: "${ASM_SCRATCH:?Set project scratch directory}"
cd "${SLURM_SUBMIT_DIR:?}"
export UV_CACHE_DIR="$ASM_SCRATCH/uv-cache"
uv run --locked --extra data asm data download
