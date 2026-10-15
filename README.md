# RAG-ISHMS

Upload PDF or TXT documents, index their contents, and ask questions with source
citations. The system runs FastAPI behind nginx, stores documents/chunks in
PostgreSQL, retrieves with PGVector or Qdrant, and uses a cross-encoder reranker
before calling an OpenAI-compatible generation API.

The local setup uses **Docker + PGVector**, with Qwen generation and BGE reranking
in the existing separate vLLM environment. The selected model is the pinned
**untuned `Qwen/Qwen3-4B-Instruct-2507` base**, served as `qwen3-legal-final`;
neither pilot adapter was selected. Embeddings still use OpenRouter's
`nvidia/llama-nemotron-embed-vl-1b-v2:free` with 2,048 dimensions.

Qwen runs in 4-bit on the laptop GPU alongside the reranker. Authenticated
generation, cited English/Arabic RAG answers, health and SSE completion have been
checked locally. The larger quality benchmark and 50-user load test remain open;
these small checks do not establish error-free legal answers. See
[model setup and verification](docs/model-serving.md).

## Start the already configured project

Run these commands in Bash from the repository root:

```bash
cd /home/yacine_105/rag-ishms

systemctl --user start rag-ishms-reranker.service rag-ishms-generator.service

docker compose -f docker/docker-compose.yml up -d

docker compose -f docker/docker-compose.yml ps
curl --fail-with-body http://localhost/health
```

`up -d` runs the services in Docker; you can close the terminal afterward. Qwen's
first load can take several minutes. The host services also run without background
terminals. Wait for
`fastapi` to become healthy before using nginx. The health response should contain
`"status":"healthy"`. On this machine, project **6** already has **1,242 chunks**
indexed, so you can ask questions immediately.

Load the client key into your terminal without displaying it:

```bash
set -a
source docker/env/.env.client
set +a
```

Then ask a question about the existing machine-learning documents:

```bash
curl --fail-with-body http://localhost/api/v1/nlp/index/answer/6 \
  -H "X-API-Key: $RAG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"What is supervised machine learning?","limit":3}'
```

The JSON response contains `answer`, `sources`, `request_id`, and `prompt_version`.
Use the returned sources to inspect the supporting document. Questions outside the
indexed documents can produce a no-information answer with empty sources.

| Service | URL | Access |
|---|---|---|
| Interactive API documentation | http://localhost/docs | Use **Authorize** and enter your client key |
| Health | http://localhost/health | No API key required |
| Direct FastAPI documentation | http://localhost:8000/docs | Same API key |
| Grafana | http://localhost:3000 | Credentials in `docker/env/.env.grafana` |
| Prometheus | http://localhost:9090 | Local monitoring UI |

The key belongs in the `X-API-Key` header, not in the question or URL. The local
key files are ignored by Git. The direct API and monitoring ports are intended
for your trusted development environment.

## First setup on a fresh checkout

Skip this section if the project is already configured as above.

You need Docker with Compose, Python 3.12, and `uv`. Docker runs the application's
Python dependencies; a host installation of vLLM is not needed for this API setup.

### 1. Create the private configuration files

From the repository root:

```bash
uv run --no-project --with python-dotenv python scripts/configure_api_access.py
```

This copies missing Docker environment examples, enables API authentication, and
creates `docker/env/.env.client` when generating the initial service key. It
preserves existing environment files and credentials.

### 2. Set database and model credentials

Edit these private files before starting Docker:

| File | Required configuration |
|---|---|
| `docker/env/.env.postgres` | Set `POSTGRES_PASSWORD`; keep `POSTGRES_USER=postgres`, `POSTGRES_DB=rag-ishms` |
| `docker/env/.env.fastapi` | Set the matching `POSTGRES_PASSWORD`, model API key, and settings below |
| `docker/env/.env.postgres-exporter` | Set `DATA_SOURCE_PASS` to the same database password |
| `docker/env/.env.grafana` | Set `GF_SECURITY_ADMIN_PASSWORD` |

For an OpenRouter-only generation setup, set these values in
`docker/env/.env.fastapi`. Replace the API-key placeholder with your own key:

