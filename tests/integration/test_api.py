"""Focused API checks using local Qdrant and stubbed models (no paid API calls)."""
import asyncio
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from helpers import config

SETTINGS = SimpleNamespace(INPUT_MAX_CHARACTERS=100, EMBEDDING_MODEL_ID="test-embed",
                           APP_VERSION="test-version")
with patch.object(config, "get_settings", return_value=SETTINGS):
    from routes import nlp, health
    from controllers.NLPController import NLPController
    from stores.VectorDB.Providers.QdrantDBProvider import QdrantDBProvider
    from stores.VectorDB.Providers.PGVProvider import PGVectorProvider

from models.db_schems import RetrievedDocuments
from utils.inference import run_serialized
from utils.logging import RequestContextMiddleware


class Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def execute(self, query):
        return SimpleNamespace(scalar_one=lambda: 2)


class Embedding:
    embedding_size = 2

    def embed_text(self, **kwargs):
        return [[1.0, 0.0]]

    def health_check(self, role):
        return True


class Generation:
    def construct_prompt(self, prompt, role):
        return {"role": role, "content": prompt}

    def generate_text(self, **kwargs):
        return "The document contains a test fact."

    def health_check(self, role):
        return True


class Vector:
    default_vector_size = 2

    async def search_by_vector(self, **kwargs):
        return [RetrievedDocuments(text="test fact", score=0.9,
                metadata={"asset_name": "report.pdf", "page": 0})] * 2

    async def get_indexed_documents_count(self):
        return 1


class Templates:
    def get(self, *args):
        return "Test prompt"


