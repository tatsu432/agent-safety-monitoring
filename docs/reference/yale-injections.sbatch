#!/usr/bin/env bash
#SBATCH --job-name=asm-injections
#SBATCH --signal=B:USR1@900
set -euo pipefail
: "${SLURM_JOB_ID:?}" "${ASM_FREEZE:?}" "${ASM_PRIMARY_REPORT:?}" "${ASM_IMAGE:?}" "${ASM_IMAGE_SHA256:?}" "${ASM_GPUS:?}"
cd "${SLURM_SUBMIT_DIR:?}"
output=${ASM_OUTPUT:-runs/secondary}
mkdir -p "$output/jobs"
server_pid= client_pid= metrics_pid=
start=$(date +%s)
cleanup() {
    status=$?
    trap - EXIT INT TERM USR1
    for child in "$client_pid" "$metrics_pid" "$server_pid"; do
        [[ -z "$child" ]] || kill -TERM "$child" 2>/dev/null || true
    done
    for child in "$client_pid" "$metrics_pid" "$server_pid"; do
        [[ -z "$child" ]] || wait "$child" 2>/dev/null || true
    done
    printf '{"job_id":"%s","exit_code":%s,"allocation_wall_seconds":%s,"gpus":%s}\n' \
        "$SLURM_JOB_ID" "$status" "$(($(date +%s)-start))" "$ASM_GPUS" > "$output/jobs/$SLURM_JOB_ID-timing.json"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM USR1
uv sync --locked --extra tokenizer --extra tracking
.venv/bin/python - <<'PY'
import os, subprocess
from pathlib import Path
from agent_safety_monitoring.io import read_json
from agent_safety_monitoring.experiments.runner import validate_freeze
f = read_json(Path(os.environ['ASM_FREEZE']))
validate_freeze(f, Path(os.environ.get('ASM_DATA', 'data/prepared')))
c = f['body']['config']; h = c['hardware']; m = c['model']; e = c['environment']
checks = [(os.environ['ASM_IMAGE_SHA256'], e['container_sha256']),
          (os.environ['ASM_MODEL_REVISION'], m['revision']),
          (int(os.environ['ASM_GPUS']), h['gpu_count']),
          (int(os.environ['SLURM_GPUS_ON_NODE']), h['gpu_count']),
          (int(os.environ['ASM_TP']), h['tensor_parallel_size']),
          (int(os.environ['ASM_CONTEXT']), m['context_limit']),
          (int(os.environ['ASM_CONCURRENCY']), m['concurrency'])]
assert all(a == b for a,b in checks), 'Frozen serving settings differ'
names = subprocess.check_output(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], text=True).splitlines()
assert names and all(n.strip() == h['gpu_name'] for n in names), 'Frozen GPU differs'
PY
nvidia-smi --query-gpu=index,uuid,name,memory.used,memory.total --format=csv > "$output/jobs/$SLURM_JOB_ID-gpu.csv"
nvidia-smi --query-gpu=timestamp,uuid,utilization.gpu,memory.used --format=csv -l 5 > "$output/jobs/$SLURM_JOB_ID-utilization.csv" &
metrics_pid=$!
bash scripts/yale/serve.sh > "$output/jobs/$SLURM_JOB_ID-server.log" 2>&1 &
server_pid=$!
ready=0
for ((i=0;i<180;i++)); do
    kill -0 "$server_pid" 2>/dev/null || { echo 'Server exited' >&2; exit 1; }
    if curl -fsS "http://127.0.0.1:${ASM_PORT:-8000}/health" >/dev/null; then ready=1; break; fi
    sleep 5
done
[[ $ready == 1 ]] || { echo 'Server readiness timeout' >&2; exit 1; }
curl -fsS "http://127.0.0.1:${ASM_PORT:-8000}/version" > "$output/jobs/$SLURM_JOB_ID-version.json"
curl -fsS "http://127.0.0.1:${ASM_PORT:-8000}/v1/models" > "$output/jobs/$SLURM_JOB_ID-models.json"
.venv/bin/python - "$output/jobs/$SLURM_JOB_ID-version.json" "$output/jobs/$SLURM_JOB_ID-models.json" <<'PY'
import json, os, sys
config=json.load(open(os.environ['ASM_FREEZE']))['body']['config']['model']
assert json.load(open(sys.argv[1]))['version'] == config['engine_version']
assert config['model'] in {m['id'] for m in json.load(open(sys.argv[2]))['data']}
PY
.venv/bin/asm experiment injections --frozen "$ASM_FREEZE" --data "${ASM_DATA:-data/prepared}" \
    --primary-report "$ASM_PRIMARY_REPORT" --output "$output" > "$output/jobs/$SLURM_JOB_ID-client.json" &
client_pid=$!
wait "$client_pid"
client_pid=
cat "$output/jobs/$SLURM_JOB_ID-client.json"
