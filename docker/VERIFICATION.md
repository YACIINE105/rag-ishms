# Docker verification — 2026-10-06

Verified locally with Docker Desktop 29.8.1 and the native Ubuntu-24.04 WSL client.
The production Dockerfile built successfully with Python 3.12 and CPU PyTorch
2.14.1. No ONNX conversion or dependency was introduced.

## Results

- Image build succeeded, including native llama-cpp-python and psycopg2 wheels.
- Runtime UID is 10001; gcc, g++, and cc are absent.
- Assets and Hugging Face cache are writable; the model bind mount is read-only.
- Native imports succeeded and `pip check` found no broken requirements.
- The real cached BAAI reranker loaded offline on CPU.
- Both Alembic migrations ran successfully against a temporary PostgreSQL database.
- `/health` returned 200 with every dependency reporting `ok`, using PGVector
  and then a separate Qdrant server. Model readiness probes reached the configured
  OpenAI-compatible service without text generation.
- Nginx started after the application became healthy. API smoke checks passed
  directly and through nginx for both vector backends.
- POST routes, exact answer schema fields, blank/invalid input returning 422,
  and returned `X-Request-ID` headers passed live checks.
- Pausing the temporary PostgreSQL container exposed a cancellation-timeout bug.
  After the fix, readiness returned 503 during the outage and recovered after
  database connections finished recovering. Unit coverage includes delayed driver
  cancellation so the response deadline is independent of cleanup completion.
- Application/migration logs parsed as JSON with the six required fields and
  correlated request/project IDs.
- Full pytest suite: **114 passed**, 12 subtests passed, **83.15% source coverage**.
- Default and Qdrant Compose configurations and `git diff --check` passed.

## Scope

Verification used the final image with isolated temporary PostgreSQL/Qdrant
containers and a separate assets volume. Existing application database volumes
were not migrated or modified. Tests did not upload documents or generate answers;
answer quality and every remote model's inference capability are outside these
Docker checks. Temporary verification resources were removed afterward.

The local, untracked Docker environment file also needed its database hostname,
HF cache path, and a missing newline corrected. No credentials were committed.

Run `python docker/smoke_test.py --base-url http://localhost:8000` to repeat HTTP
readiness and API contract checks against a running deployment.
