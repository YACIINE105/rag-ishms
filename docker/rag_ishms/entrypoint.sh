#!/bin/bash
set -e

echo "Running database migrations..."
cd /app/models/db_schems/rag_ishms/
alembic upgrade head

cd /app

