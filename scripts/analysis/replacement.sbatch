#!/usr/bin/env bash
#SBATCH --job-name=asm-evidence-replacement
set -euo pipefail
: "${SLURM_JOB_ID:?}" "${ASM_REVIEW_ROOT:?}" "${ASM_REPLACEMENT_OUTPUT:?}"
: "${ASM_FREEZE:?}" "${ASM_DATA:?}" "${ASM_RUN_ROOT:?}" "${ASM_IMAGE:?}" "${HF_HOME:?}"
cd "${SLURM_SUBMIT_DIR:?}"
mkdir -p "$ASM_REPLACEMENT_OUTPUT/jobs/$SLURM_JOB_ID"
job_dir="$ASM_REPLACEMENT_OUTPUT/jobs/$SLURM_JOB_ID"
export ASM_MODEL_REVISION=6cee5e81ee83917806bbde320786a8fb61efebee
export ASM_IMAGE_SHA256=056a8f8f182b1652c88ecf567d11dfa18a5b0a7ddd33d17b3fcc5d5869731c03
export ASM_TP=1 ASM_CONTEXT=131072 ASM_CONCURRENCY=1 ASM_TRACKING_MODE=online
export PYTHONPATH="$PWD/src"
server_pid=
cleanup() { if [[ -n "$server_pid" ]]; then kill -TERM "$server_pid" 2>/dev/null || true; fi; }
trap cleanup EXIT
[[ "$(nvidia-smi --query-gpu=name --format=csv,noheader)" == 'NVIDIA H200' ]]
[[ "${SLURM_GPUS_ON_NODE:?}" == 1 ]]
bash scripts/yale/serve.sh > "$job_dir/server.log" 2>&1 &
server_pid=$!
ready=0
for ((i=0; i<180; i++)); do
  kill -0 "$server_pid" 2>/dev/null || exit 1
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then ready=1; break; fi
  sleep 5
done
[[ "$ready" == 1 ]]
"${ASM_CLIENT_PYTHON:?}" -m agent_safety_monitoring.cli analysis replacement \
  --data "$ASM_DATA" --run-root "$ASM_RUN_ROOT" --freeze "$ASM_FREEZE" \
  --review-root "$ASM_REVIEW_ROOT" --output "$ASM_REPLACEMENT_OUTPUT"
