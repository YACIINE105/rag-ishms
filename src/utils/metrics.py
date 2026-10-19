import time

from fastapi import FastAPI, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP Requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP Request Latency", ["method", "endpoint"]
)


class RequsetMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = time.perf_counter()
        status = 500

        async def observed_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, observed_send)
        finally:
            endpoint = getattr(scope.get("route"), "path", "unmatched")
            method = (
                scope["method"]
                if scope["method"]
                in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
                else "OTHER"
            )
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(
                time.perf_counter() - started
            )


def setup_metrics(app: FastAPI):
    app.add_middleware(RequsetMiddleware)

    @app.get("/metrics", include_in_schema=False)
    @app.get("/rag_ishms_metrics_v__0", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


RAG_STAGE_LATENCY = Histogram(
    "rag_stage_latency_seconds",
    "Pipeline stage latency",
    ["stage"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 180, 300, 600),
)
RAG_REQUESTS = Counter("rag_answers_total", "Answer outcomes", ["outcome", "lang"])
RAG_RETRIEVED = Histogram(
    "rag_retrieved_chunks",
    "Retrieved candidate count",
    buckets=(0, 1, 2, 3, 5, 10, 30, 50),
)
RAG_TOP_SCORE = Histogram(
    "rag_rerank_top1_score", "Top reranker score", buckets=(-10, -5, -1, 0, 1, 5, 10)
)
LLM_TOKENS = Counter("llm_tokens_total", "Actual provider token usage", ["type"])
GUARDRAIL_DECISIONS = Counter(
    "guardrail_decisions_total", "Guardrail outcomes", ["guardrail", "decision"]
)
LLM_TTFT = Histogram("llm_time_to_first_token_seconds", "Streaming time to first token")
LLM_STREAM_DURATION = Histogram(
    "llm_stream_duration_seconds", "Streaming generation duration"
)
LLM_INFLIGHT = Gauge("llm_inflight_requests", "Active generation calls")
