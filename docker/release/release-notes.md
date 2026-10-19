The complete RAG pipeline is available as a Docker Compose deployment: CUDA API,
4-bit Qwen generation, GPU BGE reranking, PostgreSQL/pgvector and nginx.

Download the deployment ZIP, verify `SHA256SUMS`, open `docker/release`, and follow
its README. Run `python3 configure.py`, add your embedding key to `.env.fastapi`,
then `docker compose pull` and `docker compose up -d --no-build`.

Images:

- `ghcr.io/yaciine105/rag-ishms:2.0.1`
- `ghcr.io/yaciine105/rag-ishms-vllm:2.0.1`

The archive manifest records the exact published image digests. GHCR packages
may require owner-configured public visibility or `read:packages` authentication.

Both images contain the original Hugging Face download link and pinned model
identity. Weights download into a persistent volume on first startup. The selected
generator is the unchanged Qwen3-4B-Instruct-2507 base; no fine-tuned pilot adapter
is presented as a new trained release. See `models.json` for both source revisions.

The release retains Qalam PDF processing, background indexing, API authentication,
provider-key quota fallback, cited normal/SSE answers, Langfuse tracing and simple
per-stage millisecond logs. It contains no private keys, uploaded documents or
database snapshots. The existing host/systemd deployment remains supported.

NVIDIA GPU access is required; embedding service credentials and quota are still
required. Initial model downloads and CUDA warmup take time. Small functional
checks and internal legal evaluations do not establish legal correctness or
production concurrency capacity. Back up existing data before migrating it into
this deployment's separate volumes.
