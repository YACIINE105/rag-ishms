# RAG-ISHMS Docker release

This deployment runs the existing API, Qwen generator, BGE reranker, PostgreSQL
with pgvector, and nginx as separate containers. It uses the selected **untuned**
Qwen base; no pilot fine-tuned adapter is loaded. Model download links and exact
revisions are in `models.json`, in `/app/model-sources.json` in the API image,
and `/opt/rag-ishms/models.json` in the vLLM image.

Weights download from Hugging Face on first startup and remain in the
`model_cache` volume. They are not embedded in image layers. No Hugging Face login
is needed for these public models. Allow approximately 10 GB for model downloads,
additional space for the CUDA images, and several minutes for initial warmup.
The runtime keeps the existing 4-bit Qwen and FP16 BGE settings.

## Start

Use an NVIDIA GPU, its working host driver, Docker Compose with GPU support and,
on Linux, NVIDIA Container Toolkit. Windows users need Docker Desktop's WSL 2 GPU
integration. GPU inference was previously verified on the 6-GB RTX 3060 Laptop;
the two models share its limited VRAM. Do not run duplicate host vLLM services
beside these containers. More free physical RAM improves startup and avoids SSD
paging; this bundle does not modify WSL memory or swap settings.

From this directory:

```bash
python3 configure.py
```

Edit `.env.fastapi` and set your embedding provider credentials, for example:

```dotenv
OPENROUTER_API_KEYS=["your-own-openrouter-key"]
```

Generation and reranking are local. Embeddings still use the current external
OpenRouter model and are subject to its availability and quota. Changing the
embedding model requires reindexing; switching deployment alone does not.

```bash
docker compose pull
docker compose up -d --no-build
docker compose ps
docker compose logs -f generator reranker fastapi
```

If GHCR requests authentication, sign in using a GitHub token with
`read:packages`, or make the two packages public in their GitHub package settings.
Do not put that token in this bundle or the application environment files.

The generator waits for the reranker to become healthy; the API waits for both
models and PostgreSQL. First startup can spend time downloading/warming models.
Read their logs before treating a pending dependency as an application failure.

```bash
curl --fail http://localhost/health
```

The API is on port 8000 and nginx on port 80. Set `API_PORT` and `HTTP_PORT` in
`.env` before startup if those ports are occupied. API port 8000 binds only to
localhost; model servers and PostgreSQL are internal to the Compose network.
The nginx endpoint uses HTTP; configure your existing HTTPS reverse proxy before
exposing it outside a trusted network.

Use `X-API-Key` in Postman. Its generated value is in `.env.client` as
`RAG_API_KEY`; `.env` contains different internal model/database credentials.
The setup script refuses to overwrite an existing release configuration.

For a fresh database, upload your PDF, process it with `W_qalam=true`, start the
index job, wait for success, and then submit a question. Existing documents and
indexes are not included in the release. A successful health check alone does
not verify embedding quota, document indexing or answer correctness.

```text
POST /api/v1/data/upload/9
POST /api/v1/data/process/9
POST /api/v1/nlp/index/jobs/9
GET  /api/v1/nlp/index/status/{job_id}
POST /api/v1/nlp/index/answer/9
POST /api/v1/nlp/index/answer/stream/9
```

Per-stage latency is available as `latency_ms` on `embed.done`, `retrieve.done`,
`rerank.done`, `prompt.done`, `generate.done` and total `http.done`. Entries share
the request ID. Streaming also records `generate.first_token`.

## Data and updates

This deployment uses its own `rag-ishms-release` project volumes. It does not
automatically migrate data from a different Compose project. Back up and restore
the database and document assets together when moving an existing installation.
Optional Langfuse credentials can be added to `.env.fastapi`; monitoring services
remain available in the source project's existing Docker configuration.

```bash
docker compose down
```

This stops containers while retaining volumes. Do not add `--volumes` unless
you intend to delete documents, the database and downloaded model cache.

Before upgrading, back up data and retain the previous release's image tags.
Use the archive's `manifest.json` for model identities, file hashes and published
image digests. The release does not train a model, guarantee legal correctness,
or establish production concurrency capacity.
