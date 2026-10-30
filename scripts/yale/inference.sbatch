#!/usr/bin/env bash
#SBATCH --job-name=asm-inference
#SBATCH --signal=B:USR1@900
set -euo pipefail
: "${SLURM_JOB_ID:?Must run under Slurm}"
cd "${SLURM_SUBMIT_DIR:?}"
output=${ASM_OUTPUT:-runs}
mkdir -p "$output/jobs"
server_pid=
metrics_pid=
client_pid=
interrupted=0
: "${ASM_GPUS:?Set actual allocated GPU count}"
export ASM_TP="${ASM_TP:-1}" ASM_CONTEXT="${ASM_CONTEXT:-131072}"
export ASM_CONCURRENCY="${ASM_CONCURRENCY:-1}"
start=$(date +%s)
loaded=
stop_child() {
    local child=$1
    [[ -n "$child" ]] || return 0
    kill -TERM "$child" 2>/dev/null || true
    for (( n=0; n<40; n++ )); do
        kill -0 "$child" 2>/dev/null || break
        sleep 0.25
    done
    kill -KILL "$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
}
cleanup() {
    status=$?
    stop_child "$client_pid"
    stop_child "$metrics_pid"
    stop_child "$server_pid"
    end=$(date +%s)
    if [[ -z "$loaded" ]]; then loaded=$end; fi
    printf '{"job_id":"%s","startup_seconds":%s,"workload_seconds":%s,"gpus":%s,"exit_code":%s,"interrupted":%s,"allocation_wall_seconds":%s}\n' \
      "$SLURM_JOB_ID" "$((loaded-start))" "$((end-loaded))" "$ASM_GPUS" "$status" "$interrupted" "$((end-start))" \
      > "$output/jobs/$SLURM_JOB_ID-timing.json"
}
trap cleanup EXIT
forward_signal() {
    interrupted=1
    if [[ -n "$client_pid" ]]; then
        kill -USR1 "$client_pid" 2>/dev/null || true
    else
        exit 130
    fi
}
wait_client() {
    local status
    while true; do
        if wait "$client_pid"; then status=0; else status=$?; fi
        kill -0 "$client_pid" 2>/dev/null || break
        # A trapped signal interrupted wait; the Python child is still draining.
    done
    client_pid=
    return "$status"
}
trap forward_signal INT TERM USR1
# Resolve the locked client before loading the server. Invoke its entrypoint directly
# so the PID receiving USR1 is the Python runner rather than a package-manager parent.
sync_args=(--locked --extra tokenizer)
if [[ "${ASM_TRACKING_MODE:-online}" != disabled ]]; then sync_args+=(--extra tracking); fi
uv sync "${sync_args[@]}"
client="$PWD/.venv/bin/asm"
python3 - "$output/jobs/$SLURM_JOB_ID-allocation.json" <<'PY'
import json, os, sys
freeze = os.environ.get('ASM_FREEZE')
if freeze:
    with open(freeze) as frozen_stream:
        config = json.load(frozen_stream)['body']['config']
    model, hardware, environment = config['model'], config['hardware'], config['environment']
    checks = (
        (os.environ.get('ASM_IMAGE_SHA256'), environment['container_sha256']),
        (os.environ.get('ASM_MODEL_REVISION'), model['revision']),
        (int(os.environ['ASM_GPUS']), hardware['gpu_count']),
        (int(os.environ['ASM_TP']), hardware['tensor_parallel_size']),
        (int(os.environ['ASM_CONTEXT']), model['context_limit']),
        (int(os.environ['ASM_CONCURRENCY']), model['concurrency']),
    )
    if any(actual != expected for actual, expected in checks):
        raise SystemExit('Serving settings differ from scientific freeze')
    import subprocess
    names = subprocess.check_output(
        ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], text=True).splitlines()
    if not names or any(name.strip() != hardware['gpu_name'] for name in names):
        raise SystemExit('GPU model differs from scientific freeze')
if int(os.environ['ASM_GPUS']) != int(os.environ['SLURM_GPUS_ON_NODE']):
    raise SystemExit('ASM_GPUS differs from the actual Slurm allocation')
