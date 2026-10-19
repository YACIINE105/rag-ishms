from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.metrics import setup_metrics


def test_metrics_use_template_for_project_and_unmatched_paths():
    app = FastAPI()
    setup_metrics(app)

    @app.get("/project/{project_id}")
    def project(project_id: int):
        return {"id": project_id}

    with TestClient(app) as client:
        client.get("/project/98123")
        client.get("/missing/98123")
        text = client.get("/metrics").text
    assert 'endpoint="/project/{project_id}"' in text
    assert 'endpoint="unmatched"' in text
    assert 'endpoint="/project/98123"' not in text
    assert 'endpoint="/missing/98123"' not in text
