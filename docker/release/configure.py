"""Create private release configuration using only Python's standard library."""

import argparse
import json
import re
import secrets
import shutil
from getpass import getpass
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).parent)
    parser.add_argument("--reviewer", action="store_true")
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ".env"
    for name in (".env", ".env.client", ".env.fastapi"):
        if (directory / name).exists():
            parser.error(f"Configuration already exists; retained {directory / name}")

    reviewer_values = {}
    if args.reviewer:
        key = getpass("OpenRouter API key: ").strip()
        model = input("OpenRouter generation model ID: ").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            parser.error("Enter a valid OpenRouter key")
        if not re.fullmatch(r"[\w./:-]+", model, re.ASCII):
            parser.error("Enter an OpenRouter generation model ID")
        reviewer_values = {
            "OPENROUTER_API_KEYS": json.dumps([key]),
            "GENERATION_BASE_URL": "https://openrouter.ai/api/v1",
            "GENERATION_MODEL_ID": model,
            "GENERATION_MODEL_TEMPERATURE": "0",
            "EMBEDDING_MODEL_ID": "nvidia/nemotron-3-embed-1b:free",
            "RERANKER_ENABLED": "false",
            "MAX_OUTPUT_TOKENS": "256",
        }

    api_key = secrets.token_urlsafe(32)
    clients = {api_key: {"user_id": "ishms-service", "projects": ["*"]}}
    values = {
        "RELEASE_VERSION": Path(__file__).with_name("VERSION").read_text().strip(),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "GENERATOR_API_KEY": secrets.token_urlsafe(32),
        "RERANKER_API_KEY": secrets.token_urlsafe(32),
        "API_CLIENTS": json.dumps(clients, separators=(",", ":")),
    }
    if args.reviewer:
        values["HTTP_PORT"] = "8080"
    with target.open("x") as output:
        target.chmod(0o600)
        for name, value in values.items():
            output.write(f"{name}='{value}'\n")

    api_env = directory / ".env.fastapi"
    if reviewer_values:
        template = Path(__file__).with_name(".env.example.fastapi").read_text()
        settings = [
            line
            for line in template.splitlines()
            if line.partition("=")[0] not in reviewer_values
        ]
        settings.extend(f"{name}={value}" for name, value in reviewer_values.items())
        with api_env.open("x") as output:
            api_env.chmod(0o600)
            output.write("\n".join(settings) + "\n")
    else:
        shutil.copyfile(Path(__file__).with_name(".env.example.fastapi"), api_env)
        api_env.chmod(0o600)
    with (directory / ".env.client").open("x") as output:
        (directory / ".env.client").chmod(0o600)
        output.write(f"RAG_API_KEY='{api_key}'\n")
    print(f"Private configuration created in {directory}")
    if not args.reviewer:
        print("Set OPENROUTER_API_KEYS in .env.fastapi before starting the API.")
    print("The Postman X-API-Key value is saved in .env.client; no key was printed.")


if __name__ == "__main__":
    main()
