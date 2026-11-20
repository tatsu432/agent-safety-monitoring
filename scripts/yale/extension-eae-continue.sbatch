#!/usr/bin/env bash
#SBATCH --job-name=asm-extension-eae-continue
set -euo pipefail
umask 077
cd "${SLURM_SUBMIT_DIR:?}"
review_job=${1:?Pass the successfully completed blinded review job ID}
base="${PWD%/*}"
extra="$base/agent-safety-monitoring-extra-check"
frozen="$base/agent-safety-monitoring-frozen-prep"
analysis="$base/agent-safety-monitoring-analysis"
export ASM_CLIENT_PYTHON="$extra/.venv/bin/python" PYTHONPATH="$PWD/src"
export HF_HOME="/nfs/roberts/scratch/cpsc4710/$USER/agent-safety-monitoring/huggingface"
export HF_HUB_OFFLINE=1
export ASM_IMAGE="$frozen/images/vllm-openai-v0.11.0.sif"
export ASM_IMAGE_SHA256=056a8f8f182b1652c88ecf567d11dfa18a5b0a7ddd33d17b3fcc5d5869731c03
export ASM_MODEL_REVISION=6cee5e81ee83917806bbde320786a8fb61efebee
export ASM_FREEZE="$frozen/runs/study-freeze.json"
export ASM_DATA="$base/agent-safety-monitoring-strengthen/data/prepared"
export ASM_OUTPUT="$PWD/runs/eae"
export ASM_REVIEW_OUTPUT="$ASM_OUTPUT/model-review"
cmp uv.lock "$extra/uv.lock"
[[ $(sacct -X -j "$review_job" --parsable2 --noheader --format=State,ExitCode) == 'COMPLETED|0:0' ]]
"$ASM_CLIENT_PYTHON" - "$ASM_OUTPUT" "$review_job" <<'PY'
import sys
from pathlib import Path
from agent_safety_monitoring.analysis.model_review import SYSTEM
from agent_safety_monitoring.io import digest, file_hash, read_json

root = Path(sys.argv[1])
review = root / "model-review"
packet = root / "review-test.json"
identity = read_json(review / "identity.json")
receipt = read_json(review / "jobs" / sys.argv[2] / "runtime.json")
wanted = {row["trajectory_id"] for row in read_json(packet)["records"]}
files = {p.stem: p for p in (review / "annotations").glob("*.json")}
if (identity["packet_hash"] != file_hash(packet)
    or identity["system_hash"] != digest(SYSTEM)
    or receipt["config_hash"] != identity["config_hash"]
    or not receipt["hardware_verified"]
    or not receipt["container_verified"]
    or set(files) != wanted
    or any(read_json(path)["identity"] != identity for path in files.values())):
    raise SystemExit("Blinded evidence review did not clear the archive coverage gate")
PY
test -s "$analysis/runs/model-review/repair-2-development-accepted.json"
"$ASM_CLIENT_PYTHON" scripts/yale/submit.py --ledger runs/submissions.json \
    --prior-ledger "$extra/runs/submissions.json" \
    --prior-ledger "$frozen/runs/submissions.json" \
    --prior-ledger "$base/agent-safety-monitoring-readiness/runs/readiness/submissions.json" \
    --identity extension-v1-eae-fixed-judge-1 --gpus 1 --minutes 45 --cap-hours 130 \
    --controller-self -- --account=cpsc4710 --partition=gpu_h200 --mem=48G --cpus-per-task=4 \
    --output=logs/extension-eae-%j.out scripts/yale/extension-eae-judge.sbatch
