# Model serving

## Local Qwen generator — verified 2026-10-15

The final experiment selected the **untuned base**,
`Qwen/Qwen3-4B-Instruct-2507`, revision
`cdbee75f17c01a7cc42f958dc650907174af0554`. No SFT or M/A adapter is loaded.
The release ZIP contains evaluation results and a loader; the original public
weights are downloaded separately and checked against the pinned repository's
file sizes, LFS SHA-256 hashes and Git blob hashes for the smaller files.

The existing `/home/yacine_105/vllm-env` has vLLM 0.30.0, with
`vllm-bnb-plugin==0.0.3` and `bitsandbytes==0.50.2` added for in-flight 4-bit loading.
These packages are confined to that environment. The API image and its Python
dependencies do not change. The weights live on G: to avoid filling the Linux
disk, exposed through a symlink inside the vLLM environment.

To download or resume the exact weights on this machine:

```bash
cd /home/yacine_105/rag-ishms
HF_HUB_DISABLE_XET=1 ~/vllm-env/bin/python scripts/download_qwen.py \
  --model-dir /mnt/g/rag-ishms-models/Qwen3-4B-Instruct-2507
```

Direct HTTP is selected because the Xet transfer stalled during setup. Completed
files are reused; interrupted partial transfers may need downloading again.
The local link is `~/vllm-env/models/Qwen3-4B-Instruct-2507`. If setting up another
machine, create its parent directory and a symlink to the downloaded directory,
or give `configure_qwen.py --model-path` the actual directory. The configuration
helper requires the completed download's verification manifest.

```bash
uv pip install --python ~/vllm-env/bin/python --no-cache --no-deps \
  vllm-bnb-plugin==0.0.3 bitsandbytes==0.50.2
.venv/bin/python scripts/configure_qwen.py

mkdir -p ~/.config/systemd/user
cp deploy/systemd/rag-ishms-generator.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable rag-ishms-reranker.service rag-ishms-generator.service
```

The helper preserves embedding, database, reranker and client credentials. It
backs up the previous API environment once as
`docker/env/.env.fastapi.before-qwen`, creates a separate service key in
`docker/env/.env.generator`, and updates only these API settings:

```dotenv
GENERATION_PROVIDER=OPENAI
GENERATION_BASE_URL=http://host.docker.internal:8001/v1
GENERATION_API_KEY=<private generator key>
GENERATION_MODEL_ID=qwen3-legal-final
GENERATION_MODEL_TEMPERATURE=0
MAX_OUTPUT_TOKENS=256
```

Both private environment files and the rollback copy are ignored by Git. This
service key is different from the client `RAG_API_KEY` sent by Postman.

On subsequent starts, open WSL, check GPU access, and start services:

```bash
cd /home/yacine_105/rag-ishms
nvidia-smi
systemctl --user start rag-ishms-reranker.service rag-ishms-generator.service
docker compose -f docker/docker-compose.yml up -d --no-deps fastapi nginx

journalctl --user -u rag-ishms-generator.service -n 60 --no-pager
curl --fail-with-body http://localhost:8001/health
curl --fail-with-body http://localhost/health
```

