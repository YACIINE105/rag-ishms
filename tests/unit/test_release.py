import hashlib
import json
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
        assert "rag-ishms:2.0.1" in compose
        assert "rag-ishms-vllm:2.0.1" in compose
        assert manifest["models"]["generator"]["fine_tuned"] is False
    assert (
        hashlib.sha256(target.read_bytes()).hexdigest()
        in (tmp_path / "SHA256SUMS").read_text()
    )
