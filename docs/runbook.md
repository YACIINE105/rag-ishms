# Docker RAG operations

Start with `docker compose -f docker/docker-compose.yml ps`, then
`docker compose -f docker/docker-compose.yml logs --tail=100 fastapi`.
Check `curl -i http://localhost:8000/health`. A 503 identifies an unavailable
provider/database; inspect that dependency before changing prompts.

For free upstream models, local `INDEX_BATCH_DELAY_SECONDS=3.5` paces indexing
batches without blocking the event loop. A free-provider 429 can leave a failed
job with partial writes; inspect job status, let the quota window reset and retry
with pacing. Do not reset the collection merely because a batch was throttled.

## Alerts

For a remote reranker failure, check
`systemctl --user status rag-ishms-reranker.service` and
`journalctl --user -u rag-ishms-reranker.service -n 50 --no-pager`.
Start/restart the service before recreating the Docker API. The Docker API's
RERANKER_API_KEY must match VLLM_API_KEY in docker/env/.env.reranker. Generation
and embedding credentials are separate. Check VRAM with `nvidia-smi`; future
generation deployments must leave room for this reranker. To restore embedded
CPU serving, clear RERANKER_BASE_URL and recreate fastapi; retain the indexes.

**RAGServiceDown:** check API container and health, then Prometheus target status.
A failed scrape can be networking rather than an inference failure.
**RAGHighErrorRate:** correlate X-Request-ID with JSON logs; check provider
availability, timeout/rate limits, and database connectivity.
**RAGHighZeroHitRate:** compare language and index fingerprint in prediction
logs. Reprocess and index after changing embeddings. Never rename old vectors
to disguise an encoder change. Confirm the intended project contains chunks.

## Index jobs

POST `/api/v1/nlp/index/jobs/{project_id}` with `{"do_reset":0}` returns 202.
Poll GET `/api/v1/nlp/index/status/{job_id}` for queued/running/succeeded/failed.
The queue allows eight active jobs, one running at a time, and retains the last
100 records in an atomic assets-volume snapshot. One job per project is allowed.
Restart marks unfinished jobs failed with server_restarted; inspect and retry
the idempotent upsert with do_reset=0. Upload, processing and synchronous indexing
are blocked with 409 while a same-project job is queued/running.
Partial writes may remain on failure. No Redis worker is needed for this demo.

## Model release and rollback

Save the current generation settings and image tag before a release. Configure
GENERATION_BASE_URL, GENERATION_API_KEY, and GENERATION_MODEL_ID for the candidate.
Keep EMBEDDING_MODEL_ID fixed when changing only generation. Run the reviewed
benchmark before promotion and save its report with the model revision.
Revert those settings/image tag and recreate fastapi to roll back. Do not delete
Docker volumes. No blue/green infrastructure is required for this final project.

## Load evidence

Install Locust in a separate environment and run from the repository root:
`locust -f loadtest/locustfile.py --host http://localhost:8000 --users 50 --spawn-rate 5 --run-time 3m --headless --csv reports/load`.
Set LOADTEST_PROJECT_ID to a disposable project with the benchmark corpus indexed.
Use stage p95 in Grafana to identify the bottleneck. The benchmark treats missing
sources as failure because its questions are answerable. Do not report measured
throughput/quality until the actual fine-tuned generation model is available.

## Exposure

Metrics are blocked through nginx; port 8000 is a direct development port and
should remain private. Static API-key identities and project ACLs are implemented. Integrating the actual
ISHMS user/session policy and validating privacy protections is still required
before use with patient data. Benchmark legal text is sufficient for
the course demo. Regex checks cannot certify medical PII removal or groundedness.
Prometheus rules are visible in its Alerts UI; notification delivery is not
configured because no destination was supplied.


## Authentication and throttling

Docker API authentication is configured by scripts/configure_api_access.py. Send
X-API-Key from the ignored client environment file; keep it out of logs/reports.
401 means missing/invalid key; 403 means the identity lacks this project; 429 means
the single-worker key quota is exhausted. Follow Retry-After. To perform a measured
50-user test, increase RATE_LIMIT_PER_MINUTE/BURST for the isolated benchmark
identity/deployment, then restore normal limits afterward. A shared service key
shares one quota; it is not a replacement for authenticated individual users.

## Quality alerts

RAGLowFaithfulness: inspect the saved report per language, then compare corpus,
prompt hash and provider revision. RAGEvaluationFailed: check judge/configuration
before treating this as a model regression. RAGEvaluationStale: verify the evaluation
scheduler and host report publishing command; a GitHub artifact is not automatically
installed on this host. No sample result file is populated with fictitious scores.

## Redaction limitations

The deterministic rules cover specified bounded patterns. They can miss unlabeled
names, alternate contact formats and indirect/encoded injections. Stream output is
buffered to avoid leaking a known pattern across token boundaries, so TTFT includes
redaction delay. Raw text is omitted from optional Langfuse spans. Prediction logs
still require access controls and retention review before sensitive use.
