from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from routes import data, nlp
from utils import security
from utils.jobs import IndexJobs

KEY = "test-key-with-at-least-24-characters"
OTHER = "another-key-with-at-least-24-characters"


def test_auth_project_access_and_rate_limits(monkeypatch):
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            API_AUTH_ENABLED=True,
            API_CLIENTS={
                KEY: {"user_id": "alice", "projects": [1]},
                OTHER: {"user_id": "bob", "projects": [2]},
            },
            RATE_LIMIT_BURST=1,
            RATE_LIMIT_PER_MINUTE=1,
        ),
    )
    app = FastAPI()
    app.include_router(nlp.nlp_router)
    app.state.index_jobs = IndexJobs()
    job = app.state.index_jobs.submit(2)

    @app.post("/test/{project_id}", dependencies=[Depends(security.authorize)])
    async def protected(project_id: int):
        return {"project": project_id}

    with TestClient(app) as client:
        assert client.post("/test/1").status_code == 401
        assert client.post("/test/2", headers={"X-API-Key": KEY}).status_code == 403
        assert (
            client.get(
                f"/api/v1/nlp/index/status/{job['job_id']}", headers={"X-API-Key": KEY}
            ).status_code
            == 403
        )
        assert (
            client.get(
                f"/api/v1/nlp/index/status/{job['job_id']}",
                headers={"X-API-Key": OTHER},
            ).status_code
            == 200
        )
        assert client.post("/test/1", headers={"X-API-Key": KEY}).status_code == 200
        limited = client.post("/test/1", headers={"X-API-Key": KEY})
        assert limited.status_code == 429 and int(limited.headers["Retry-After"]) > 0


def test_active_index_job_blocks_upload_process_and_sync_index():
    app = FastAPI()
    app.include_router(nlp.nlp_router)
    app.include_router(data.data_router)
    app.state.index_jobs = IndexJobs()
    app.state.index_jobs.submit(1)
    with TestClient(app) as client:
        assert client.post("/api/v1/nlp/index/push/1", json={}).status_code == 409
        assert client.post("/api/v1/data/process/1", json={}).status_code == 409
        assert (
            client.post(
                "/api/v1/data/upload/1",
                files={"file": ("x.txt", b"example", "text/plain")},
            ).status_code
            == 409
        )
        assert client.post("/api/v1/nlp/index/jobs/1", json={}).status_code == 409


def test_background_process_and_status(monkeypatch):
    app = FastAPI()
    app.include_router(data.data_router)
    processor = AsyncMock(
        return_value=JSONResponse({"signal": "success", "processed_files": 1})
    )
    monkeypatch.setattr(data, "process_endpoint", processor)
    with TestClient(app) as client:
        response = client.post("/api/v1/data/process/jobs/1", json={})
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        job = client.get(f"/api/v1/data/process/status/{job_id}").json()
        assert job["state"] == "succeeded" and job["result"]["processed_files"] == 1
        assert client.get("/api/v1/data/process/status/missing").status_code == 404
