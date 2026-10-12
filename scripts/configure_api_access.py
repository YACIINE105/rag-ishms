"""Configure a local service API key without changing database/model settings."""

import json
import secrets
from pathlib import Path

from dotenv import dotenv_values, set_key


def main():
    env_dir = Path(__file__).resolve().parents[1] / "docker/env"
    for name in ("postgres", "postgres-exporter", "grafana", "qdrant"):
        config = env_dir / f".env.{name}"
        if not config.exists():
            config.write_text((env_dir / f".env.example.{name}").read_text())
            config.chmod(0o600)
    target = env_dir / ".env.fastapi"
    if not target.exists():
        target.write_text(target.with_name(".env.example.fastapi").read_text())
    values = dotenv_values(target)
    clients = json.loads(values.get("API_CLIENTS") or "{}")
    if not clients:
        key = secrets.token_urlsafe(32)
        clients = {key: {"user_id": "ishms-service", "projects": ["*"]}}
        set_key(str(target), "API_CLIENTS", json.dumps(clients))
        client_file = target.with_name(".env.client")
        client_file.write_text(f"RAG_API_KEY='{key}'\n")
        client_file.chmod(0o600)
    set_key(str(target), "API_AUTH_ENABLED", "true", quote_mode="never")
    target.chmod(0o600)
    print(
        "API authentication configured. Local client key is in docker/env/.env.client when newly generated."
    )


if __name__ == "__main__":
    main()
