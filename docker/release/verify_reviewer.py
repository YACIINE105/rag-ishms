"""Verify upload, processing, indexing and cited generation for the reviewer stack."""

import json
import secrets
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures/reviewer_provision.txt"
QUESTION = "Under Article 7 of the North Harbor Charter, how long is a permit valid?"


def setting(path, key):
    for line in (ROOT / path).read_text().splitlines():
        name, _, value = line.partition("=")
        if name == key:
            return value.strip().strip("'\"")
    raise ValueError(f"Missing {key} in {path}")


def verify(call):
    project = 1_000_000_000 + secrets.randbelow(1_000_000_000)
    fixture = FIXTURE.read_bytes()
    boundary = uuid4().hex
    upload = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{FIXTURE.name}"\r\nContent-Type: text/plain\r\n\r\n'.encode()
        + fixture
        + f"\r\n--{boundary}--\r\n".encode()
    )
    file_id = call(
        "upload",
        f"/data/upload/{project}",
        upload,
        f"multipart/form-data; boundary={boundary}",
    ).get("file_id")
    if not file_id:
        raise ValueError("upload: missing asset ID")

    def job(stage, route, payload, count_field):
        job_id = call(stage, f"{route}/jobs/{project}", payload).get("job_id")
        if not job_id:
            raise ValueError(f"{stage}: missing job ID")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            status = call(stage, f"{route}/status/{job_id}")
            if status.get("state") == "succeeded":
                if status.get("result", {}).get(count_field, 0) <= 0:
                    raise ValueError(f"{stage}: no chunks produced")
                return
            if status.get("state") == "failed":
                raise ValueError(
                    f"{stage}: job failed; check service logs and provider quota"
                )
            time.sleep(1)
        raise ValueError(f"{stage}: job exceeded 120 seconds")

    job(
        "process",
        "/data/process",
        {
            "file_id": file_id,
            "W_qalam": False,
            "do_emantic_chunk": 0,
            "chunk_size": 512,
            "overlap_size": 0,
        },
        "inserted_chunks",
    )
    job("index", "/nlp/index", {"do_reset": 0}, "inserted_items_count")
    result = call(
        "answer", f"/nlp/index/answer/{project}", {"text": QUESTION, "limit": 1}
    )
    answer = result.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("answer: empty text; check model access and quota")
    if not any(
        str(source.get("asset_name", "")).endswith(FIXTURE.name)
        for source in result.get("sources", [])
    ):
        raise ValueError("answer: missing fixture citation")
    return project


def main():
    try:
        key = setting(".env.client", "RAG_API_KEY")
        port = int(setting(".env", "HTTP_PORT"))

        def call(stage, path, data=None, content_type="application/json"):
            if isinstance(data, dict):
                data = json.dumps(data).encode()
            request = Request(
                f"http://127.0.0.1:{port}/api/v1{path}",
                data=data,
                headers={"X-API-Key": key, "Content-Type": content_type},
            )
            try:
                with urlopen(request, timeout=55) as response:
                    content = json.load(response)
                    if not isinstance(content, dict):
                        raise ValueError
                    return content
            except HTTPError as error:
                raise ValueError(f"{stage}: HTTP {error.code}") from None
            except (OSError, ValueError) as error:
                raise ValueError(f"{stage}: {type(error).__name__}") from None

        project = verify(call)
    except (OSError, ValueError) as error:
        print(f"Reviewer verification failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Reviewer project {project}: upload, processing, indexing, cited answer passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
