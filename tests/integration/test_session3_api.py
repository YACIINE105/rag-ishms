from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import nlp
from utils.jobs import IndexJobs


def test_sse_contract_and_job_status(monkeypatch):
    app = FastAPI()
    app.include_router(nlp.nlp_router)
    app.generation_client = SimpleNamespace(stream_text=lambda: None)
    app.embedding_client = app.vector_db_client = app.reranker_client = (
        app.template_parser
    ) = None
    app.db_client = None
    project_model = SimpleNamespace(
        get_project_or_create_one=AsyncMock(return_value=SimpleNamespace(project_id=1))
    )
    monkeypatch.setattr(
        nlp.ProjectModel, "create_instance", AsyncMock(return_value=project_model)
    )
    controller = SimpleNamespace(
        answer_rag_query=AsyncMock(
            return_value={
                "stream": iter(["hello", " world"]),
                "sources": [{"asset_name": "test.pdf", "page": 1}],
                "prompt_version": "rag-v1",
            }
        )
    )
    monkeypatch.setattr(nlp, "NLPController", lambda **kwargs: controller)
    # A generator, rather than a list iterator, supports cleanup on disconnect.
    controller.answer_rag_query.return_value["stream"] = (
        text for text in ["hello", " world"]
    )
    app.state.index_jobs = IndexJobs()
    job = app.state.index_jobs.submit(1)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/nlp/index/answer/stream/1", json={"text": "question"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: sources" in response.text
        assert response.text.count("event: token") == 2
        assert "event: done" in response.text
        assert "event: error" not in response.text
        assert (
            client.get(f"/api/v1/nlp/index/status/{job['job_id']}").json()["state"]
            == "queued"
        )
        assert client.get("/api/v1/nlp/index/status/missing").status_code == 404
