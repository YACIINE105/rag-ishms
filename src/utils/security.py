"""Static API-key identities, project permissions and a single-worker token bucket."""

import hashlib
import math
import secrets
from collections import OrderedDict
from contextvars import ContextVar
from time import monotonic

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from helpers.config import get_settings
from utils.metrics import GUARDRAIL_DECISIONS

identity_context = ContextVar("identity", default=None)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class TokenBuckets:
    def __init__(self, capacity=60, per_minute=60, max_keys=1024, clock=monotonic):
        self.capacity = capacity
        self.rate = per_minute / 60
        self.max_keys = max_keys
        self.clock = clock
        self.buckets = OrderedDict()

    def take(self, key):
        now = self.clock()
        tokens, updated = self.buckets.pop(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + max(0, now - updated) * self.rate)
        wait = max(1, math.ceil((1 - tokens) / self.rate)) if tokens < 1 else 0
        self.buckets[key] = (tokens if wait else tokens - 1, now)
        while len(self.buckets) > self.max_keys:
            self.buckets.popitem(last=False)
        return wait


def project_allowed(identity, project_id):
    projects = identity["projects"]
    return projects == ["*"] or project_id in projects


async def authorize(request: Request, api_key: str | None = Security(api_key_header)):
    settings = get_settings()
    enabled = getattr(settings, "API_AUTH_ENABLED", False)
    identity = {"user_id": "local-demo", "projects": ["*"]}
    if enabled:
        clients = getattr(settings, "API_CLIENTS", {})
        identity = next(
            (
                client
                for key, client in clients.items()
                if api_key and secrets.compare_digest(key.encode(), api_key.encode())
            ),
            None,
        )
        if identity is None:
            GUARDRAIL_DECISIONS.labels("auth", "denied").inc()
            raise HTTPException(401, "Invalid or missing API key")
    project_id = request.path_params.get("project_id")
    if project_id is None and "job_id" in request.path_params:
        jobs = getattr(request.app.state, "index_jobs", None)
        record = jobs.records.get(request.path_params["job_id"]) if jobs else None
        if record:
            project_id = record["project_id"]
    if project_id is not None:
        try:
            project_id = int(project_id)
        except (ValueError, TypeError):
            raise HTTPException(422, "Project ID must be a positive integer") from None
        if project_id < 1:
            raise HTTPException(422, "Project ID must be a positive integer")
    if project_id is not None and not project_allowed(identity, project_id):
        GUARDRAIL_DECISIONS.labels("project_acl", "denied").inc()
        raise HTTPException(403, "Project access denied")
    request.state.identity = identity
    if enabled and request.method == "POST":
        if not hasattr(request.app.state, "rate_limits"):
            request.app.state.rate_limits = TokenBuckets(
                capacity=getattr(settings, "RATE_LIMIT_BURST", 60),
                per_minute=getattr(settings, "RATE_LIMIT_PER_MINUTE", 60),
            )
        # Identity comes from server configuration; no untrusted forwarding headers.
        key = hashlib.sha256(api_key.encode()).hexdigest()
        retry_after = request.app.state.rate_limits.take(key)
        if retry_after:
            GUARDRAIL_DECISIONS.labels("rate_limit", "denied").inc()
            raise HTTPException(
                429, "Rate limit exceeded", headers={"Retry-After": str(retry_after)}
            )
    token = identity_context.set(identity["user_id"])
    try:
        yield identity
    finally:
        identity_context.reset(token)