def make_app():
    app = FastAPI()
    app.db_client = Session
    app.vector_db_client = Vector()
    app.generation_client = Generation()
    app.embedding_client = Embedding()
    app.reranker_client = SimpleNamespace(model=object(), rerank=lambda **kw: [(0, 1.0), (1, 0.9)])
    app.template_parser = Templates()
    app.include_router(nlp.nlp_router)
    app.include_router(health.health_router)
    app.add_middleware(RequestContextMiddleware, access_sample_rate=1.0)
    app.dependency_overrides[health.get_settings] = lambda: SETTINGS
    return app


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        project_model = SimpleNamespace(get_project_or_create_one=AsyncMock(
            return_value=SimpleNamespace(project_id=1)))
        self.project_patch = patch.object(nlp.ProjectModel, "create_instance",
                                          AsyncMock(return_value=project_model))
        self.settings_patch = patch("controllers.BaseController.get_settings", return_value=SETTINGS)
        self.project_patch.start()
        self.settings_patch.start()
        self.addCleanup(self.project_patch.stop)
        self.addCleanup(self.settings_patch.stop)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_validation_and_methods(self):
        for endpoint in ("search", "answer"):
            url = f"/api/v1/nlp/index/{endpoint}/1"
            for body in ({"text": ""}, {"text": "   "}, {"text": "x" * 101},
                         {"text": "question", "limit": 0},
                         {"text": "question", "limit": 21},
                         {"text": "question", "limit": None}):
                with self.subTest(endpoint=endpoint, body=body):
                    self.assertEqual(self.client.post(url, json=body).status_code, 422)
            self.assertEqual(self.client.get(url).status_code, 405)

    def test_answer_has_citations_and_no_debug_fields(self):
        response = self.client.post("/api/v1/nlp/index/answer/1", json={"text": "question"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["sources"], [{"asset_name": "report.pdf", "page": 1}])
        self.assertEqual(body["answer"], "The document contains a test fact.")
        self.assertEqual(set(body), {"signal", "answer", "sources", "request_id", "prompt_version"})
        self.assertEqual(body["request_id"], response.headers["x-request-id"])
        self.assertEqual(body["prompt_version"], "rag-v1")
        UUID(body["request_id"])
        self.assertNotIn("full_prompt", body)
        self.assertNotIn("chat_history", body)

    def test_search_retains_metadata(self):
        response = self.client.post("/api/v1/nlp/index/search/1", json={"text": "question"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["indexed_vectors"][0]["metadata"]["page"], 0)

    def test_no_results_returns_no_information(self):
        self.app.vector_db_client.search_by_vector = AsyncMock(return_value=[])
        self.assertEqual(self.client.post("/api/v1/nlp/index/answer/1",
                         json={"text": "question"}).status_code, 200)

    def test_documented_response_models(self):
        paths = self.client.get("/openapi.json").json()["paths"]
        for endpoint, model in (("answer", "AnswerResponse"), ("search", "SearchResponse")):
            schema = paths[f"/api/v1/nlp/index/{endpoint}/{{project_id}}"]
            self.assertEqual(schema["post"]["responses"]["200"]["content"]
                             ["application/json"]["schema"]["$ref"], f"#/components/schemas/{model}")

    def test_health_reports_real_count(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["documents_indexed"], 1)
        self.assertEqual(response.json()["embedding_model"], "test-embed")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_failed_dependencies_return_503_without_secrets(self):
        async def fail():
            raise RuntimeError("secret connection string")
        self.app.vector_db_client.get_indexed_documents_count = fail
        self.app.generation_client.health_check = lambda role: False
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["vector_db"], "error")
        self.assertEqual(response.json()["llm"], "error")
        self.assertIsNone(response.json()["documents_indexed"])
        self.assertNotIn("secret", response.text)

    def test_database_failure_returns_503(self):
        class BadSession(Session):
            async def execute(self, query):
                raise ConnectionError("database down")
        self.app.db_client = BadSession
        self.assertEqual(self.client.get("/health").json()["db"], "error")


class AsyncChecks(unittest.IsolatedAsyncioTestCase):
    async def test_slow_health_check_times_out(self):
        async def slow():
            await asyncio.sleep(1)
        with patch.object(health, "CHECK_TIMEOUT", 0.01):
            self.assertEqual(await health.checked("slow", slow), ("error", None))

    async def test_model_calls_are_serialized_and_do_not_block_event_loop(self):
        owner = SimpleNamespace()
        active = 0
        maximum = 0
        guard = threading.Lock()
        ticks = 0
        progress_during_work = False
        def work():
            nonlocal active, maximum
            with guard:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.05)
            with guard:
                active -= 1
        async def heartbeat():
            nonlocal ticks, progress_during_work
            for _ in range(12):
                await asyncio.sleep(0.01)
                ticks += 1
                if active > 0:
                    progress_during_work = True
        await asyncio.gather(heartbeat(), *(run_serialized(owner, work) for _ in range(3)))
        self.assertEqual(maximum, 1)
        self.assertEqual(ticks, 12)
        self.assertTrue(progress_during_work)

    async def test_qdrant_index_search_count_reset_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = QdrantDBProvider(directory, default_vector_size=2, distance_method="cosine")
            await provider.connect()
            try:
                self.assertTrue(await provider.create_collection("collection_2_1", 2))
                self.assertTrue(await provider.insert_many("collection_2_1",
                    ["page one", "page two"], [[1.0, 0.0], [0.9, 0.1]],
                    [{"asset_id": 7, "asset_name": "report.pdf", "page": 0},
                     {"asset_id": 7, "asset_name": "report.pdf", "page": 1}], [1, 2]))
                results = await provider.search_by_vector("collection_2_1", [1.0, 0.0], k=2)
                self.assertIsInstance(results[0], RetrievedDocuments)
                self.assertEqual(results[0].metadata["asset_name"], "report.pdf")
                self.assertEqual(await provider.get_indexed_documents_count(), 1)
                await provider.delete_vectors_by_asset_id("collection_2_1", 7)
                self.assertEqual(await provider.get_indexed_documents_count(), 0)
                self.assertTrue(await provider.create_collection("collection_2_1", 2, do_reset=True))
                self.assertFalse(await provider.insert_many("collection_2_1", ["x"], [[1.0, 0.0]], [], [3]))
            finally:
                await provider.disconnect()

    async def test_index_failure_is_not_reported_as_success(self):
        controller = NLPController.__new__(NLPController)
        controller.embedding_client = Embedding()
        controller.vector_db_client = SimpleNamespace(
            default_vector_size=2, create_collection=AsyncMock(),
            insert_many=AsyncMock(return_value=False))
        chunk = SimpleNamespace(chunk_text="test fact", chunk_metadata={}, chunk_asset_id=7)
        result = await controller.index_into_vector_db(SimpleNamespace(project_id=1), [chunk], [1])
        self.assertFalse(result)
        self.assertEqual(controller.vector_db_client.insert_many.call_args.kwargs["metadata"],
                         [{"asset_id": 7, "chunk_id": 1}])

    async def test_postgres_count_uses_indexed_assets(self):
        provider = PGVectorProvider(Session, default_vector_size=2, distance_method="cosine")
        provider.list_collections = AsyncMock(return_value=["collection_2_1"])
        self.assertEqual(await provider.get_indexed_documents_count(), 2)
        provider.list_collections = AsyncMock(return_value=["unsafe; DROP TABLE chunks"])
        with self.assertRaises(ValueError):
            await provider.get_indexed_documents_count()


if __name__ == "__main__":
    unittest.main()
