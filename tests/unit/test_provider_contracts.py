from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.db_schems import RetrievedDocuments
from stores.llm.providers.CoHereProvider import CohereProvider
from stores.llm.providers.GoogleAIProvider import GoogleAIProvider
from stores.llm.providers.LlamaCPPProvider import LlamaCPPProvider
from stores.llm.providers.OpenAIProvider import OpenAIProvider
from stores.VectorDB.Providers.PGVProvider import PGVectorProvider
from stores.VectorDB.Providers.QdrantDBProvider import QdrantDBProvider
from stores.VectorDB.VectorDBEnums import PGVectorDistanceMethodEnums as Distance


@pytest.fixture(
    params=[OpenAIProvider, CohereProvider, GoogleAIProvider, LlamaCPPProvider]
)
def provider(request):
    cls = request.param
    module = cls.__module__
    if cls is OpenAIProvider:
        with patch(module + ".OpenAI"):
            result = cls("test", api_url="http://test")
    elif cls is CohereProvider:
        with patch(module + ".cohere.Client"):
            result = cls("test")
    elif cls is GoogleAIProvider:
        with patch(module + ".genai.Client"):
            result = cls("test")
    else:
        result = cls()
    with patch("stores.llm.providers.LlamaCPPProvider.Llama"):
        result.set_generation_model("model")
        result.set_embedding_model("embedding", 2)
    return result


def set_embedding_result(provider, vectors):
    if isinstance(provider, OpenAIProvider):
        provider.client.embeddings.create.return_value = NS(
            data=[NS(embedding=v) for v in vectors]
        )
    elif isinstance(provider, CohereProvider):
        provider.client.embed.return_value = NS(embeddings=NS(float=vectors))
    elif isinstance(provider, GoogleAIProvider):
        provider.client.models.embed_content.return_value = NS(
            embeddings=[NS(values=v) for v in vectors]
        )
    else:
        provider.embedding_client.embed.return_value = vectors


@pytest.mark.parametrize("text", ["query", ["one", "two"]])
def test_embedding_contract(provider, text):
    count = 1 if isinstance(text, str) else 2
    set_embedding_result(provider, [[1.0, 0.0]] * count)
    result = provider.embed_text(text=text, document_type="query", input_type="query")
    assert result == [[1.0, 0.0]] * count
    # Document type and keyword must also be accepted for indexing.
    assert provider.embed_text(
        text=text, document_type="document", input_type="passage"
    )


def test_missing_or_empty_embeddings(provider):
    set_embedding_result(provider, [])
    assert provider.embed_text("x", "document", "passage") is None
    provider.embedding_model_id = None
    assert provider.embed_text("x", "document", "passage") is None
    if isinstance(provider, LlamaCPPProvider):
        provider.embedding_client = None
    else:
        provider.client = None
    assert provider.embed_text("x", "document", "passage") is None


def set_generation_result(provider, text="answer"):
    if isinstance(provider, OpenAIProvider):
        method = provider.client.chat.completions.create
        method.return_value = NS(
            choices=[NS(message=NS(content=text))],
            usage=NS(prompt_tokens=4, completion_tokens=2),
        )
    elif isinstance(provider, CohereProvider):
        method = provider.client.chat
        method.return_value = NS(
            text=text, meta=NS(tokens=NS(input_tokens=4, output_tokens=2))
        )
    elif isinstance(provider, GoogleAIProvider):
        method = provider.client.models.generate_content
        method.return_value = NS(
            text=text, usage_metadata=NS(prompt_token_count=4, candidates_token_count=2)
        )
    else:
        method = provider.generation_client.create_chat_completion
        method.return_value = {
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2},
        }
    return method


def test_generation_usage_and_failure_contract(provider):
    method = set_generation_result(provider)
    answer = provider.generate_text("question", max_output_token=5, temperature=0.3)
    assert str(answer) == "answer" and answer.tokens_in == 4 and answer.tokens_out == 2
    set_generation_result(provider, "")
    assert provider.generate_text("question") is None
    method.side_effect = RuntimeError("offline")
    assert provider.generate_text("question") is None
    provider.generation_model_id = None
    assert provider.generate_text("question") is None
    if isinstance(provider, LlamaCPPProvider):
        provider.generation_client = None
    else:
        provider.client = None
    assert provider.generate_text("question") is None


def test_provider_readiness(provider):
    if isinstance(provider, LlamaCPPProvider):
        provider.generation_client.n_ctx.return_value = 100
        provider.embedding_client.n_ctx.return_value = 100
    assert provider.health_check("generation")
    assert provider.health_check("embedding")
    if isinstance(provider, LlamaCPPProvider):
        provider.generation_client = None
    else:
        provider.generation_model_id = None
    assert not provider.health_check("generation")


