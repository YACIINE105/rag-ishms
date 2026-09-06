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

COPY src/ .

RUN mkdir -p /app/models/db_schems/rag_ishms

COPY docker/rag_ishms/alembic.ini /app/models/db_schems/rag_ishms/alembic.ini

COPY docker/rag_ishms/entrypoint.sh /entrypoint.sh


RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]


CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "workers", "5"]
