import json
from unittest.mock import patch

import httpx
import pytest

from stores.llm.rerankers.http_reranker import HTTPReranker


def make_reranker(handler):
    client = httpx.Client(
        base_url="http://reranker/v1/",
        headers={"Authorization": "Bearer test-key"},
        transport=httpx.MockTransport(handler),
    )
    with patch("stores.llm.rerankers.http_reranker.httpx.Client", return_value=client):
        return HTTPReranker("http://reranker/v1", "bge", "test-key")


def test_remote_reranker_preserves_indices_and_checks_authentication():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-key"
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "bge"}]})
        assert request.url.path == "/v1/rerank"
        body = json.loads(request.content)
        assert body["documents"] == ["first", "second"]
        assert body["top_n"] == 2
        assert body["truncate_prompt_tokens"] == 512
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 0, "relevance_score": 0.1},
                    {"index": 1, "relevance_score": 0.9},
                ]
            },
        )

    reranker = make_reranker(handler)
    assert reranker.health_check()
    assert reranker.rerank("query", ["first", "second"]) == [(1, 0.9), (0, 0.1)]
    assert reranker.rerank("query", []) == []
    reranker.close()


@pytest.mark.parametrize(
    "results",
    [
        [],
        [{"index": 2, "relevance_score": 0.8}],
        [{"index": 0, "relevance_score": float("nan")}],
        [{"index": 0, "relevance_score": 0.8}, {"index": 0, "relevance_score": 0.7}],
    ],
)
def test_invalid_remote_results_fail_instead_of_corrupting_citations(results):
    # Build raw JSON to exercise even a non-standard upstream NaN response.
    reranker = make_reranker(
        lambda request: httpx.Response(
            200, content=json.dumps({"results": results}).encode()
        )
    )
    with pytest.raises(ValueError):
        reranker.rerank("query", ["first", "second"], top_n=2)
    reranker.close()


def test_remote_error_is_not_silently_replaced_with_vector_results():
    reranker = make_reranker(lambda request: httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        reranker.rerank("query", ["first"])
    reranker.close()
