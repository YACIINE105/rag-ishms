"""Bounded single-worker jobs with atomic status snapshots in the assets volume."""

import asyncio
import json
import logging
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, Request


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class IndexJobs:
    def __init__(self, path=None):
        self.records = OrderedDict()
        self.lock = asyncio.Lock()
        self.mutating = set()
        self.path = Path(path) if path else None
        if self.path and self.path.exists():
            self.records.update(json.loads(self.path.read_text()))
            for job in self.records.values():
                if job["state"] in {"queued", "running"}:
                    job.update(
                        state="failed",
                        error="server_restarted",
                        finished_at=timestamp(),
                    )
            self.save()

    def save(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.records), encoding="utf-8")
            temporary.chmod(0o600)
            temporary.replace(self.path)

    def busy(self, project_id):
        return project_id in self.mutating or any(
            j["state"] in {"queued", "running"} and j["project_id"] == project_id
            for j in self.records.values()
        )

    @contextmanager
    def mutation(self, project_id):
        if self.busy(project_id):
            raise HTTPException(
                409, "Project has an active processing/indexing operation"
            )
        self.mutating.add(project_id)
        try:
            yield
        finally:
            self.mutating.remove(project_id)

    def submit(self, project_id, kind="index"):
        if self.busy(project_id):
            raise ValueError("This project already has an active operation")
        active = sum(j["state"] in {"queued", "running"} for j in self.records.values())
        if active >= 8:
            raise ValueError("Job queue is full")
        while len(self.records) >= 100:
            completed = next(
                (
                    k
                    for k, v in self.records.items()
                    if v["state"] in {"succeeded", "failed"}
                ),
                None,
            )
            if completed is None:
                raise ValueError("Job queue is full")
            del self.records[completed]
        job_id = str(uuid4())
        self.records[job_id] = {
            "job_id": job_id,
            "project_id": project_id,
            "kind": kind,
            "state": "queued",
            "created_at": timestamp(),
        }
        self.save()
        return self.records[job_id]

    async def run(self, job_id, function, *args):
        async with self.lock:
            job = self.records[job_id]
            job.update(state="running", started_at=timestamp())
            self.save()
            try:
                response = await function(*args)
                body = json.loads(getattr(response, "body", b"{}"))
                job["state"] = "succeeded" if response.status_code < 400 else "failed"
                # Store counts/signals, never file contents, provider errors or credentials.
                job["result"] = {
                    key: value
                    for key, value in body.items()
                    if key
                    in {
                        "signal",
                        "inserted_items_count",
                        "inserted_chunks",
                        "processed_files",
                        "processing_mode",
                    }
                }
            except asyncio.CancelledError:
                job.update(state="failed", error="job_cancelled")
                raise
            except Exception:
                logging.getLogger(__name__).exception("job.failed")
                job.update(state="failed", error="operation_failed")
            finally:
                job["finished_at"] = timestamp()
                self.save()


def get_jobs(app):
    if not hasattr(app.state, "index_jobs"):
        app.state.index_jobs = IndexJobs()
    return app.state.index_jobs


async def reserve_project(request: Request, project_id: int):
    with get_jobs(request.app).mutation(project_id):
        yield