```dotenv
POSTGRES_HOST=pgvector
POSTGRES_PORT=5432
POSTGRES_USERNAME=postgres
POSTGRES_MAIN_DATABASE=rag-ishms

GENERATION_PROVIDER=OPENAI
EMBEDDING_PROVIDER=OPENAI
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=YOUR_OPENROUTER_API_KEY
GENERATION_BASE_URL=
GENERATION_API_KEY=
GENERATION_MODEL_ID=nvidia/nemotron-3-ultra-550b-a55b:free
GENERATION_MODEL_TEMPERATURE=0.2
MAX_OUTPUT_TOKENS=1000
EMBEDDING_MODEL_ID=nvidia/llama-nemotron-embed-vl-1b-v2:free
EMBEDDING_MODEL_SIZE=2048
VECTOR_DB_BACKEND=PGVector
RERANKER_ENABLED=true
INDEX_BATCH_DELAY_SECONDS=3.5
```

Keep the generated `API_AUTH_ENABLED=true` and `API_CLIENTS` settings. The service
key generated by the setup script has access to all projects; narrower project
permissions can be configured in `API_CLIENTS`.

Free provider availability and quotas can change. The old
`minimax/minimax-m3:free` endpoint failed during verification; do not use that
example value. A healthy `/health` confirms dependency readiness, but an actual
answer request is still needed to verify generation. See
[model configuration and verification](docs/model-serving.md).

For Docker, `docker/env/.env.fastapi` controls the application. `src/.env` is for
host execution and is not the configuration file to edit for this deployment.

### 3. Build and start

```bash
docker compose -f docker/docker-compose.yml up -d --build

docker compose -f docker/docker-compose.yml ps

docker compose -f docker/docker-compose.yml logs --tail=100 fastapi

curl --fail-with-body http://localhost/health
```

The first image build compiles native dependencies and can take several minutes.
The first application start also downloads the multilingual reranker if its named
Hugging Face cache is empty. Model caching, uploaded files, and database contents
persist in Docker volumes. A fresh checkout does not include your existing local
project 6 database; upload and index documents using the next section.

## GPU reranking with the existing vLLM environment

The current machine uses `BAAI/bge-reranker-v2-m3` served by vLLM 0.30.0 from
`/home/yacine_105/vllm-env`, on port 8002. The Docker API calls its authenticated
`/v1/rerank` endpoint; it does not load a second CrossEncoder or need CUDA packages
inside its image. Your indexes and Postman request URLs remain the same.

To reproduce this setup on a machine with that vLLM environment and a CUDA GPU:

```bash
uv run --no-project --with python-dotenv python scripts/configure_reranker.py

mkdir -p ~/.config/systemd/user
cp deploy/systemd/rag-ishms-reranker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now rag-ishms-reranker.service

docker compose -f docker/docker-compose.yml up -d --build fastapi nginx
curl --fail-with-body http://localhost/health
```

The supplied user unit assumes the checkout is `~/rag-ishms`; adjust its paths
for another location. The startup script uses `~/vllm-env/bin/vllm` by default;
`VLLM_BIN` can select another existing installation. It reuses the cached BGE
weights in `hf_cache`; without those weights, vLLM downloads the same model.
vLLM dependencies remain separate from this API project.

The configuration helper creates a separate private key in
`docker/env/.env.reranker` and configures `RERANKER_BASE_URL`/`RERANKER_API_KEY` in
the Docker API environment. This service key is separate from `RAG_API_KEY`;
Postman still sends your existing application key. Both private files are ignored.

The server uses FP16, a 512-token query/document pair limit and at most 16
concurrent sequences; long pairs are truncated. It uses about 1.3 GiB of VRAM on
the current 6 GiB GPU. `RERANKER_GPU_MEMORY_UTILIZATION` defaults to 0.45. The
pair limit must agree between the vLLM service and `RERANKER_MAX_LENGTH` in the API;
review longer legal chunks before interpreting their quality scores.

Useful service commands:

```bash
systemctl --user status rag-ishms-reranker.service
journalctl --user -u rag-ishms-reranker.service -n 50 --no-pager
systemctl --user restart rag-ishms-reranker.service
systemctl --user stop rag-ishms-reranker.service
```

This is a managed user service; it needs no background terminal. Start it before
the Docker API after restarting WSL. `docker compose down` does not stop this
host service. If it is unavailable, `/health` reports the reranker dependency as
an error. Clear `RERANKER_BASE_URL` to restore the embedded CPU reranker and
recreate the API. Reindexing is not needed for a reranker change.

Measured on project 8 with the same prompt-chaining question and 30 candidates:
3.21 seconds for the first GPU search, then 0.51/0.41 seconds on repeats, compared
with the prior 90.36-second Postman request. This is a small latency check, not a
concurrency or answer-quality benchmark.

## Local Qwen generation

