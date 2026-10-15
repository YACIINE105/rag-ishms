"""Exercise an isolated copy of the existing API using the full Qalam corpus."""

import argparse
import csv
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def wait_job(session, base_url, path, report, timeout=1800):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = session.get(base_url + path, timeout=30)
        response.raise_for_status()
        state = response.json()
        report.write_text(json.dumps(state, indent=2) + "\n")
        if state["state"] in ("succeeded", "failed"):
            if state["state"] == "failed":
                raise RuntimeError("Isolated API job failed; see saved status")
            return state
        time.sleep(2)
    raise TimeoutError("Isolated API job timeout")


def prepare_corpus(session, base_url, args):
    with args.source.open("rb") as document:
        response = session.post(
            f"{base_url}/api/v1/data/upload/{args.project}",
            files={"file": (args.source.name, document, "application/pdf")},
            timeout=60,
        )
    response.raise_for_status()
    upload = response.json()
    (args.reports / "upload.json").write_text(json.dumps(upload, indent=2))
    response = session.post(
        f"{base_url}/api/v1/data/process/jobs/{args.project}",
        json={"file_id": upload["file_id"], "W_qalam": True},
        timeout=30,
    )
    response.raise_for_status()
    job = response.json()
    wait_job(
        session,
        base_url,
        "/api/v1/data/process/status/" + job["job_id"],
        args.reports / "processing.json",
    )
    response = session.post(
        f"{base_url}/api/v1/nlp/index/jobs/{args.project}",
        json={"do_reset": 0},
        timeout=30,
    )
    response.raise_for_status()
    job = response.json()
    wait_job(
        session,
        base_url,
        "/api/v1/nlp/index/status/" + job["job_id"],
        args.reports / "indexing.json",
    )
    response = session.get(
        f"{base_url}/api/v1/nlp/index/info/{args.project}", timeout=30
    )
    response.raise_for_status()
    (args.reports / "index-info.json").write_text(json.dumps(response.json(), indent=2))


