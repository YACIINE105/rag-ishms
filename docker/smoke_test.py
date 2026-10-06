"""Readiness and API contract smoke checks against a running container.

Run with Python's standard library; never uploads documents or generates text.
"""

import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(base_url, path, method="GET", payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"X-Request-ID": "docker-smoke-check"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(
        base_url.rstrip("/") + path, data=body, headers=headers, method=method
    )
    try:
        response = urlopen(req, timeout=20)
    except HTTPError as error:
        response = error
    with response:
        assert response.headers.get("X-Request-ID") == "docker-smoke-check", path
        return response.status, json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--expect-unhealthy", action="store_true")
    args = parser.parse_args()
    status, health = request(args.base_url, "/health")
    if args.expect_unhealthy:
        assert status == 503 and health["status"] == "unhealthy", (status, health)
        print("PASS: dependency failure produces HTTP 503 and a correlated request ID")
        return
    assert status == 200 and health["status"] == "healthy", (status, health)
    for dependency in ("db", "vector_db", "llm", "embedding", "reranker"):
        assert health[dependency] == "ok", health
    assert isinstance(health["documents_indexed"], int), health
    print("PASS: all readiness dependencies report ok")

    status, schema = request(args.base_url, "/openapi.json")
    assert status == 200
    for action in ("search", "answer"):
        path = "/api/v1/nlp/index/" + action + "/{project_id}"
        assert "post" in schema["paths"][path] and "get" not in schema["paths"][path]
        endpoint = path.replace("{project_id}", "1")
        for payload in (
            {},
            {"text": ""},
            {"text": "   "},
            {"text": "x", "limit": 0},
            {"text": "x", "limit": 999},
        ):
            code, error = request(args.base_url, endpoint, "POST", payload)
            assert code == 422 and "detail" in error, (endpoint, payload, code)
    fields = schema["components"]["schemas"]["AnswerResponse"]["properties"]
    assert set(fields) == {
        "signal",
        "answer",
        "sources",
        "request_id",
        "prompt_version",
    }, fields
    print("PASS: POST routes, response schema, validation and request ID headers")


if __name__ == "__main__":
    main()
