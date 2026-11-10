#!/usr/bin/env bash
#SBATCH --job-name=asm-review-controller
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PYTHONPATH="$PWD/src"
exec .venv/bin/python scripts/analysis/followup-controller.py "$1" "$2"
