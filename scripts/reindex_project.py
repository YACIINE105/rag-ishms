"""Submit non-destructive background processing/indexing through the existing API."""

import argparse
import os
import time
from pathlib import Path

import requests


def wait(session, base_url, status_path, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = session.get(base_url + status_path, timeout=15)
        response.raise_for_status()
        job = response.json()
        if job["state"] == "succeeded":
            return job
        if job["state"] == "failed":
            raise RuntimeError("Background operation failed; inspect job status/logs")
        time.sleep(2)
    raise TimeoutError("Operation still pending; poll the returned job URL")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--qalam", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if args.project_id < 1 or args.timeout < 1:
        parser.error("project-id and timeout must be positive")
    base = args.base_url.rstrip("/")
    with requests.Session() as session:
        if os.environ.get("RAG_API_KEY"):
            session.headers["X-API-Key"] = os.environ["RAG_API_KEY"]
        if args.file:
            mime = (
                "application/pdf"
                if args.file.suffix.lower() == ".pdf"
                else "text/plain"
            )
            with args.file.open("rb") as file:
                upload = session.post(
                    f"{base}/api/v1/data/upload/{args.project_id}",
                    files={"file": (args.file.name, file, mime)},
                    timeout=60,
                )
                upload.raise_for_status()
        for route, payload, status_route in [
            (
                "data/process/jobs",
                {"W_qalam": args.qalam, "do_reset": 0},
                "data/process/status",
            ),
            ("nlp/index/jobs", {"do_reset": 0}, "nlp/index/status"),
        ]:
            response = session.post(
                f"{base}/api/v1/{route}/{args.project_id}", json=payload, timeout=15
            )
            response.raise_for_status()
            job_id = response.json()["job_id"]
            status_path = f"/api/v1/{status_route}/{job_id}"
            print(f"Submitted: {base}{status_path}", flush=True)
            wait(session, base, status_path, args.timeout)
    print("Project processing and indexing completed")


if __name__ == "__main__":
    main()
