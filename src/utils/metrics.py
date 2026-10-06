import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP Requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP Request Latency", ["method", "endpoint"]
)


class RequsetMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, next_call):
        start_time = time.time()

        response = await next_call(request)

        duration = time.time() - start_time

        # getting the endpoint name
        end_Point = request.url.path

        REQUEST_COUNT.labels(
            method=request.method, endpoint=end_Point, status=response.status_code
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, endpoint=end_Point).observe(
            duration
        )

        return response


def setup_metrics(app: FastAPI):
    app.add_middleware(RequsetMiddleware)

    @app.get("/rag_ishms_metrics_v__0", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
