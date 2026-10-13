#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$project_root/docker/env/.env.reranker" ]]; then
    set -a
    source "$project_root/docker/env/.env.reranker"
    set +a
fi
: "${VLLM_API_KEY:?Configure docker/env/.env.reranker before starting the server}"
vllm_binary="${VLLM_BIN:-$HOME/vllm-env/bin/vllm}"
model_location="${RERANKER_MODEL_PATH:-BAAI/bge-reranker-v2-m3}"
cache_dir="$project_root/hf_cache/hub/models--BAAI--bge-reranker-v2-m3"
if [[ -z "${RERANKER_MODEL_PATH:-}" && -f "$cache_dir/refs/main" ]]; then
    cached_revision="$(cat "$cache_dir/refs/main")"
    model_location="$cache_dir/snapshots/$cached_revision"
    export HF_HUB_OFFLINE=1
fi
export VLLM_NO_USAGE_STATS=1
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
exec "$vllm_binary" serve "$model_location" \
    --served-model-name BAAI/bge-reranker-v2-m3 \
    --runner pooling --host 0.0.0.0 --port "${RERANKER_PORT:-8002}" \
    --dtype half --max-model-len "${RERANKER_MAX_LENGTH:-512}" \
    --max-num-seqs 16 --gpu-memory-utilization "${RERANKER_GPU_MEMORY_UTILIZATION:-0.45}" \
    --enforce-eager "$@"
