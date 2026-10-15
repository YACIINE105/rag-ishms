"""Configure the selected Qwen base in the separate vLLM environment."""

import argparse
import json
import secrets
import shutil
from pathlib import Path

from dotenv import dotenv_values, set_key

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
SERVED_MODEL_NAME = "qwen3-legal-final"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://host.docker.internal:8001/v1")
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path.home() / "vllm-env/models/Qwen3-4B-Instruct-2507",
    )
    args = parser.parse_args()
    manifest_path = args.model_path / "rag-ishms-model.json"
    if not manifest_path.is_file():
        parser.error("Download and verify the pinned model before configuring Qwen")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest.get("model_id") != MODEL_ID
        or manifest.get("revision") != MODEL_REVISION
        or not manifest.get("download_complete")
        or not manifest.get("lfs_sha256_verified")
    ):
        parser.error("The local model manifest does not match the verified release")

    env_dir = Path(__file__).resolve().parents[1] / "docker/env"
    target = env_dir / ".env.fastapi"
    if not target.exists():
        parser.error("Run configure_api_access.py before configuring Qwen")
    backup = env_dir / ".env.fastapi.before-qwen"
    if not backup.exists():
        with backup.open("xb") as output:
            backup.chmod(0o600)
            with target.open("rb") as source:
                shutil.copyfileobj(source, output)

    service_env = env_dir / ".env.generator"
    if not service_env.exists():
        service_env.touch(mode=0o600)
    service_env.chmod(0o600)
    key = dotenv_values(service_env).get("VLLM_API_KEY")
    if not key:
        key = secrets.token_urlsafe(32)
    for name, value in {
        "VLLM_API_KEY": key,
        "GENERATOR_MODEL_PATH": str(args.model_path.absolute()),
        "GENERATOR_SERVED_MODEL_NAME": SERVED_MODEL_NAME,
    }.items():
        set_key(str(service_env), name, value)

    for name, value in {
        "GENERATION_PROVIDER": "OPENAI",
        "GENERATION_BASE_URL": args.base_url,
        "GENERATION_API_KEY": key,
        "GENERATION_MODEL_ID": SERVED_MODEL_NAME,
        "GENERATION_MODEL_TEMPERATURE": "0",
        "MAX_OUTPUT_TOKENS": "256",
    }.items():
        set_key(str(target), name, value)
    target.chmod(0o600)
    print(
        "Qwen generation configured; embedding, database and client settings preserved."
    )
    print("Private rollback copy: docker/env/.env.fastapi.before-qwen")


if __name__ == "__main__":
    main()
