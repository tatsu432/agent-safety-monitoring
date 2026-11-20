#!/usr/bin/env bash
#SBATCH --job-name=asm-extension-adaptive-cold
set -euo pipefail
umask 077
cd "${SLURM_SUBMIT_DIR:?}"
: "${ASM_CLIENT_PYTHON:?Use verified project Python}"
: "${ASM_OUTPUT:?Use a new private timing directory}"
[[ "${SLURM_GPUS_ON_NODE:?}" == 1 ]]
[[ $(nvidia-smi --query-gpu=name --format=csv,noheader) == 'NVIDIA H200' ]]
version=$(apptainer exec --cleanenv "${ASM_IMAGE:?}" python3 -c 'import vllm; print(vllm.__version__)')
[[ "$version" == 0.11.0 ]]
export HF_HUB_OFFLINE=1 PYTHONPATH="$PWD/src"
job="$ASM_OUTPUT/jobs/$SLURM_JOB_ID"
mkdir -p "$job"
bash scripts/yale/serve.sh > "$job/server.log" 2>&1 &
server=$!
trap 'kill -TERM "$server" 2>/dev/null || true' EXIT
ready=0
for ((i=0; i<180; i++)); do
    kill -0 "$server" 2>/dev/null || { echo 'Serving process exited' >&2; exit 1; }
    if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then ready=1; break; fi
    sleep 5
done
[[ "$ready" == 1 ]]
"$ASM_CLIENT_PYTHON" scripts/analysis/extension_adaptive_timing.py \
    --frozen "${ASM_FREEZE:?}" --data "${ASM_DATA:?}" --policy "${ASM_POLICY:?}" --output "$ASM_OUTPUT"