with open(sys.argv[1], 'w') as stream:
    json.dump({key: os.environ.get(key) for key in (
        'SLURM_JOB_ID', 'SLURM_JOB_GPUS', 'SLURM_GPUS_ON_NODE', 'ASM_GPUS',
        'CUDA_VISIBLE_DEVICES', 'SLURM_JOB_NODELIST', 'ASM_TP', 'ASM_CONTEXT',
        'ASM_CONCURRENCY', 'ASM_MODEL_REVISION', 'ASM_IMAGE_SHA256')}, stream, indent=2)
PY
nvidia-smi --query-gpu=index,uuid,name,memory.used,memory.total --format=csv > "$output/jobs/$SLURM_JOB_ID-gpu.csv"
nvidia-smi --query-gpu=timestamp,uuid,utilization.gpu,memory.used --format=csv -l 5 \
  > "$output/jobs/$SLURM_JOB_ID-utilization.csv" &
metrics_pid=$!
export ASM_GPU_METRICS="$PWD/$output/jobs/$SLURM_JOB_ID-utilization.csv"
if [[ "$output" == /* ]]; then export ASM_GPU_METRICS="$output/jobs/$SLURM_JOB_ID-utilization.csv"; fi
bash scripts/yale/serve.sh > "$output/jobs/$SLURM_JOB_ID-server.log" 2>&1 &
server_pid=$!
ready=0
for (( i=0; i<180; i++ )); do
    kill -0 "$server_pid" 2>/dev/null || { echo 'Server exited during startup' >&2; exit 1; }
    if curl -fsS "http://127.0.0.1:${ASM_PORT:-8000}/health" >/dev/null; then ready=1; break; fi
    sleep 5
done
[[ "$ready" == 1 ]] || { echo 'Server readiness timeout' >&2; exit 1; }
curl -fsS "http://127.0.0.1:${ASM_PORT:-8000}/version" > "$output/jobs/$SLURM_JOB_ID-version.json"
curl -fsS "http://127.0.0.1:${ASM_PORT:-8000}/v1/models" > "$output/jobs/$SLURM_JOB_ID-models.json"
python3 - "$output/jobs/$SLURM_JOB_ID-version.json" "$output/jobs/$SLURM_JOB_ID-models.json" "${ASM_CONFIG:-${ASM_FREEZE:-}}" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    version = json.load(stream)['version']
with open(sys.argv[2]) as stream:
    models = json.load(stream)['data']
with open(sys.argv[3]) as stream:
    config = json.load(stream)
config = config.get('body', {}).get('config', config)
expected = config['model']
if version != expected['engine_version'] or expected['model'] not in {m['id'] for m in models}:
    raise SystemExit('Serving engine/model differs from the requested configuration')
PY
loaded=$(date +%s)
args=(--data "${ASM_DATA:-data/prepared}" --output "$output")
if [[ "${ASM_ACTION:-run}" == benchmark ]]; then
    "$client" experiment benchmark --config "${ASM_CONFIG:?}" \
      --gpus "${ASM_GPUS:?}" --limit "${ASM_LIMIT:-4}" \
      --trial-id "${ASM_TRIAL_ID:-default}" "${args[@]}" &
    client_pid=$!
else
    args+=(--split "${ASM_SPLIT:-development}" --shard "${ASM_SHARD:-0}" --shards "${ASM_SHARDS:-1}")
    if [[ -n "${ASM_FREEZE:-}" ]]; then args+=(--frozen "$ASM_FREEZE"); else args+=(--config "${ASM_CONFIG:?}"); fi
    "$client" experiment run "${args[@]}" \
      > "$output/jobs/$SLURM_JOB_ID-client.json" &
    client_pid=$!
    wait_client
    cat "$output/jobs/$SLURM_JOB_ID-client.json"
    if [[ "${SLURM_JOB_NAME:-}" == asm-pilot ]]; then
        python3 - "$output/jobs/$SLURM_JOB_ID-client.json" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    result = json.load(stream)
if result['completed'] != 4 or result['invalid'] != 0:
    raise SystemExit('Pilot failed: four valid judgments are required')
PY
        uv run --locked --extra tokenizer python scripts/yale/long_context.py
    fi
fi

if [[ -n "$client_pid" ]]; then
    wait_client
fi
[[ "$interrupted" == 0 ]] || exit 130