The generator runs on port 8001 from `~/vllm-env`; Docker calls it through
`host.docker.internal`. Its weights are stored at
`/mnt/g/rag-ishms-models/Qwen3-4B-Instruct-2507`, linked from
`~/vllm-env/models/Qwen3-4B-Instruct-2507`. Keep G: mounted when starting it.

The setup, download/resume command, service logs, verification requests and
rollback instructions are in [model serving](docs/model-serving.md#local-qwen-generator--verified-2026-10-15).
Postman continues to use the same RAG URLs and `X-API-Key`; the generator has its
own private service key. No document reindexing is required for this switch.

## Add your documents

The normal flow is **upload → process → index → ask**. Use a positive integer as
`project_id`; keep unrelated document collections in separate projects.

The helper below handles upload, background job submission, and status polling.
Load the client key first, then replace `/absolute/path/document.pdf` with your file:

```bash
set -a
source docker/env/.env.client
set +a

uv run --no-project --with requests python scripts/reindex_project.py \
  --base-url http://localhost \
  --project-id 7 \
  --file /absolute/path/document.pdf
```

For a structured bilingual legal PDF with article headings, add `--qalam` to
produce separate Arabic/English article chunks and richer article citations:

```bash
uv run --no-project --with requests python scripts/reindex_project.py \
  --base-url http://localhost \
  --project-id 7 \
  --file /absolute/path/legal-document.pdf \
  --qalam
```

Use ordinary processing for general PDFs and TXT files. The helper uses
`do_reset=0` and waits for processing to succeed before indexing. Its default
polling timeout is 1,800 seconds; `--timeout` changes it. If it times out, check the
printed status URL before submitting another job.

The helper processes the project's eligible files, not only the newly uploaded
file. Uploading the same filename replaces the previous asset and its current
indexed chunks. Use distinct filenames when you intend to keep both documents.

After the helper reports completion, ask a question at
`/api/v1/nlp/index/answer/7`, using the same JSON/header pattern as project 6.

## Use the API directly

All `/api/v1/data/*` and `/api/v1/nlp/*` requests require `X-API-Key`.
Swagger at `/docs` provides forms for every endpoint, including file uploads.

| Method | Endpoint | Body or purpose |
|---|---|---|
| GET | `/health` | Readiness; no key required |
| POST | `/api/v1/data/upload/{project_id}` | Multipart field `file`: PDF or TXT |
| POST | `/api/v1/data/process/jobs/{project_id}` | Start processing; examples below |
| GET | `/api/v1/data/process/status/{job_id}` | Processing status/results |
| POST | `/api/v1/nlp/index/jobs/{project_id}` | `{"do_reset":0}` |
| GET | `/api/v1/nlp/index/status/{job_id}` | Indexing status/results |
| GET | `/api/v1/nlp/index/info/{project_id}` | Collection information and vector count |
| POST | `/api/v1/nlp/index/search/{project_id}` | `{"text":"question","limit":3}`; retrieved chunks |
| POST | `/api/v1/nlp/index/answer/{project_id}` | Same body; generated answer and sources |
| POST | `/api/v1/nlp/index/answer/stream/{project_id}` | Same body; streamed answer |
| POST | `/api/v1/nlp/answer/feedback/{project_id}` | Answer `request_id`, score, optional comment |

Ordinary processing body:

```json
{"chunk_size":500,"overlap_size":50,"do_reset":0}
```

Legal article processing body:

```json
{"W_qalam":true,"do_reset":0}
```

A submitted background job returns HTTP 202 and a `job_id`. Poll the corresponding
status endpoint until `state` is `succeeded` or `failed`; other states are `queued`
and `running`. Wait for processing to succeed before starting indexing. Avoid
uploading or modifying that project while its job is active.

Synchronous `/api/v1/data/process/{project_id}` and
`/api/v1/nlp/index/push/{project_id}` remain available; use the background endpoints
for larger documents. Keep `do_reset=0` for normal updates. Reset requests remove
existing project processing/index data.

For streaming, add `-N` to curl:

```bash
curl -N --fail-with-body http://localhost/api/v1/nlp/index/answer/stream/6 \
  -H "X-API-Key: $RAG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Explain supervised learning briefly.","limit":3}'
```

SSE events are `sources`, `token`, and `done`; provider failures emit `error`.
Streaming can buffer some output for PII filtering. Treat `done` as completion,
not the initial HTTP 200 alone.

Send feedback using a successful answer's returned `request_id`:

```json
{"request_id":"RETURNED_REQUEST_ID","score":1,"comment":"Helpful answer"}
```

Scores range from −1 to 1. Feedback must come from the same identity/project that
received the answer; answer receipts expire after restart or after 1,000 entries.

## Restart, update, and stop

These commands run from the repository root:

```bash
# Apply changes to the API environment file or recreate its container.
docker compose -f docker/docker-compose.yml up -d --force-recreate fastapi

# Rebuild after changing application source or image dependencies.
docker compose -f docker/docker-compose.yml up -d --build fastapi nginx

# Inspect recent logs without opening a persistent terminal.
docker compose -f docker/docker-compose.yml logs --tail=100 fastapi

# Follow logs; Ctrl+C closes the log view and leaves Docker running.
docker compose -f docker/docker-compose.yml logs -f fastapi

# Stop the stack while retaining its stored data.
docker compose -f docker/docker-compose.yml down
systemctl --user stop rag-ishms-reranker.service

# Start it again.
systemctl --user start rag-ishms-reranker.service
docker compose -f docker/docker-compose.yml up -d
```

Do not add `-v` to `down` unless you intend to delete the database, uploaded files,
model cache, and monitoring volumes. Jobs interrupted by restart are marked failed;
work does not resume automatically, and partial writes may remain.

## Troubleshooting

| Symptom | What to check |
|---|---|
| nginx is unavailable or returns 502 | Check `docker compose -f docker/docker-compose.yml ps` and API logs; nginx waits for API health |
| `/health` returns 503 | Inspect its dependency fields, then API logs; check database credentials and model API reachability |
| 401 | Reload `docker/env/.env.client` and send `X-API-Key` |
| 403 | Check the key's allowed projects in `API_CLIENTS` |
| 409 | Poll the active project job before another upload/process/index request |
| 422 | Provide nonblank `text`, `limit` between 1 and 20, and overlap smaller than chunk size |
| 429 | Follow `Retry-After`; upstream free-model quotas are separate from the application's quota |
| Failed indexing after upstream 429 | Wait for the upstream quota window, inspect the partial index, then retry with `do_reset=0` and batch pacing |
| Empty sources/no information | Check project ID, processing/index job results, and whether the question is covered by those documents |
| Upload fails with `Permission denied` | Correct an old root-owned assets volume using the command below |

For the known non-root migration issue, preserve the files and correct ownership:

```bash
docker compose -f docker/docker-compose.yml run --rm --no-deps \
  --user 0 --entrypoint sh fastapi \
  -c 'chown -R 10001:10001 /app/assets'
```

Changing only the generation model requires recreating the API, not reindexing.
Changing the embedding provider/model/dimension creates a different fingerprinted
collection; re-index the stored chunks for that configuration. An old legacy index
is not automatically converted. See the [runbook](docs/runbook.md) for recovery.

## Development, evaluation, and monitoring

Host-side development tools are optional for running Docker:

```bash
uv sync --locked --group dev
uv run pytest
uv run pre-commit run --all-files
```

The verified suite has 202 tests plus 12 subtests, with 86.21% source coverage; tests
use mocks and do not download native model weights or make paid inference calls.

For the reproducible legal corpus and optional evaluation tools:

```bash
uv sync --locked --group dev --group data --group eval
uv run dvc repro
uv run dvc status
```

The corpus contains 1,149 article records. The exact source PDF has an Arabic
alignment defect around Articles 1021–1022, recorded in a checksum-pinned issue
manifest. The 52-case monitoring dataset is a draft requiring human review.
Actual RAGAS grades, experiment results, and 50-user load measurements still need
to be run; successful connectivity checks do not establish answer quality.
See [evaluation instructions](eval/README.md).

Grafana's 13 panels and Prometheus's six alert rules are provisioned automatically.
Quality panels need a real evaluation report before displaying scores. Langfuse
is optional and requires separate credentials; its traces omit raw query/document/
answer content. `/metrics` is available on port 8000 and blocked through nginx.

The existing FastAPI/controllers/provider factories and PostgreSQL/PGVector/Qdrant
architecture are retained. Keep one API worker for the current job/model/quotas
implementation. Deterministic guardrails are limited and do not certify medical
privacy or answer correctness; use public documents for the course demonstration.

- [Model serving and future vLLM configuration](docs/model-serving.md)
- [Monitoring, tracing, and feedback](docs/observability.md)
- [Plan review and scope limits](docs/plan-review.md)
- [Verified Docker and API results](docker/VERIFICATION.md)
- [Docker/Qdrant details](docker/README.md)
- [Send queries to the Cue bot and read replies](docs/cue-mail.md)

`certifcates_sys/` is a separate assignment and is not needed to run this RAG API.
