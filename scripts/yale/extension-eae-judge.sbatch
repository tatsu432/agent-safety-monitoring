#!/usr/bin/env bash
#SBATCH --job-name=asm-extension-eae
set -euo pipefail
umask 077
cd "${SLURM_SUBMIT_DIR:?}"
: "${ASM_CLIENT_PYTHON:?Use verified project Python}"
: "${ASM_FREEZE:?Use original freeze}"
: "${ASM_DATA:?Use original prepared data}"
: "${ASM_OUTPUT:?Use the private versioned run root}"
: "${ASM_REVIEW_OUTPUT:?Use accepted local reviewer outputs}"
: "${ASM_IMAGE:?Use verified project container}"
[[ "${SLURM_GPUS_ON_NODE:?}" == 1 ]]
[[ $(nvidia-smi --query-gpu=name --format=csv,noheader) == 'NVIDIA H200' ]]
version=$(apptainer exec --cleanenv "$ASM_IMAGE" python3 -c 'import vllm; print(vllm.__version__)')
[[ "$version" == 0.11.0 ]]
export HF_HUB_OFFLINE=1
export PYTHONPATH="$PWD/src"
job="$ASM_OUTPUT/jobs/$SLURM_JOB_ID"
mkdir -p "$job"
bash scripts/yale/serve.sh > "$job/server.log" 2>&1 &
server=$!
nvidia-smi --query-gpu=timestamp,uuid,utilization.gpu,memory.used --format=csv -l 5 \
    > "$job/utilization.csv" &
telemetry=$!
trap 'kill -TERM "$server" "$telemetry" 2>/dev/null || true' EXIT
ready=0
for ((i=0; i<180; i++)); do
    kill -0 "$server" 2>/dev/null || { echo 'Serving process exited' >&2; exit 1; }
    if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then ready=1; break; fi
    sleep 5
done
[[ "$ready" == 1 ]]
"$ASM_CLIENT_PYTHON" -m agent_safety_monitoring.cli analysis extension-eae-judge \
    --frozen "$ASM_FREEZE" --data "$ASM_DATA" --output "$ASM_OUTPUT" --review "$ASM_REVIEW_OUTPUT"
