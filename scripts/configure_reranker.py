"""Create a private vLLM reranker key and configure the existing Docker API."""

import argparse
import secrets
from pathlib import Path

from dotenv import dotenv_values, set_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://host.docker.internal:8002/v1")
    args = parser.parse_args()
    env_dir = Path(__file__).resolve().parents[1] / "docker/env"
    target = env_dir / ".env.fastapi"
    if not target.exists():
        parser.error("Run configure_api_access.py before configuring the reranker")
    service_env = env_dir / ".env.reranker"
    key = (
        dotenv_values(service_env).get("VLLM_API_KEY") if service_env.exists() else None
    )
    if not key:
        key = secrets.token_urlsafe(32)
        set_key(str(service_env), "VLLM_API_KEY", key)
    service_env.chmod(0o600)
    for name, value in {
        "RERANKER_ENABLED": "true",
        "RERANKER_BASE_URL": args.base_url,
        "RERANKER_API_KEY": key,
        "RERANKER_MODEL_ID": "BAAI/bge-reranker-v2-m3",
        "RERANKER_MAX_LENGTH": "512",
    }.items():
        set_key(str(target), name, value)
    target.chmod(0o600)
    print("GPU reranker connection configured; keys remain in ignored local files.")


if __name__ == "__main__":
    main()
