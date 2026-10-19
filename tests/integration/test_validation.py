import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.schemes.nlp import SearchRequest
from utils.logging import RequestContextMiddleware


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"text": ""},
        {"text": "   "},
        {"text": "x", "limit": 0},
        {"text": "x", "limit": 999},
        {"text": "x" * 101},
    ],
)
def test_invalid_questions_return_422(body):
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.post("/answer")
    def answer(payload: SearchRequest):
        return payload

    with TestClient(app) as client:
        response = client.post("/answer", json=body)
    assert response.status_code == 422
    assert response.headers["x-request-id"]
