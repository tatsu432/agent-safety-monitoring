#!/usr/bin/env bash
#SBATCH --job-name=asm-inference
#SBATCH --signal=B:USR1@120
set -euo pipefail
: "${SLURM_JOB_ID:?Must run under Slurm}"
cd "${SLURM_SUBMIT_DIR:?}"
output=${ASM_OUTPUT:-runs}
mkdir -p "$output/jobs"
server_pid=
metrics_pid=
: "${ASM_GPUS:?Set actual allocated GPU count}"
start=$(date +%s)
loaded=$start
cleanup() {
    status=$?
    end=$(date +%s)
    printf '{"job_id":"%s","startup_seconds":%s,"workload_seconds":%s,"gpus":%s,"exit_code":%s}\n' \
      "$SLURM_JOB_ID" "$((loaded-start))" "$((end-loaded))" "$ASM_GPUS" "$status" \
      > "$output/jobs/$SLURM_JOB_ID-timing.json"
    if [[ -n "$metrics_pid" ]]; then kill "$metrics_pid" 2>/dev/null || true; wait "$metrics_pid" || true; fi
    if [[ -n "$server_pid" ]]; then kill "$server_pid" 2>/dev/null || true; wait "$server_pid" || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM USR1
nvidia-smi --query-gpu=uuid,name,memory.used,memory.total --format=csv > "$output/jobs/$SLURM_JOB_ID-gpu.csv"
nvidia-smi --query-gpu=timestamp,uuid,utilization.gpu,memory.used --format=csv -l 5 \
  > "$output/jobs/$SLURM_JOB_ID-utilization.csv" &
metrics_pid=$!
bash scripts/yale/serve.sh > "$output/jobs/$SLURM_JOB_ID-server.log" 2>&1 &
server_pid=$!
ready=0
for (( i=0; i<180; i++ )); do
    kill -0 "$server_pid" 2>/dev/null || { echo 'Server exited during startup' >&2; exit 1; }
    if curl -fsS "http://127.0.0.1:${ASM_PORT:-8000}/health" >/dev/null; then ready=1; break; fi
    sleep 5
done
[[ "$ready" == 1 ]] || { echo 'Server readiness timeout' >&2; exit 1; }
loaded=$(date +%s)
args=(--data "${ASM_DATA:-data/prepared}" --output "$output")
if [[ "${ASM_ACTION:-run}" == benchmark ]]; then
    uv run --locked --extra tokenizer --extra tracking asm experiment benchmark --config "${ASM_CONFIG:?}" \
      --gpus "${ASM_GPUS:?}" --limit "${ASM_LIMIT:-4}" "${args[@]}"
else
    args+=(--split "${ASM_SPLIT:-development}" --shard "${ASM_SHARD:-0}" --shards "${ASM_SHARDS:-1}")
    if [[ -n "${ASM_FREEZE:-}" ]]; then args+=(--frozen "$ASM_FREEZE"); else args+=(--config "${ASM_CONFIG:?}"); fi
    uv run --locked --extra tokenizer --extra tracking asm experiment run "${args[@]}" \
      > "$output/jobs/$SLURM_JOB_ID-client.json"
    cat "$output/jobs/$SLURM_JOB_ID-client.json"
    if [[ "${SLURM_JOB_NAME:-}" == asm-pilot ]]; then
        python - "$output/jobs/$SLURM_JOB_ID-client.json" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    result = json.load(stream)
if result['completed'] != 4 or result['invalid'] != 0:
    raise SystemExit('Pilot failed: four valid judgments are required')
PY
        uv run --locked --extra tokenizer python scripts/yale/long_context.py
    fi
fi
