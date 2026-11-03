#!/usr/bin/env bash
#SBATCH --job-name=asm-review-controller
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PYTHONPATH="$PWD/src"
exec "${ASM_CLIENT_PYTHON:?}" scripts/analysis/review-controller.py --phase "$1" --prior-job "$2"
