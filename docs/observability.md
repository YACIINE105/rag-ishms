# Optional Langfuse and quality monitoring

No Langfuse credentials or hosted project are required for the local API. To
export traces later, set LANGFUSE_ENABLED=true, LANGFUSE_PUBLIC_KEY,
LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL and APP_ENVIRONMENT in the API environment.
The pinned Python SDK is included in the API image. Use an existing authorized
Langfuse instance; this project does not add its multi-service hosting stack.

An answer trace contains retrieve, embed, rerank and generation spans. Streaming
uses explicit observation IDs so the SSE threadpool does not transfer a ContextVar
token across threads. Request IDs map deterministically to trace IDs. No query,
retrieved text, prompt or answer content is supplied to the exporter; local JSON
prediction logs retain redacted content. The recursive SDK mask is a secondary
limited defense for values explicitly supplied later. Keep retention/access controls
appropriate to your environment. Auth identities should be stable internal IDs.

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
