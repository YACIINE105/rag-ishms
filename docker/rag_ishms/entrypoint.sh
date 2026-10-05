#!/bin/sh
set -eu
cd /app/models/db_schems/rag_ishms
alembic upgrade head
cd /app
exec "$@"
