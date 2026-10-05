FROM python:3.12-slim-bookworm AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake gcc pkg-config libpq-dev libavif-dev libjpeg-dev \
    libxml2-dev libxslt1-dev libffi-dev libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY src/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libpq5 libavif15 libjpeg62-turbo libxml2 libxslt1.1 libffi8 libgomp1 libopenblas0 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 10001 appuser \
    && adduser --system --uid 10001 --ingroup appuser --home /home/appuser appuser
WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/.hf_cache HF_HUB_OFFLINE=1
COPY --from=builder /opt/venv /opt/venv
# Only the whitelisted Hugging Face hub cache is included in the build context.
COPY --chown=appuser:appuser hf_cache/ /app/.hf_cache/
COPY --chown=appuser:appuser src/ /app/
COPY --chown=appuser:appuser docker/rag_ishms/alembic.example.ini /app/models/db_schems/rag_ishms/alembic.ini
COPY --chmod=755 docker/rag_ishms/entrypoint.sh /entrypoint.sh
RUN mkdir -p /app/assets /app/ai-models /app/.hf_cache /home/appuser \
    && chown -R appuser:appuser /app/assets /app/ai-models /app/.hf_cache /home/appuser
USER appuser
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD curl --fail --silent http://localhost:8000/health || exit 1
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
