import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]


def test_release_setup_creates_private_separate_keys_and_preserves_existing_config(
    tmp_path,
):
    command = [
        sys.executable,
        str(ROOT / "docker/release/configure.py"),
        "--directory",
        str(tmp_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    from dotenv import dotenv_values

    values = dotenv_values(tmp_path / ".env")
    clients = json.loads(values["API_CLIENTS"])
    api_key = next(iter(clients))
    assert (
        len(
            {
                api_key,
                values["GENERATOR_API_KEY"],
                values["RERANKER_API_KEY"],
                values["POSTGRES_PASSWORD"],
            }
        )
        == 4
    )
    assert dotenv_values(tmp_path / ".env.client")["RAG_API_KEY"] == api_key
    for name in (".env", ".env.fastapi", ".env.client"):
        assert (tmp_path / name).stat().st_mode & 0o777 == 0o600
    assert api_key not in result.stdout
    from helpers.config import Settings

    settings = Settings(
        _env_file=tmp_path / ".env.fastapi",
        POSTGRES_HOST="pgvector",
        POSTGRES_PASSWORD=values["POSTGRES_PASSWORD"],
        GENERATION_MODEL_ID="qwen3-legal-final",
        GENERATION_MODEL_TEMPERATURE=0,
        MAX_OUTPUT_TOKENS=256,
        API_AUTH_ENABLED=True,
        API_CLIENTS=clients,
    )
    assert settings.EMBEDDING_MODEL_SIZE == 2048
    assert settings.GENERATION_MODEL_ID == "qwen3-legal-final"
    before = (tmp_path / ".env").read_bytes()
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0
    assert (tmp_path / ".env").read_bytes() == before


def test_release_archive_hashes_match_payload_without_private_runtime_files(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_release_bundle.py"),
            "--version",
            "2.0.1",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    target = tmp_path / "rag-ishms-2.0.1-docker.zip"
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        for name, checksum in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == checksum
        assert all(
            not Path(name).name.startswith(".env")
            or Path(name).name.startswith(".env.example")
            for name in archive.namelist()
        )
        compose = archive.read("docker/release/compose.yml").decode()
        for name in (
            "compose.reviewer.yml",
            "verify_reviewer.py",
            "fixtures/reviewer_provision.txt",
        ):
            assert f"docker/release/{name}" in manifest["files"]
        assert "rag-ishms:${RELEASE_VERSION:" in compose
        assert "rag-ishms-vllm:${RELEASE_VERSION:" in compose
        assert archive.read("docker/release/VERSION").decode().strip() == "2.0.1"
        assert manifest["models"]["generator"]["fine_tuned"] is False
    assert (
        hashlib.sha256(target.read_bytes()).hexdigest()
        in (tmp_path / "SHA256SUMS").read_text()
    )


def test_reviewer_config_enables_hosted_models_and_retains_private_key(
    tmp_path, monkeypatch, capsys
):
    from dotenv import dotenv_values

    from helpers.config import Settings

    key = "test-reviewer-only-key"
    monkeypatch.setattr("getpass.getpass", lambda _: key)
    monkeypatch.setattr("builtins.input", lambda _: "openrouter/free")
    monkeypatch.setattr(
        sys, "argv", ["configure.py", "--reviewer", "--directory", str(tmp_path)]
    )
    runpy.run_path(str(ROOT / "docker/release/configure.py"), run_name="__main__")
    values = dotenv_values(tmp_path / ".env.fastapi")
    assert json.loads(values["OPENROUTER_API_KEYS"]) == [key]
    assert values["GENERATION_MODEL_ID"] == "openrouter/free"
    assert values["EMBEDDING_MODEL_ID"] == "nvidia/nemotron-3-embed-1b:free"
    assert values["EMBEDDING_MODEL_SIZE"] == "2048"
    assert values["RERANKER_ENABLED"] == "false"
    assert key not in capsys.readouterr().out
    assert (tmp_path / ".env.fastapi").stat().st_mode & 0o777 == 0o600
    compose_settings = dotenv_values(tmp_path / ".env")
    settings = Settings(
        _env_file=tmp_path / ".env.fastapi",
        POSTGRES_HOST="pgvector",
        POSTGRES_PASSWORD=compose_settings["POSTGRES_PASSWORD"],
        API_AUTH_ENABLED=True,
        API_CLIENTS=json.loads(compose_settings["API_CLIENTS"]),
    )
    assert settings.GENERATION_MODEL_TEMPERATURE == 0
    assert settings.GENERATION_MODEL_ID == "openrouter/free"
    assert settings.RERANKER_ENABLED is False
