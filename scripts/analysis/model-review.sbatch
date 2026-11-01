#!/usr/bin/env bash
#SBATCH --job-name=asm-model-review
set -euo pipefail
: "${SLURM_JOB_ID:?Run within a project Slurm allocation}"
: "${ASM_REVIEW_PACKET:?Set prepared private packet}"
: "${ASM_REVIEW_OUTPUT:?Set private output directory}"
: "${ASM_REVIEW_CONFIG:?Set pinned reviewer configuration}"
: "${ASM_IMAGE:?Set verified container path}"
: "${HF_HOME:?Set this project model cache}"
: "${CUDA_VISIBLE_DEVICES:?Slurm must select allocated GPU}"
cd "${SLURM_SUBMIT_DIR:?}"
client=${ASM_CLIENT_PYTHON:-.venv/bin/python}
mkdir -p "$ASM_REVIEW_OUTPUT/jobs"
job_dir="$ASM_REVIEW_OUTPUT/jobs/$SLURM_JOB_ID"
mkdir -p "$job_dir"
server_pid=
metrics_pid=
cleanup() {
    if [[ -n "$metrics_pid" ]]; then kill -TERM "$metrics_pid" 2>/dev/null || true; fi
    if [[ -n "$server_pid" ]]; then kill -TERM "$server_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
# Validate physical runtime before serving. No transcript is read by this shell.
"$client" - "$ASM_REVIEW_CONFIG" "$ASM_IMAGE" "$job_dir/runtime.json" <<'PY'
import json, os, subprocess, sys
from pathlib import Path
from agent_safety_monitoring.analysis.model_review import check_model_config
from agent_safety_monitoring.io import digest, file_hash
config = json.loads(Path(sys.argv[1]).read_text())
model = check_model_config(config)
if file_hash(Path(sys.argv[2])) != config['environment']['container_sha256']:
    raise SystemExit('Container checksum mismatch')
names = subprocess.check_output(['nvidia-smi','--query-gpu=name',
                                 '--format=csv,noheader'], text=True).splitlines()
if (names != [config['hardware']['gpu_name']]
        or int(os.environ['SLURM_GPUS_ON_NODE']) != config['hardware']['gpu_count']):
    raise SystemExit('GPU allocation mismatch')
version = subprocess.check_output(['apptainer','exec','--cleanenv',sys.argv[2],
                                  'python3','-c','import vllm; print(vllm.__version__)'],
                                 text=True).strip()
if version != model.engine_version:
    raise SystemExit('Engine mismatch')
Path(sys.argv[3]).write_text(json.dumps({'job_id': os.environ['SLURM_JOB_ID'],
    'config_hash': digest(config), 'hardware_verified': True, 'container_verified': True,
    'engine_verified': True, 'engine_version': version, 'gpu_names': names}))
PY
revision=$("$client" -c 'import json,sys; print(json.load(open(sys.argv[1]))["model"]["revision"])' "$ASM_REVIEW_CONFIG")
nvidia-smi --query-gpu=timestamp,uuid,utilization.gpu,memory.used --format=csv -l 5 \
    > "$job_dir/utilization.csv" &
metrics_pid=$!
# Configuration fixes one H200, TP=1, concurrency=1, 131072 context and local port 8000.
apptainer exec --nv --cleanenv --bind "$HF_HOME:$HF_HOME" \
    --env "HF_HOME=$HF_HOME" --env "HF_HUB_OFFLINE=1" \
    --env "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES" \
    "$ASM_IMAGE" python3 -m vllm.entrypoints.openai.api_server \
    --model openai/gpt-oss-120b --revision "$revision" --tokenizer-revision "$revision" \
    --host 127.0.0.1 --port 8000 --disable-log-requests --no-enable-prefix-caching \
    --tensor-parallel-size 1 --max-model-len 131072 --max-num-seqs 1 \
    > "$job_dir/server.log" 2>&1 &
server_pid=$!
ready=0
for ((i=0; i<180; i++)); do
    kill -0 "$server_pid" 2>/dev/null || { echo 'Reviewer server exited' >&2; exit 1; }
    if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then ready=1; break; fi
    sleep 5
done
[[ "$ready" == 1 ]] || { echo 'Reviewer server timeout' >&2; exit 1; }
args=(analysis review-run --packet "$ASM_REVIEW_PACKET" --config "$ASM_REVIEW_CONFIG"
      --output "$ASM_REVIEW_OUTPUT")
if [[ -n "${ASM_REVIEW_PROOF:-}" ]]; then args+=(--proof "$ASM_REVIEW_PROOF"); fi
export ASM_TRACKING_MODE=online
"$client" -m agent_safety_monitoring.cli "${args[@]}"