def test_llama_embedding_batch_alias():
    p = LlamaCPPProvider()
    p.embedding_client = MagicMock()
    p.embedding_model_id = "m"
    p.embedding_size = 2
    p.embedding_client.embed.return_value = [[1.0, 0.0]]
    assert p.embed_texts(["x"]) == [[1.0, 0.0]]
    p.embedding_client.embed.return_value = []
    assert p.embed_texts(["x"]) is None
    p.embedding_client.embed.side_effect = RuntimeError("failed")
    assert p.embed_texts(["x"]) is None


class Session:
    def __init__(self):
        self.result = MagicMock()
        self.execute = AsyncMock(return_value=self.result)
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def begin(self):
        return self


@pytest.fixture
def pg():
    session = Session()
    p = PGVectorProvider(
        lambda: session,
        default_vector_size=2,
        distance_method="cosine",
        index_threshold=2,
    )
    return p, session


@pytest.mark.parametrize("kind", ["qdrant", "pgvector"])
async def test_vector_provider_keyword_and_metadata_contract(kind, pg):
    if kind == "qdrant":
        p = QdrantDBProvider(":memory:")
        p.client = MagicMock()
        p.client.query_points.return_value = NS(
            points=[
                NS(id=7, score=1.0, payload={"text": "text", "metadata": {"page": 2}})
            ]
        )
    else:
        p, session = pg
        p.collection_exists = AsyncMock(return_value=True)
        session.result.fetchall.return_value = [
            NS(id=7, text="text", score=1.0, metadata={"page": 2})
        ]
    result = await p.search_by_vector(
        collection_name="collection_2_1", vector=[1.0, 0.0], k=3
    )
    assert isinstance(result[0], RetrievedDocuments)
    assert result[0].id == 7 and result[0].metadata == {"page": 2}


@pytest.mark.parametrize("distance", list(Distance)[:-1])
async def test_pg_distance_and_vector_cast(pg, distance):
    p, s = pg
    p.collection_exists = AsyncMock(return_value=True)
    s.result.fetchall.return_value = []
    assert (
        await p.search_by_vector(
            "collection_2_1", [0.0] * 2001, k=3, distance_method=distance
        )
        == []
    )
    assert "halfvec" in str(s.execute.call_args.args[0])
    assert s.execute.call_args.args[1]["limit"] == 3


async def test_pg_lifecycle_and_count(pg):
    p, s = pg
    await p.connect()
    await p.disconnect()
    s.result.first.return_value = True
    assert await p.collection_exists("collection_2_1")
    s.result.scalars.return_value.all.return_value = ["collection_2_1"]
    assert await p.list_collections() == ["collection_2_1"]
    s.result.scalar_one.return_value = 3
    assert await p.get_indexed_documents_count() == 3
    s.result.fetchone.return_value = NS(_mapping={"tablename": "collection_2_1"})
    assert (await p.get_collection_info("collection_2_1"))["record_count"] == 3
    s.result.fetchone.return_value = None
    assert await p.get_collection_info("collection_2_1") is None
    for method in (p.delete_collection, p.get_collection_info):
        with pytest.raises(ValueError):
            await method("bad;name")
    p.collection_exists = AsyncMock(return_value=False)
    assert await p.delete_collection("collection_2_1")
    assert await p.create_collection("collection_2_1", 2001, do_reset=True)
    p.collection_exists.return_value = True
    assert not await p.create_collection("collection_2_1", 2)


async def test_pg_insert_parameters_and_failures(pg):
    p, s = pg
    p.collection_exists = AsyncMock(return_value=True)
    assert await p.insert_one(
        "collection_2_1", "x", [1.0, 0.0], {"page": 1}, record_id=7
    )
    assert s.execute.call_args.args[1]["record_id"] == 7
    assert not await p.insert_one("collection_2_1", "x", [1.0, 0.0])
    assert await p.insert_many(
        "collection_2_1",
        ["a", "b"],
        [[1.0, 0.0], [0.0, 1.0]],
        record_ids=[1, 2],
        batch_size=1,
    )
    assert not await p.insert_many("collection_2_1", ["a"], [], record_ids=[1])
    assert not await p.insert_many(
        "collection_2_1", ["a"], [[1.0, 0.0]], metadata=[{}, {}], record_ids=[1]
    )
    s.execute.side_effect = RuntimeError("offline")
    assert not await p.insert_many(
        "collection_2_1", ["a"], [[1.0, 0.0]], record_ids=[1]
    )
    assert not await p.delete_vectors_by_asset_id("collection_2_1", 7)
    assert await p.search_by_vector("collection_2_1", [1.0, 0.0], k=3) is None
    p.collection_exists.return_value = False
    assert await p.delete_vectors_by_asset_id("collection_2_1", 7)
    assert not await p.insert_many(
        "collection_2_1", ["a"], [[1.0, 0.0]], record_ids=[1]
    )
    assert not await p.insert_one("collection_2_1", "a", [1.0, 0.0], record_id=1)
    assert await p.search_by_vector("collection_2_1", [1.0, 0.0], k=3) is None