def run(args):
    if args.reuse_index and args.vector_backend != "PGVector":
        raise ValueError("Only persistent PGVector evaluation indexes can be reused")
    if args.project < 900100:
        raise ValueError("Use a disposable evaluation project ID >= 900100")
    args.reports.mkdir(parents=True, exist_ok=True)
    settings = {
        key: value
        for key, value in dotenv_values(args.env_file).items()
        if value is not None
    }
    keys = [secrets.token_urlsafe(32) for _ in range(50)]
    clients = {
        key: {"user_id": f"load-user-{index}", "projects": [args.project]}
        for index, key in enumerate(keys)
    }
    settings.update(
        API_AUTH_ENABLED="true",
        API_CLIENTS=json.dumps(clients),
        VECTOR_DB_BACKEND=args.vector_backend,
        QDRANT_URL="",
        QDRANT_API_KEY="",
        RERANKER_ENABLED="true",
        RATE_LIMIT_PER_MINUTE="60",
        RATE_LIMIT_BURST="60",
    )
    with tempfile.TemporaryDirectory(prefix="rag-load-") as directory:
        settings["VECTOR_DB_PATH"] = str(Path(directory) / "vectors")
        # A temporary settings file stays private and is removed with the keys.
        profile = Path(directory) / "profile.env"
        profile.write_text(
            "\n".join(f"{k}={json.dumps(v)}" for k, v in settings.items()) + "\n"
        )
        profile.chmod(0o600)
        key_file = Path(directory) / "keys.json"
        key_file.write_text(json.dumps(keys))
        key_file.chmod(0o600)
        env = {**os.environ, **settings}
        env.pop("QDRANT_URL", None)
        env.pop("QDRANT_API_KEY", None)
        base_url = f"http://127.0.0.1:{args.port}"
        log = (args.reports / "api.log").open("w")
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--app-dir",
                "src",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.port),
                "--no-access-log",
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 180
            while True:
                if server.poll() is not None:
                    raise RuntimeError("Isolated API stopped during startup")
                try:
                    response = requests.get(base_url + "/health", timeout=5)
                    if response.status_code == 200:
                        break
                except requests.RequestException:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError("Isolated API startup timeout")
                time.sleep(2)
            session = requests.Session()
            session.headers["X-API-Key"] = keys[0]
            if args.reuse_index:
                # Resume measurements against this runner's already indexed project.
                # User projects must never be reset for a benchmark retry.
                previous = json.loads(
                    (args.reuse_index / "index-info.json").read_text()
                )
                current = session.get(
                    f"{base_url}/api/v1/nlp/index/info/{args.project}", timeout=30
                )
                current.raise_for_status()
                if current.json() != previous:
                    raise ValueError("Saved and current evaluation indexes differ")
                for name in (
                    "upload.json",
                    "processing.json",
                    "indexing.json",
                    "index-info.json",
                ):
                    (args.reports / name).write_bytes(
                        (args.reuse_index / name).read_bytes()
                    )
            else:
                prepare_corpus(session, base_url, args)
            # Measure SSE without competing requests, then take the load-only baseline.
            subprocess.run(
                [
                    sys.executable,
                    "scripts/measure_streaming.py",
                    "--env-file",
                    str(profile),
                    "--base-url",
                    base_url,
                    "--project",
                    str(args.project),
                    "--report",
                    str(args.reports / "streaming.json"),
                ],
                cwd=ROOT,
                check=True,
            )
            (args.reports / "metrics-before.prom").write_text(
                requests.get(base_url + "/metrics", timeout=30).text
            )
            load_env = {
                **env,
                "LOADTEST_KEYS_FILE": str(key_file),
                "LOADTEST_DATASET": str(ROOT / "eval/civil_code_full.json"),
                "LOADTEST_PROJECT_ID": str(args.project),
            }
            started = time.time()
            gpu_output = (args.reports / "gpu.csv").open("w")
            sampler = subprocess.Popen(
                [
                    "nvidia-smi",
                    "--query-gpu=timestamp,memory.used,memory.total,utilization.gpu,temperature.gpu",
                    "--format=csv,nounits",
                    "--loop=1",
                ],
                stdout=gpu_output,
                stderr=subprocess.DEVNULL,
            )
            with (args.reports / "locust.log").open("w") as output:
                try:
                    result = subprocess.run(
                        [
                            str(args.locust),
                            "-f",
                            "loadtest/locustfile.py",
                            "--host",
                            base_url,
                            "--users",
                            "50",
                            "--spawn-rate",
                            "5",
                            "--run-time",
                            "3m",
                            "--headless",
                            "--stop-timeout",
                            "180",
                            "--csv",
                            str(args.reports / "load"),
                            "--csv-full-history",
                            "--json-file",
                            str(args.reports / "load-final"),
                            "--html",
                            str(args.reports / "load.html"),
                        ],
                        cwd=ROOT,
                        env=load_env,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        timeout=420,
                        check=False,
                    )
                finally:
                    sampler.terminate()
                    sampler.wait(timeout=10)
                    gpu_output.close()
            (args.reports / "metrics-after.prom").write_text(
                requests.get(base_url + "/metrics", timeout=30).text
            )
            with (args.reports / "load_stats_history.csv").open() as history:
                peak_users = max(
                    int(row["User Count"]) for row in csv.DictReader(history)
                )
            metadata = dict(
                users=50,
                observed_peak_users=peak_users,
                spawn_rate=5,
                run_seconds=180,
                drain_timeout_seconds=180,
                actual_wall_seconds=time.time() - started,
                locust_exit_code=result.returncode,
                project_id=args.project,
                base_url=base_url,
                independent_api_keys=50,
                workload_seed=20261015,
                embedding_model=settings["EMBEDDING_MODEL_ID"],
                embedding_endpoint=settings["OPENAI_BASE_URL"],
                generator=settings["GENERATION_MODEL_ID"],
                vector_backend=args.vector_backend,
                profile="Isolated existing FastAPI code; direct NVIDIA embedding route; local Qwen/BGE; no production traffic",
                quality_warning="Sources/nonempty answer checks only; load requests are not legal accuracy labels",
            )
            (args.reports / "metadata.json").write_text(
                json.dumps(metadata, indent=2) + "\n"
            )
        finally:
            server.terminate()
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
            log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--reports", type=Path, default=Path("eval/reports/final-project/load")
    )
    parser.add_argument(
        "--reuse-index",
        type=Path,
        help="Prior successful ingestion report directory (PGVector only)",
    )
    parser.add_argument("--locust", type=Path, required=True)
    parser.add_argument("--project", type=int, default=900102)
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument(
        "--vector-backend", choices=["PGVector", "QDRANT"], default="PGVector"
    )
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
