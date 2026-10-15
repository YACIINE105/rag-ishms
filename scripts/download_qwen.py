"""Download and hash-check the selected public Qwen revision using the vLLM env."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path.home() / "vllm-env/models/Qwen3-4B-Instruct-2507",
    )
    args = parser.parse_args()
    target = args.model_dir.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_XET_CACHE", str(target.parent / ".hf-xet-cache"))
    info = HfApi().model_info(
        MODEL_ID, revision=MODEL_REVISION, files_metadata=True, token=False
    )
    files = [file for file in info.siblings if file.rfilename != ".gitattributes"]
    print(f"Downloading pinned model to {target}", flush=True)
    snapshot_download(
        MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=target,
        allow_patterns=[file.rfilename for file in files],
        max_workers=3,
        token=False,
    )
    verified_files = []
    for file in files:
        path = target / file.rfilename
        if not path.is_file() or path.stat().st_size != file.size:
            raise ValueError(f"Missing or incorrect file size: {file.rfilename}")
        with path.open("rb") as source:
            checksum = hashlib.file_digest(source, "sha256").hexdigest()
        if file.lfs and checksum != file.lfs.sha256:
            raise ValueError(f"SHA-256 mismatch: {file.rfilename}")
        if not file.lfs:
            git_checksum = hashlib.sha1(f"blob {file.size}\0".encode())
            git_checksum.update(path.read_bytes())
            if git_checksum.hexdigest() != file.blob_id:
                raise ValueError(f"Git blob checksum mismatch: {file.rfilename}")
        verified_files.append(
            {
                "name": file.rfilename,
                "size": file.size,
                "sha256": checksum,
            }
        )
        print(f"Verified {file.rfilename}", flush=True)
    manifest = {
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "download_complete": True,
        "lfs_sha256_verified": True,
        "files": verified_files,
    }
    temporary = target / "rag-ishms-model.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(target / "rag-ishms-model.json")
    print("Pinned Qwen model downloaded and verified.")


if __name__ == "__main__":
    main()
