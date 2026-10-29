#!/usr/bin/env bash
#SBATCH --job-name=asm-gpu-smoke
set -euo pipefail
: "${SLURM_JOB_ID:?Must run under Slurm}"
cd "${SLURM_SUBMIT_DIR:?}"
mkdir -p "${ASM_OUTPUT:-runs}/hardware"
nvidia-smi --query-gpu=name,uuid,memory.total,driver_version --format=csv
python - <<'PY'
import json, os, time
from pathlib import Path
import torch
start = time.perf_counter()
assert torch.cuda.is_available(), 'CUDA unavailable'
a=torch.randn(256,256,device='cuda')
b=a@a
assert torch.isfinite(b).all().item()
torch.cuda.synchronize()
out={'job_id':os.environ['SLURM_JOB_ID'],'torch':torch.__version__,
     'cuda':torch.version.cuda,'devices':torch.cuda.device_count(),
     'gpu':torch.cuda.get_device_name(0),'seconds':time.perf_counter()-start,
     'model_validated':False}
p=Path(os.environ.get('ASM_OUTPUT','runs'))/'hardware'/f"{out['job_id']}.json"
p.write_text(json.dumps(out,indent=2))
print(json.dumps(out))
PY
