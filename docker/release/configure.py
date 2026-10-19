"""Create private release configuration using only Python's standard library."""

import argparse
import json
import secrets
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ".env"
    for name in (".env", ".env.client", ".env.fastapi"):
        if (directory / name).exists():
            parser.error(f"Configuration already exists; retained {directory / name}")

    api_key = secrets.token_urlsafe(32)
    clients = {api_key: {"user_id": "ishms-service", "projects": ["*"]}}
    values = {
        "RELEASE_VERSION": "2.0.0",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "GENERATOR_API_KEY": secrets.token_urlsafe(32),
        "RERANKER_API_KEY": secrets.token_urlsafe(32),
        "API_CLIENTS": json.dumps(clients, separators=(",", ":")),
    }
    with target.open("x") as output:
        target.chmod(0o600)
        for name, value in values.items():
            output.write(f"{name}='{value}'\n")

    api_env = directory / ".env.fastapi"
    if not api_env.exists():
        shutil.copyfile(Path(__file__).with_name(".env.example.fastapi"), api_env)
        api_env.chmod(0o600)
    with (directory / ".env.client").open("x") as output:
        (directory / ".env.client").chmod(0o600)
        output.write(f"RAG_API_KEY='{api_key}'\n")
    print(f"Private configuration created in {directory}")
    print("Set OPENROUTER_API_KEYS in .env.fastapi before starting the API.")
    print("The Postman X-API-Key value is saved in .env.client; no key was printed.")


if __name__ == "__main__":
    main()
