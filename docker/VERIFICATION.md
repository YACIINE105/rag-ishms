# Docker verification

## Civil Code evaluation follow-up — 2026-10-16

- Rebuilt the existing FastAPI image with the tested asset-ID processing lookup,
  Qalam citation headers, async model wait gate, 30-second bulk SQL budget and
  idempotent PGVector batch replacement. No active production job existed before
  recreation; existing settings, documents and vector volumes were preserved.
- Live nginx readiness returned 200 with all dependencies ready. Missing-key
  and authenticated blank-query checks returned 401 and 422 with request IDs.
  The async wait gate is present in the running image. Existing chunks were not
  rewritten to acquire the new Qalam headers.
- Full suite: **243 passed, 86.55% source coverage**. Actual evaluation-project
  SQL verified that two identical chunk reinsertions retain exactly 2,297 rows.
- The real isolated PGVector load run observed 50 users, 58 answer requests and
  50 failures, with p95 at the 180-second timeout. Six guarded SSE probes finished.
  This is a failed capacity target, not a successful 50-user qualification.
- Grafana returns the provisioned dashboard with 13 panels; all five Prometheus
  targets are up. The port-8003 load API used saved metric snapshots and was not
  a production scrape target. See the final-project report for quality-scoring
  status, endpoint differences and retained failures.
- After the laptop restart, both managed GPU servers returned health 200 and
  the existing Docker containers recovered. API/nginx readiness again returned
  200; missing-key and blank-query checks returned 401/422 with request IDs.
  The image ID matches the tested rebuild. This is a restart check, not a new
  50-user capacity result.

## GPU reranker follow-up — 2026-10-12

- Host RTX 3060 Laptop GPU (6 GiB) and existing vLLM 0.30.0 / CUDA environment
  verified. The cached BGE reranker now runs as an authenticated managed user
  service on port 8002, using FP16 and 512-token pairs; approximately 1.3 GiB
  of VRAM was observed.
- Docker-to-host authentication, model readiness, remote result validation and
  HTTP client shutdown passed. The Docker API no longer loads the embedded
  CrossEncoder while remote serving is configured. Existing indexes remain intact.
- Same project-8 search, 30 candidates and limit 5: total 3.214 seconds first run,
  then 0.508/0.413 seconds; rerank stages 2.191/0.244/0.190 seconds. Prior CPU
  reranking was 82.034 seconds. These are three latency trials, not a load test.
- Full suite: **202 tests**, 12 subtests, **86.21% source coverage**. Docker image
  rebuild and live health passed. Service unit/shell syntax were verified.
- Long-pair truncation and FP16 can affect scores; no quality-equivalence claim
  is made. Generation/embedding settings and the existing vLLM installation were
  not changed. Keys and detailed local reports remain ignored.

## Live API follow-up — 2026-10-12

- OpenRouter generation `minimax/minimax-m3:free` returned 404; a free Gemma
  candidate returned 429. `nvidia/nemotron-3-ultra-550b-a55b:free` completed a
  bilingual probe and is now the local Docker generation model.
- The unchanged free embedding endpoint returned 2,048-dimensional vectors.
- FastAPI and nginx started healthy. Readiness and authenticated API contract
  smoke tests passed directly on port 8000 and through nginx on port 80.
- Public-corpus project 900001 passed upload, background processing/indexing,
  cited answers to English/Arabic questions, streaming completion and feedback.
  Its ignored local report is eval/reports/api-verification.json.
- The existing assets volume was root-owned; its ownership was corrected to
  UID/GID 10001. Cached reranker files were copied into the named HF cache.
- PGVector collection discovery/counting now includes both legacy numeric and
  current fingerprinted names. A regression test covers both formats.
- After the counting and batch-pacing fixes, the full suite passed **192 tests**
  and 12 subtests with **86.00% source coverage**. The updated image was rebuilt.
- Existing project 6 and its index/documents were preserved. No full RAGAS
  evaluation, concurrency benchmark or fine-tuned/vLLM deployment is claimed.
