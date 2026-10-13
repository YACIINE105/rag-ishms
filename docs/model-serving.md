# Model serving

## Current Docker API — verified 2026-10-12

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

## Separate vLLM generation later

Keep vLLM and its dependencies in the existing `/home/yacine_105/vllm-env`.
Do not install vLLM into this API environment or Docker image. Later start your
fine-tuned model from that environment with the served model name you choose.
This change does not download weights or start an unprovided model.

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
