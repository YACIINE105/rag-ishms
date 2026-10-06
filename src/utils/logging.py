"""JSON application logs with request context and sampled HTTP access events."""

import logging
import random
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from pythonjsonlogger.json import JsonFormatter
from starlette.responses import JSONResponse

request_id_context = ContextVar("request_id", default=None)
project_id_context = ContextVar("project_id", default=None)


class ContextJsonFormatter(JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record.update(
            timestamp=datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            request_id=request_id_context.get(),
            project_id=project_id_context.get(),
        )


def configure_logging(level="INFO"):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ContextJsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Prediction audit events remain enabled even with a quieter root log level.
    logging.getLogger("rag.prediction").setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    # The middleware owns access events so they have context and one sampling policy.
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware:
    def __init__(self, app, access_sample_rate=0.1):
        self.app = app
        self.access_sample_rate = max(0.0, min(1.0, access_sample_rate))
        self.logger = logging.getLogger("http.access")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        incoming = headers.get(b"x-request-id", b"").decode("latin1")
        request_id = (
            incoming
            if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", incoming)
            else str(uuid4())
        )
        match = re.search(
            r"/(?:index/(?:push|info|search|answer)|upload|process)/(\d+)/?$",
            scope["path"],
        )
        project_id = int(match.group(1)) if match else None
        request_token = request_id_context.set(request_id)
        project_token = project_id_context.set(project_id)
        scope.setdefault("state", {})["request_id"] = request_id
        started = False
        status_code = 500
        start = perf_counter()

        async def send_with_id(message):
            nonlocal started, status_code
            if message["type"] == "http.response.start":
                started = True
                status_code = message["status"]
                message["headers"] = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != b"x-request-id"
                ]
                message["headers"].append((b"x-request-id", request_id.encode("ascii")))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            self.logger.exception("request.failed")
            if started:
                raise
            await JSONResponse({"detail": "Internal server error"}, status_code=500)(
                scope, receive, send_with_id
            )
        finally:
            if status_code >= 400 or random.random() < self.access_sample_rate:
                self.logger.log(
                    logging.ERROR if status_code >= 500 else logging.INFO,
                    "http.done",
                    extra={
                        "method": scope["method"],
                        "path": scope["path"],
                        "status_code": status_code,
                        "latency_ms": round((perf_counter() - start) * 1000, 2),
                    },
                )
            project_id_context.reset(project_token)
            request_id_context.reset(request_token)
