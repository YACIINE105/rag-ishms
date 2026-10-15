"""Render local evidence and package public results without credentials or models."""

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def render(results):
    screenshots = results / "screenshots"
    screenshots.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1080})
        page.goto((results / "report.html").resolve().as_uri())
        page.screenshot(path=str(screenshots / "report.png"), full_page=True)
        page.pdf(
            path=str(results / "final-project-report.pdf"),
            format="A4",
            print_background=True,
        )
        page.goto((results / "load/load.html").resolve().as_uri())
        page.wait_for_timeout(1500)
        page.screenshot(path=str(screenshots / "locust.png"))
        if os.environ.get("GF_SECURITY_ADMIN_PASSWORD"):
            page.goto("http://127.0.0.1:3000/login")
            page.get_by_placeholder("email or username").fill(
                os.environ.get("GF_SECURITY_ADMIN_USER", "admin")
            )
            page.get_by_placeholder("password", exact=True).fill(
                os.environ["GF_SECURITY_ADMIN_PASSWORD"]
            )
            page.get_by_role("button", name="Log in", exact=True).click()
            page.wait_for_url("http://127.0.0.1:3000/**", wait_until="domcontentloaded")
            page.goto("http://127.0.0.1:3000/d/rag-ishms/rag-ishms?from=now-6h&to=now")
            page.get_by_text("RAG-ISHMS", exact=False).first.wait_for()
            page.wait_for_timeout(8000)
            page.screenshot(path=str(screenshots / "grafana.png"))
        browser.close()


def package(results, destination, secret_file):
    # sqlite backup includes committed WAL contents without stopping MLflow.
    tracking = results / "mlflow.db"
    with sqlite3.connect(ROOT / "reports/mlflow.db") as source:
        with sqlite3.connect(tracking) as backup:
            source.backup(backup)
    fixed = [
        ROOT / "eval/civil_code_full.json",
        ROOT / "eval/civil_code_full.manifest.json",
        ROOT / "eval/corpus/egyptian-civil-code.pdf",
        ROOT / "eval/CIVIL_CODE_EVALUATION.md",
        ROOT / "docs/final-project-report.md",
        ROOT / "docs/plan-review.md",
        ROOT / "scripts/evaluate_rag.py",
        ROOT / "scripts/run_experiments.py",
        ROOT / "scripts/score_captured.py",
        ROOT / "scripts/run_loadtest.py",
        ROOT / "scripts/measure_streaming.py",
        ROOT / "scripts/report_final_project.py",
        ROOT / "scripts/export_final_evidence.py",
        ROOT / "loadtest/locustfile.py",
        ROOT / "loadtest/requirements.txt",
    ]
    files = [
        path
        for path in results.rglob("*")
        if path.is_file()
        and "judge-cache" not in path.parts
        and path.suffix
        in {".json", ".csv", ".png", ".pdf", ".html", ".prom", ".log", ".db"}
        and path.name != "evidence-manifest.json"
    ] + fixed
    # Secret candidates come through a private file; never print their contents.
    secrets = json.loads(secret_file.read_text())
    manifest = {
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "files": {},
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    for path in files:
        data = path.read_bytes()
        if any(value.encode() in data for value in secrets if len(value) >= 8):
            raise ValueError(
                f"Credential match in export input: {path.relative_to(ROOT)}"
            )
        manifest["files"][str(path.relative_to(ROOT))] = hashlib.sha256(
            data
        ).hexdigest()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, str(path.relative_to(ROOT)))
        archive.writestr(
            "evidence-manifest.json", json.dumps(manifest, indent=2) + "\n"
        )
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity failure")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        f"{digest}  {destination.name}\n"
    )
    (results / "evidence-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(f"Verified {len(files)} files: {destination} (SHA-256 {digest})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results", type=Path, default=ROOT / "eval/reports/final-project"
    )
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    if args.render:
        render(args.results)
    if args.archive:
        if not args.secret_file:
            parser.error("--secret-file is required for archive credential scanning")
        package(args.results, args.archive, args.secret_file)


if __name__ == "__main__":
    main()
