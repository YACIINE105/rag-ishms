# Docker setup for RAG ISHMS

Run the following commands from the repository root. The default setup uses
PostgreSQL/pgvector. FastAPI runs as UID/GID 10001 and nginx waits for `/health`.

## Configuration

```bash
cp docker/env/.env.example.fastapi docker/env/.env.fastapi
cp docker/env/.env.example.postgres docker/env/.env.postgres
cp docker/env/.env.example.grafana docker/env/.env.grafana
cp docker/env/.env.example.postgres-exporter docker/env/.env.postgres-exporter
```

Edit those files for your configuration. Never commit credentials. Set
`POSTGRES_HOST=pgvector` inside the application container and use matching
PostgreSQL credentials. The image installs `alembic.example.ini`; migrations
read the database connection from the application environment variables.

Put the reranker's downloaded Hugging Face files in `hf_cache/hub/` before
building. The image is offline by default and only includes that hub cache.
GGUF weights are excluded from the image: place them in `ai-models/` (or set
`MODEL_DIR` to another host directory) and configure model IDs with container
paths such as `/app/ai-models/model.gguf`. This directory is mounted read-only;
the host files must be readable by UID 10001. The application assets and the
copied HF cache are owned by appuser and remain writable.

```bash
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up --build -d
```

Existing asset volumes created by the previous root image may need an ownership
migration. Back up the volume, then use this one-off command only for that case:

```bash
docker compose -f docker/docker-compose.yml run --rm --no-deps --user root --entrypoint chown fastapi -R 10001:10001 /app/assets
```

## Qdrant server mode

Embedded Qdrant remains available when `VECTOR_DB_BACKEND=QDRANT` and
`QDRANT_URL` is unset. It uses `/app/assets` and requires one application worker.
To connect to the separate Qdrant service, use the profile and override together:

```bash
cp docker/env/.env.example.qdrant docker/env/.env.qdrant
docker compose -f docker/docker-compose.yml -f docker/compose.qdrant.yml --profile qdrant up --build -d
```

The override sets the backend and URL and adds a `service_healthy` dependency
on Qdrant. If authentication is enabled, set the same key in the server's
configuration and the application's `QDRANT_API_KEY` environment variable.
Switching from embedded storage to server mode requires indexing documents
into the server; it does not migrate existing local points automatically.

## Readiness and logs

- API docs: http://localhost:8000/docs
- Application through nginx: http://localhost/
- Readiness: http://localhost/health
- Metrics: http://localhost:8000/rag_ishms_metrics_v__0
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (credentials come from its environment file)
- Qdrant dashboard in server mode: http://localhost:6333/dashboard

`/health` returns 503 when a required dependency fails. Docker probes every
30 seconds with a 180-second model startup allowance. Nginx waits for initial
readiness; Compose does not continuously remove an unhealthy upstream.

Application logs are JSON. Set `LOG_LEVEL=DEBUG` to include prompt text.
`HTTP_ACCESS_LOG_SAMPLE_RATE` controls successful access logs (default 0.1);
prediction events containing the query, retrieved IDs, and answer are never
sampled. Keep these logs access-controlled because they contain application data.
Every response has an `X-Request-ID`, also present in its correlated log events.

```bash
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs --tail=100 fastapi
```

The production image does not enable reload. Rebuild after code changes.
The entrypoint runs migrations and then executes the supplied command, so CMD
or Compose `command` controls server flags. The runtime image contains the
virtual environment and runtime libraries, without builder compilers.


## Building from WSL

Run Docker commands inside the WSL distribution containing the repository.
Building from a Windows `\\wsl.localhost` path can fail when Docker transfers
Hugging Face snapshot symlinks. The native Linux client preserves those links.

The default image installs CPU-only PyTorch because this Compose configuration
does not request a GPU. `TORCH_VERSION` and `TORCH_INDEX_URL` are Docker build
arguments for an alternative PyTorch wheel source. GPU deployment also requires
matching drivers, runtime configuration, and GPU access in Compose. Native llama
builds are limited to two compiler jobs to reduce peak build memory.

For container settings, use `POSTGRES_HOST=pgvector` and `HF_HOME=/app/.hf_cache`.
Each environment assignment must occupy its own line; do not copy host cache
paths into the application container configuration.


## Runtime smoke checks

After the stack becomes healthy, run these checks from the repository root:

```bash
python docker/smoke_test.py --base-url http://localhost:8000
python docker/smoke_test.py --base-url http://localhost
```

They verify real readiness signals, request ID headers, POST routes, answer
schema and 422 validation through both FastAPI and nginx. They do not upload
documents or invoke text generation. Real readiness probes still contact the
configured model services. Use `--expect-unhealthy` to verify HTTP 503 only when
deliberately testing a dependency outage in an isolated environment.

See [recorded verification](VERIFICATION.md) for the tested image behavior and remaining scope.