- Project 6 now has a complete current fingerprinted index of 1,242 chunks.
  Its initial background run failed at the free upstream's per-minute limit after
  1,050 chunks; the remaining 192 were resumed through the existing controller
  after the window reset. The failed job record was retained. Local indexing is
  now paced at 3.5 seconds between batches; unrestricted deployments default to 0.

## Model-independent checks — 2026-10-12

The final-project changes preserve the existing architecture and defer model
setup and inference measurements at the user's request.

- Final production Docker image built successfully, including native
  llama-cpp-python, psycopg2, Qalam and the optional Langfuse SDK.
- In-image imports and `pip check` passed. Runtime UID is 10001 and gcc/g++/cc
  are absent.
- In-image HTTP contract checks passed without running application lifespan:
  missing API key returns 401; authenticated blank search returns 422 with a
  request ID; metrics and OpenAPI expose the expected job, stream, feedback and
  article citation contracts. No inference or model download was invoked.
- Full pytest suite: **190 passed**, 12 subtests passed, **85.97% source coverage**.
- Ruff/pre-commit, Compose configuration and `git diff --check` passed.
- Editable installation/import checks and DVC reproduction passed; DVC status
  reports all corpus stages up to date.
- Live Grafana provisioning exposes 13 panels. Prometheus loaded all six alert
  rules; its configuration passed promtool. PostgreSQL, Qdrant, node-exporter and
  Prometheus scrape targets are up.
- The API is not running, so its scrape target is down. Full readiness, real
  answers, evaluation grades and 50-user load results remain deferred until the
  generation model is supplied. Earlier readiness results below are historical.
- Docker API authentication is enabled locally. The client secret is stored in
  ignored `docker/env/.env.client`; no secret was printed or committed. Temporary
  verification containers were removed. Existing database/vector volumes were
  not reset and the separate vLLM environment was not modified.

## Historical checks — 2026-10-06

Verified locally with Docker Desktop 29.8.1 and the native Ubuntu-24.04 WSL client.
The production Dockerfile built successfully with Python 3.12 and CPU PyTorch
2.14.1. No ONNX conversion or dependency was introduced.

## Results

- Image build succeeded, including native llama-cpp-python and psycopg2 wheels.
- Runtime UID is 10001; gcc, g++, and cc are absent.
- Assets and Hugging Face cache are writable; the model bind mount is read-only.
- Native imports succeeded and `pip check` found no broken requirements.
- The real cached BAAI reranker loaded offline on CPU.
- Both Alembic migrations ran successfully against a temporary PostgreSQL database.
- `/health` returned 200 with every dependency reporting `ok`, using PGVector
  and then a separate Qdrant server. Model readiness probes reached the configured
  OpenAI-compatible service without text generation.
- Nginx started after the application became healthy. API smoke checks passed
  directly and through nginx for both vector backends.
- POST routes, exact answer schema fields, blank/invalid input returning 422,
  and returned `X-Request-ID` headers passed live checks.
- Pausing the temporary PostgreSQL container exposed a cancellation-timeout bug.
  After the fix, readiness returned 503 during the outage and recovered after
  database connections finished recovering. Unit coverage includes delayed driver
  cancellation so the response deadline is independent of cleanup completion.
- Application/migration logs parsed as JSON with the six required fields and
  correlated request/project IDs.
- Full pytest suite: **114 passed**, 12 subtests passed, **83.15% source coverage**.
- Default and Qdrant Compose configurations and `git diff --check` passed.

## Scope

Verification used the final image with isolated temporary PostgreSQL/Qdrant
containers and a separate assets volume. Existing application database volumes
were not migrated or modified. Tests did not upload documents or generate answers;
answer quality and every remote model's inference capability are outside these
Docker checks. Temporary verification resources were removed afterward.

The local, untracked Docker environment file also needed its database hostname,
HF cache path, and a missing newline corrected. No credentials were committed.

Run `python docker/smoke_test.py --base-url http://localhost:8000` to repeat HTTP
readiness and API contract checks against a running deployment.
