#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$project_root/docker/env/.env.generator" ]]; then
    set -a
    source "$project_root/docker/env/.env.generator"
    set +a
fi
: "${VLLM_API_KEY:?Run scripts/configure_qwen.py before starting the server}"
vllm_binary="${VLLM_BIN:-$HOME/vllm-env/bin/vllm}"
export PATH="$(dirname -- "$vllm_binary"):$PATH"
model_location="${GENERATOR_MODEL_PATH:-$HOME/vllm-env/models/Qwen3-4B-Instruct-2507}"
if [[ ! -f "$model_location/rag-ishms-model.json" ]]; then
    echo "The verified local Qwen checkpoint is unavailable: $model_location" >&2
    exit 1
fi

# Let the smaller reranker finish loading before profiling generation memory.
if [[ "${GENERATOR_WAIT_FOR_RERANKER:-true}" == "true" ]]; then
    echo "Waiting for the local GPU reranker to become healthy..."
    deadline=$((SECONDS + 240))
    until curl --fail --silent --max-time 2 \
        "http://127.0.0.1:${RERANKER_PORT:-8002}/health" > /dev/null; do
        if (( SECONDS >= deadline )); then
            echo "Reranker startup timed out; check rag-ishms-reranker.service." >&2
            exit 1
        fi
        sleep 2
    done
fi

export HF_HUB_OFFLINE=1
export VLLM_NO_USAGE_STATS=1
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
exec "$vllm_binary" serve "$model_location" \
    --served-model-name "${GENERATOR_SERVED_MODEL_NAME:-qwen3-legal-final}" \
    --host 0.0.0.0 --port "${GENERATOR_PORT:-8001}" \
    --quantization bitsandbytes --dtype half \
    --max-model-len "${GENERATOR_MAX_MODEL_LEN:-2048}" \
    --max-num-seqs 1 --max-num-batched-tokens 512 \
    --gpu-memory-utilization "${GENERATOR_GPU_MEMORY_UTILIZATION:-0.70}" \
    --generation-config vllm --enforce-eager "$@"
