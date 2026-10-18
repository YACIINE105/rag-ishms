# Optional Langfuse and quality monitoring

RAG latency is also available directly in the API's JSON logs, without Langfuse:

```bash
docker logs --since 5m fastapi
```

For the same `request_id`, read `latency_ms` on `embed.done` (query embedding),
`retrieve.done` (vector search only), `rerank.done`, `prompt.done` and
`generate.done`. The final `http.done` records the total HTTP request duration
and is always logged for RAG search/answer requests. Other successful access
events remain sampled. Stages that do not run have no timing entry.

Streaming also logs `generate.first_token`; its `generate.done` includes
`first_token_ms`, `streamed=true` and `completed=true`. A stream that stops early
logs `generate.interrupted` with `completed=false`. The HTTP total includes
stream consumption. Timings measure elapsed wall time, including provider queue
waits, network calls and retries; they are not isolated GPU compute measurements.
The total includes remaining request overhead, so it can exceed the stage sum.

No Langfuse credentials or hosted project are required for the local API. To
export traces later, set LANGFUSE_ENABLED=true, LANGFUSE_PUBLIC_KEY,
LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL and APP_ENVIRONMENT in the API environment.
The pinned Python SDK is included in the API image. Use an existing authorized
Langfuse instance; this project does not add its multi-service hosting stack.

An answer trace contains retrieve, embed, rerank and generation spans. Streaming
uses explicit observation IDs so the SSE threadpool does not transfer a ContextVar
token across threads. Request IDs map deterministically to trace IDs. When
tracing is enabled, the answer observation records the question, final answer
and source citations. Its generation observation records the system/user
messages and generated response, with actual token usage for ordinary answers.
Inputs are captured before the provider modifies conversation history. Content
passes through the existing PII redaction before export and the SDK mask.
Local JSON prediction logs also retain redacted content.

Readiness checks do not create inference traces. Docker calls `/health` every
30 seconds, and its generation, embedding and reranker probes previously created
empty `provider` observations even without user requests. These probes still use
the shared client locks and worker pool, but skip the tracing wrapper. Existing
empty observations remain in Langfuse history.

For streaming, open the generate observation to see the prompt, assembled answer
and time to first nonempty token. Partial streams retain their partial output
and completed=false; failures are marked ERROR and interrupted streams WARNING.
Streaming token usage remains unset because the current iterator exposes only
text. The parent answer observation records question/sources before streaming
begins; the streamed answer is on its generate child. Export/update failures
do not change application answers. Keep retention/access controls appropriate
to your environment. Auth identities should be stable internal IDs.

Existing traces are not backfilled: submit a new answer after rebuilding the
API and open its answer/generate observations in Langfuse. Cost requires a
matching model price definition or explicitly supplied measured costs. A local
Qwen model alias has no inferred API price by default. Prompt Name requires a
linked Langfuse prompt object; the local prompt-version metadata alone does not
populate that field. These fields may legitimately remain empty.

Set LANGFUSE_PROMPT_LABEL=production to fetch `rag-system-en` or `rag-system-ar`.
Only the system prompt is remote-managed; document/footer templates stay local.
Fetch runs off the API event loop, caches for 60 seconds and falls back to the
local template on failure. Prompt versions include the local content hash and
remote version when used. Model/temperature remain explicit server configuration.

Feedback requires an issued answer receipt for the current user/project. Receipts
are limited to the latest 1,000 identities/requests and disappear on restart.
Local redacted feedback is append-only in the assets volume; export failure does
not erase it. Rotate/archive feedback according to your retention policy.

After a real evaluation, run:

```bash
uv run python scripts/publish_eval_metrics.py --report eval/reports/latest.json
```

The publisher atomically writes reports/metrics/rag_eval.prom, mounted into
node_exporter's textfile collector. Scores are reported per language. Missing
metrics are omitted. A failed configuration report records failure, not an invented
quality score. Recreate node_exporter after adding the new mount/collector flag.

Rules include service availability, HTTP error rate, zero hits, faithfulness <0.80,
evaluation failure and stale evaluation timestamps. Quality rules activate only
when a report exists. Alerts are visible in Prometheus; outbound notifications
remain unconfigured because no destination was supplied.

A nightly CI artifact is stored on GitHub, not automatically copied to the Docker
host. Publish/download the actual report on this host to update the dashboard.
No endpoint silently accepts arbitrary unauthenticated quality reports.
