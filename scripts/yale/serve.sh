#!/usr/bin/env bash
set -euo pipefail
: "${SLURM_JOB_ID:?Must run under Slurm}"
: "${ASM_MODEL_REVISION:?Set verified model commit}"
: "${CUDA_VISIBLE_DEVICES:?Slurm must identify allocated GPU devices}"
args=(--model openai/gpt-oss-20b --revision "$ASM_MODEL_REVISION"
      --tokenizer-revision "$ASM_MODEL_REVISION"
      --disable-log-requests --no-enable-prefix-caching --host 127.0.0.1 --port "${ASM_PORT:-8000}"
      --tensor-parallel-size "${ASM_TP:-1}"
      --max-model-len "${ASM_CONTEXT:-131072}"
      --max-num-seqs "${ASM_CONCURRENCY:-1}")
if [[ -n "${ASM_IMAGE:-}" ]]; then
    : "${ASM_IMAGE_SHA256:?Set verified SIF checksum}"
    actual=$(sha256sum "$ASM_IMAGE")
    [[ "${actual%% *}" == "$ASM_IMAGE_SHA256" ]] || { echo 'Image checksum mismatch' >&2; exit 1; }
    exec apptainer exec --nv --cleanenv --bind "${HF_HOME:?}:$HF_HOME" \
      --env "HF_HOME=$HF_HOME" --env "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES" \
      "$ASM_IMAGE" python3 -m vllm.entrypoints.openai.api_server "${args[@]}"
else
    # First pilot may use a separately verified site environment.
    exec python3 -m vllm.entrypoints.openai.api_server "${args[@]}"
fi