async def test_pg_indexes(pg):
    p, s = pg
    p.collection_exists = AsyncMock(return_value=True)
    s.result.scalar_one_or_none.return_value = 1
    assert await p.is_existed_index("collection_2_1")
    s.result.scalar_one.return_value = 1
    assert not await p.create_vector_index("collection_2_1")
    s.result.scalar_one.return_value = 3
    await p.create_vector_index("collection_2_1")
    assert "CREATE INDEX" in str(s.execute.call_args.args[0])
    await p.reset_vector_index("collection_2_1")
    p.is_existed_index = AsyncMock(return_value=False)
    assert not await p.reset_vector_index("collection_2_1")
    p.collection_exists.return_value = False
    assert not await p.create_vector_index("collection_2_1")


@pytest.mark.parametrize(
    "size,distance", [(2, "cosine"), (2, "l2"), (2001, "cosine"), (2001, "l2")]
)
def test_pg_storage_precision(size, distance):
    p = PGVectorProvider(None, default_vector_size=size, distance_method=distance)
    assert ("halfvec" in p.distance_method) == (size > 2000)


async def test_qdrant_remote_and_failed_inserts():
    with patch("stores.VectorDB.Providers.QdrantDBProvider.QdrantClient") as cls:
        p = QdrantDBProvider("unused", url="http://qdrant:6333")
        await p.connect()
        cls.assert_called_once_with(url="http://qdrant:6333", api_key=None, timeout=3)
        p.client.collection_exists.return_value = False
        assert not await p.insert_one("collection_2_1", "x", [1.0, 0.0], record_id=1)
        assert await p.delete_vectors_by_asset_id("collection_2_1", 1)
        p.client.collection_exists.return_value = True
        p.client.upsert.side_effect = RuntimeError("offline")
        assert not await p.insert_one("collection_2_1", "x", [1.0, 0.0], record_id=1)
        p.client.get_collection.return_value.model_dump.return_value = {
            "points_count": 1
        }
        assert await p.get_collection_info("collection_2_1") == {"points_count": 1}
        assert await p.create_vector_index("collection_2_1")
        await p.list_collections()
        await p.disconnect()


def test_generation_message_shape_matches_sdk(provider):
    method = set_generation_result(provider)
    history = [provider.construct_prompt("System instructions", "system")]
    assert provider.generate_text("question", chat_history=history) == "answer"
    if isinstance(provider, CohereProvider):
        messages = method.call_args.kwargs["chat_history"]
        assert all(
            "message" in item and item["role"] in {"USER", "SYSTEM", "CHATBOT"}
            for item in messages
        )
        assert method.call_args.kwargs["message"] == "question"
        assert sum(item["role"] == "USER" for item in history) == 1
    elif isinstance(provider, GoogleAIProvider):
        args = method.call_args.kwargs
        assert args["config"].system_instruction == "System instructions"
        assert all(item["role"] != "system" for item in args["contents"])
        # Exercise the installed SDK's input conversion, not just a permissive mock.
        from google.genai import _transformers

        converted = _transformers.t_contents(args["contents"])
        assert converted[0].role == "user"
        assert converted[0].parts[0].text == "question"


def test_reranker_orders_scores_without_progress_output():
    from stores.llm.rerankers.cross_encoder_reranker import CrossEncoderReranker

    with patch("stores.llm.rerankers.cross_encoder_reranker.CrossEncoder") as model:
        model.return_value.predict.return_value = [0.2, 0.9, 0.5]
        reranker = CrossEncoderReranker(device="cpu")
        assert reranker.rerank("question", ["first", "second", "third"], top_n=2) == [
            (1, 0.9),
            (2, 0.5),
        ]
        model.return_value.predict.assert_called_once_with(
            [("question", "first"), ("question", "second"), ("question", "third")],
            show_progress_bar=False,
        )
