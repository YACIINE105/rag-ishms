FROM ghcr.io/astral-sh/uv:0.12-python3.12-trixie

WORKDIR /app

# install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libavif-dev pkg-config \
    libjpeg-dev \
    gcc unzip zip \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY src/requirements.txt .

RUN uv pip install --no-cache-dir -r requirements.txt --system

# Copy the pre-downloaded HF cache from the WSL host into the image,
# so models are baked in and never re-downloaded at container startup.
# Placed BEFORE the volatile src/ copy below so this large layer stays
# cached across rebuilds instead of being re-created every time src/ changes.
ENV HF_HOME=/app/.hf_cache
COPY hf_cache/ /app/.hf_cache/
ENV HF_HUB_OFFLINE=1

COPY src/ .

RUN mkdir -p /app/models/db_schems/rag_ishms

COPY docker/rag_ishms/alembic.ini /app/models/db_schems/rag_ishms/alembic.ini

COPY docker/rag_ishms/entrypoint.sh /entrypoint.sh


RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]


CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "workers", "5"]