The generator waits for the reranker's `/health` before profiling GPU memory.
It uses FP16 activations, bitsandbytes 4-bit loading, eager execution, one active
sequence, a 2,048-token total context and a 0.70 GPU-memory budget. These settings
passed the local startup and inference checks with both GPU models loaded. The
installed loader uses NF4 with compressed statistics; vLLM's numerical behavior
has not been compared against Cue's Transformers run. The reference is
[vLLM's bitsandbytes documentation](https://docs.vllm.ai/en/v0.30.0/features/quantization/bnb/).

The initial `GPU access blocked by the operating system` error cleared after the
laptop restart. First startup then exposed a missing `ninja` command in the user
service's PATH. The launcher now adds the vLLM environment's `bin` directory,
allowing FlashInfer's kernel build to finish using the existing tools. The first
model load and warmup take several minutes. Both user services are now running.
Optional launcher overrides belong in
`docker/env/.env.generator`: `GENERATOR_GPU_MEMORY_UTILIZATION`,
`GENERATOR_MAX_MODEL_LEN`, `GENERATOR_PORT`, and `GENERATOR_WAIT_FOR_RERANKER`.
Keep any port change synchronized with the API base URL.

Local verification used project `900001`'s single indexed bilingual Article 1/2
chunk without reindexing or changing its source. `/health` returned 200 with all dependencies
ready. Two direct English/Arabic completions, cited English/Arabic Article 1
answers, an explicit Arabic request for the complete fallback sequence, a refusal
for a judge's unsupported personal name, and Article 2 SSE completion all returned
successfully. Inspecting the responses is a small semantic smoke check, not a
reviewed legal benchmark; the English Article 1 answer redundantly restates the
last fallback.

The loader reported 2.71 GiB for Qwen weights. Total sampled GPU use was 4,694 to
5,742 MiB out of 6,144 MiB with both services loaded; these are samples, not a
continuous peak measurement. Direct completions took 1.17/1.56 seconds, while
ordinary RAG probes took 4.63–9.12 seconds. The SSE probe completed in 6.45 seconds;
first delivered text arrived at 6.43 seconds because the configured guardrails
buffered the answer. This does not demonstrate low TTFT or concurrent capacity.
The ignored evidence is `eval/reports/qwen3-local-serving-verification.json`.

Verify a real generator request as well as health, without displaying the key:

```bash
.venv/bin/python - <<'PY'
import requests
from dotenv import dotenv_values

key = dotenv_values('docker/env/.env.generator')['VLLM_API_KEY']
response = requests.post(
    'http://localhost:8001/v1/chat/completions',
    headers={'Authorization': f'Bearer {key}'},
    json={
        'model': 'qwen3-legal-final',
        'messages': [
            {'role': 'system', 'content': 'Answer only from the supplied passage.'},
            {'role': 'user', 'content': 'Passage: The minimum age is 21 years. What is the minimum age?'},
        ],
        'temperature': 0,
        'max_tokens': 64,
    },
    timeout=120,
)
response.raise_for_status()
print(response.json()['choices'][0]['message']['content'])
PY
```

Then send ordinary English and Arabic requests through the RAG API with real
indexed documents and inspect their cited evidence. Start with `limit: 3`.
The total prompt plus output must fit 2,048 tokens; long legal articles can exceed
this. The API does not silently truncate a long generation prompt. A health
response or the acceptance set alone does not establish RAG answer quality.

The acceptance results favored base over both pilot adapters, but still include
omissions and Arabic translation errors. Both question languages used English
passages in that small test. Results are not a legal accuracy guarantee.

To restore the previous generation API using the saved setup snapshot:

```bash
cp docker/env/.env.fastapi.before-qwen docker/env/.env.fastapi
chmod 600 docker/env/.env.fastapi
docker compose -f docker/docker-compose.yml up -d --no-deps --force-recreate fastapi
docker compose -f docker/docker-compose.yml up -d --no-deps --force-recreate nginx
systemctl --user disable --now rag-ishms-generator.service
```

That restores the entire setup-time API environment; review later configuration
edits before using the snapshot. Generation changes need no reindexing. Embedding
changes would require their own new index.

## Previous Docker API — verified 2026-10-12

The local Docker configuration uses OpenRouter with
`GENERATION_MODEL_ID=nvidia/nemotron-3-ultra-550b-a55b:free`. The previous
`minimax/minimax-m3:free` returned 404 (free endpoint unavailable). A Gemma free
candidate returned 429; Nemotron completed a bilingual connectivity probe and
real application answers/streaming. Free endpoint availability and quotas can
change; consult https://openrouter.ai/docs/api/reference/limits.

Embedding remains `nvidia/llama-nemotron-embed-vl-1b-v2:free` on the same
OpenRouter API, verified to return 2,048 dimensions. No source-environment
credentials were copied or changed. Generation can be switched independently
when the fine-tuned model is ready.

FastAPI and nginx are running. Public-corpus smoke project `900001` contains
Articles 1–2 in `api-verification-civil-code.txt`; project 6 and its existing
documents/index were preserved. Live upload, processing/index jobs, cited
English/Arabic answers, SSE completion and feedback passed. The ignored report
is `eval/reports/api-verification.json`. This is a connectivity check, not a
RAGAS grade or load benchmark. The named Hugging Face cache was populated from
the existing local reranker cache; an older root-owned assets volume was corrected
to UID/GID 10001 so the API can upload and persist jobs.

Project 6's 1,242 stored chunks were also indexed into its current fingerprinted
collection. The first background run reached 1,050 chunks before the free upstream
per-minute quota failed it; the remaining 192 were resumed after the window reset
using the existing controller. The failed job remains recorded accurately. The
legacy index was retained. Local `INDEX_BATCH_DELAY_SECONDS=3.5` now paces future
indexing batches asynchronously; its default is 0 for unrestricted providers.

## GPU reranker — verified 2026-10-12

The existing vLLM 0.30.0 environment now serves the cached BGE reranker on the RTX
3060 Laptop GPU. `scripts/run_vllm_reranker.sh` uses FP16, 512-token pairs,
16 concurrent sequences, eager execution and a 0.45 GPU memory budget. Current
observed VRAM usage is approximately 1.3 GiB. It has a separate private service
key in docker/env/.env.reranker. No vLLM packages were installed in the API image.

The Docker API uses `RERANKER_BASE_URL=http://host.docker.internal:8002/v1` with
the same model ID and matching private key. HTTPReranker preserves the controller's
index/score contract, validates result indices/scores and closes its HTTP client
on shutdown. Readiness checks authenticated model availability. Empty URL restores
the existing embedded CrossEncoder; an unavailable remote service fails explicitly.

Start/stop/log commands and setup are in the root README's GPU section. The managed
user unit is deploy/systemd/rag-ishms-reranker.service; it is enabled on this
machine. Its initial startup can take a few minutes. Keep port 8002 restricted to
trusted host/Docker access. Long query/document pairs are truncated at 512 tokens;
this is a deliberate memory bound, not identical long-text processing to every
CrossEncoder configuration.

The project-8 prompt-chaining search retained 30 candidates and limit 5. It took
3.214 seconds on the first GPU run and 0.508/0.413 seconds on repeats; rerank stages
were 2.191/0.244/0.190 seconds. Earlier CPU reranking was 82.034 seconds with a
90.36-second Postman total. These three trials are a latency check, not a quality
or concurrency benchmark. The ignored report is
eval/reports/gpu-reranker-verification.json. No index rebuild was performed.

## Generation provider settings and streaming

Keep vLLM and its dependencies in the existing `/home/yacine_105/vllm-env`.
Do not install vLLM into this API environment or Docker image. Other compatible
generation servers use the same configuration fields shown below.

For Docker API generation, configure `docker/env/.env.fastapi`:

```dotenv
GENERATION_PROVIDER=OPENAI
GENERATION_BASE_URL=http://host.docker.internal:8001/v1
GENERATION_API_KEY=your-local-server-key
GENERATION_MODEL_ID=your-served-model-name
GENERATION_MODEL_TEMPERATURE=0.2
```

Use the port actually assigned to vLLM (8001 avoids the API's port 8000).
Compose maps host.docker.internal to the Docker host. The server must listen on
an address reachable from the Docker bridge. Configure its API key accordingly.
OPENAI_BASE_URL/OPENAI_API_KEY remain the embedding provider settings when
EMBEDDING_PROVIDER=OPENAI. Changing generation requires no vector rebuild.
Changing the embedding model requires reindexing into its new fingerprinted
collection. Pin the model revision in your release record.

POST `/api/v1/nlp/index/answer/stream/{project_id}` accepts the same JSON as answer.
SSE events are sources, token, done; an interrupted provider produces error.
Non-OpenAI providers return 501. Sources precede tokens. Zero hits stream the
no-information answer. Proxy buffering is disabled by the response header.
Streaming uses real provider chunks; it does not split a completed answer.
Streaming TTFT/duration and outcomes are instrumented. Stream token usage is not
estimated; ordinary token counters retain real non-stream provider usage. PII
redaction can buffer output and increase TTFT. Measure throughput with the actual
model when it is supplied.
