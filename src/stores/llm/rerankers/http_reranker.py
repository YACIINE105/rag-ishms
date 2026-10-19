"""Keep the controller's rerank contract while serving the model outside the API."""

import math

import httpx


class HTTPReranker:
    def __init__(self, base_url, model_name, api_key=None, timeout=30, max_length=512):
        self.model_name = model_name
        self.max_length = max_length
        self.client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=timeout,
            trust_env=False,
        )

    def rerank(self, query: str, documents: list[str], top_n: int = 5):
        if not documents:
            return []
        response = self.client.post(
            "rerank",
            json={
                "model": self.model_name,
                "query": query,
                "documents": documents,
                "top_n": min(top_n, len(documents)),
                "truncate_prompt_tokens": self.max_length,
                "use_activation": True,
            },
        )
        response.raise_for_status()
        results = response.json()["results"]
        ranked, seen = [], set()
        for item in results:
            index, score = item["index"], item["relevance_score"]
            if (
                type(index) is not int
                or not 0 <= index < len(documents)
                or index in seen
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
            ):
                raise ValueError("Invalid reranker response")
            seen.add(index)
            ranked.append((index, float(score)))
        if len(ranked) != min(top_n, len(documents)):
            raise ValueError("Incomplete reranker response")
        return sorted(ranked, key=lambda item: item[1], reverse=True)[:top_n]

    def health_check(self):
        response = self.client.get("models", timeout=3)
        response.raise_for_status()
        return any(item["id"] == self.model_name for item in response.json()["data"])

    def close(self):
        self.client.close()
