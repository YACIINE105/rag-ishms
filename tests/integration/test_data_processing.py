import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from controllers.ProcessController import Document
from controllers.ProjectController import ProjectController
from models.db_schems import DataChunk
from routes import data, nlp
from stores.VectorDB.Providers.QdrantDBProvider import QdrantDBProvider


@pytest.fixture
async def processing_context(tmp_path, monkeypatch):
    app = FastAPI()
    vector = QdrantDBProvider(
        str(tmp_path / "vectors"), default_vector_size=2, distance_method="cosine"
    )
    await vector.connect()

    embedding = MagicMock()
    embedding.embedding_model_id = "test-embed"
    embedding.embedding_size = 2
    embedding.embed_text.side_effect = lambda text, **kwargs: [
        [1.0, 0.0] if content.startswith("العقد") else [0.0, 1.0] for content in text
    ]

    app.db_client = object()
    app.vector_db_client = vector
    app.embedding_client = embedding
    app.generation_client = None
    app.reranker_client = None
    app.template_parser = None
    app.include_router(data.data_router)
    app.include_router(nlp.nlp_router)

    project = SimpleNamespace(project_id=1)
    asset = SimpleNamespace(
        asset_id=7, unique_asset_name="law.PDF", asset_name="civil-code.pdf"
    )
    (tmp_path / asset.unique_asset_name).write_bytes(b"PDF input")

    stored_chunks = []
    next_chunk_id = 1

    def insert_chunks(chunks):
        nonlocal next_chunk_id
        for chunk in chunks:
            chunk.chunk_id = next_chunk_id
            next_chunk_id += 1
            stored_chunks.append(chunk)
        return len(chunks)

    def delete_asset_chunks(asset_id):
        previous_count = len(stored_chunks)
        stored_chunks[:] = [
            chunk for chunk in stored_chunks if chunk.chunk_asset_id != asset_id
        ]
        return previous_count - len(stored_chunks)

    def has_asset_chunks(asset_id, processing_mode=None):
        return any(
            chunk.chunk_asset_id == asset_id
            and (
                processing_mode is None
                or chunk.chunk_metadata["processing_mode"] == processing_mode
            )
            for chunk in stored_chunks
        )

    def get_chunks(project_id, page_number, page_size=50):
        start = (page_number - 1) * page_size
        return stored_chunks[start : start + page_size]

    chunk_model = SimpleNamespace(
        insert_many_chunks=AsyncMock(side_effect=insert_chunks),
        delete_chunk_by_asset_id=AsyncMock(side_effect=delete_asset_chunks),
        delete_chunk_by_project_id=AsyncMock(
            side_effect=lambda **kwargs: stored_chunks.clear()
        ),
        has_chunks_for_asset=AsyncMock(side_effect=has_asset_chunks),
        get_project_chunks=AsyncMock(side_effect=get_chunks),
        get_all_chunks_count=AsyncMock(side_effect=lambda **kwargs: len(stored_chunks)),
    )
    project_model = SimpleNamespace(
        get_project_or_create_one=AsyncMock(return_value=project)
    )
    asset_model = SimpleNamespace(
        get_asset_record=AsyncMock(return_value=asset),
        get_all_project_assets=AsyncMock(return_value=[asset]),
    )
    monkeypatch.setattr(
        data.ProjectModel, "create_instance", AsyncMock(return_value=project_model)
    )
    monkeypatch.setattr(
        data.AssetModel, "create_instance", AsyncMock(return_value=asset_model)
    )
    monkeypatch.setattr(
        data.ChunkModel, "create_instance", AsyncMock(return_value=chunk_model)
    )
    monkeypatch.setattr(
        ProjectController,
        "get_project_path",
        lambda self, project_id: str(tmp_path),
    )

    qalam_data = {
        "pages": [
            {
                "number": 16,
                "width": 600,
                "blocks": [
                    {
                        "type": "table",
                        "rows": [
                            [
                                {
                                    "text": "مادة ١٤٧ العقد شريعة المتعاقدين.",
                                    "bbox": [310, 600, 580, 660],
                                },
                                {
                                    "text": "Article 147 A complete English article provision.",
                                    "bbox": [20, 600, 290, 660],
                                },
                            ]
                        ],
                    }
                ],
            }
        ],
    }
    process_module = importlib.import_module("controllers.ProcessController")
    qalam_factory = MagicMock(
        return_value=SimpleNamespace(to_json=lambda: json.dumps(qalam_data))
    )
    baseline_loader = MagicMock()
    baseline_loader.return_value.load.return_value = [
        Document("Baseline page text for character chunking.", {"page": 0})
    ]
    monkeypatch.setattr(process_module.qalam, "Document", qalam_factory)
    monkeypatch.setattr(process_module, "PyMuPDFLoader", baseline_loader)

    try:
        async with AsyncClient(
            transport=ASGITransport(app), base_url="http://test"
        ) as client:
            yield SimpleNamespace(
                client=client,
                vector=vector,
                embedding=embedding,
                records=stored_chunks,
                asset=asset,
                chunk_model=chunk_model,
                qalam_factory=qalam_factory,
                baseline_loader=baseline_loader,
            )
    finally:
        await vector.disconnect()


@pytest.mark.parametrize("W_qalam", [True, False, None])
async def test_processing_modes_and_separate_vector_storage(
    processing_context, W_qalam
):
    context = processing_context
    body = {
        "file_id": context.asset.unique_asset_name,
        "chunk_size": 8,
        "overlap_size": 50 if W_qalam else 2,
    }
    if W_qalam is not None:
        body["W_qalam"] = W_qalam

    response = await context.client.post("/api/v1/data/process/1", json=body)
    assert response.status_code == 200, response.text
    mode = "qalam" if W_qalam else "baseline"
    assert response.json()["processing_mode"] == mode
    assert response.json()["inserted_chunks"] == len(context.records)
    assert all(isinstance(chunk, DataChunk) for chunk in context.records)
    assert all(
        chunk.chunk_metadata["processing_mode"] == mode for chunk in context.records
    )

    if W_qalam:
        context.qalam_factory.assert_called_once()
        context.baseline_loader.assert_not_called()
        assert response.json()["inserted_chunks_by_language"] == {"ar": 1, "en": 1}
        assert [chunk.chunk_metadata["language"] for chunk in context.records] == [
            "ar",
            "en",
        ]
        assert all(len(chunk.chunk_text) > 8 for chunk in context.records)
    else:
        context.qalam_factory.assert_not_called()
        context.baseline_loader.assert_called_once()
        assert all(len(chunk.chunk_text) <= 8 for chunk in context.records)
        assert response.json()["inserted_chunks_by_language"] == {
            "unknown": len(context.records)
        }

    indexed = await context.client.post("/api/v1/nlp/index/push/1", json={})
    assert indexed.status_code == 200, indexed.text
    assert indexed.json()["inserted_items_count"] == len(context.records)
    assert context.embedding.embed_text.call_args.kwargs["text"] == [
        chunk.chunk_text for chunk in context.records
    ]

    collections = await context.vector.list_collections()
    assert len(collections.collections) == 1
    stored_vectors = await context.vector.search_by_vector(
        collections.collections[0].name, [1.0, 0.0], k=len(context.records)
    )
    assert {vector.id for vector in stored_vectors} == {
        chunk.chunk_id for chunk in context.records
    }
    assert all(vector.metadata["asset_id"] == 7 for vector in stored_vectors)

    if W_qalam:
        assert {vector.metadata["language"] for vector in stored_vectors} == {
            "ar",
            "en",
        }
        assert all(
            vector.metadata["article_number"] == 147 for vector in stored_vectors
        )
        assert all(
            vector.metadata["citation"] == "Egyptian Civil Code, Article 147"
            for vector in stored_vectors
        )
        assert {vector.text for vector in stored_vectors} == {
            "Egyptian Civil Code, Article 147\nالعقد شريعة المتعاقدين.",
            "Egyptian Civil Code, Article 147\nA complete English article provision.",
        }


async def test_indexing_paces_batches_for_free_upstream(
    processing_context, monkeypatch
):
    context = processing_context
    response = await context.client.post(
        "/api/v1/data/process/1", json={"W_qalam": True}
    )
    assert response.status_code == 200
    sleep = AsyncMock()
    monkeypatch.setattr(nlp, "asyncio", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(
        nlp,
        "get_settings",
        lambda: SimpleNamespace(INDEX_BATCH_DELAY_SECONDS=3.5, INDEX_BATCH_SIZE=1),
    )
    indexed = await context.client.post("/api/v1/nlp/index/push/1", json={})
    assert indexed.status_code == 200
    assert indexed.json()["inserted_items_count"] == len(context.records)
    assert sleep.await_count == len(context.records)
    assert all(call.args == (3.5,) for call in sleep.await_args_list)
    assert all(
        call.kwargs["page_size"] == 1
        for call in context.chunk_model.get_project_chunks.await_args_list
    )


@pytest.mark.parametrize("initial_mode", [False, True])
async def test_switching_modes_replaces_chunks_and_vectors(
    processing_context, initial_mode
):
    context = processing_context
    response = await context.client.post(
        "/api/v1/data/process/1", json={"W_qalam": initial_mode}
    )
    assert response.status_code == 200
    initial_ids = {chunk.chunk_id for chunk in context.records}
    indexed = await context.client.post("/api/v1/nlp/index/push/1", json={})
    assert indexed.status_code == 200
    assert await context.vector.get_indexed_documents_count() == 1

    repeated = await context.client.post(
        "/api/v1/data/process/1", json={"W_qalam": initial_mode}
    )
    assert repeated.json()["processed_files"] == 0
    assert {chunk.chunk_id for chunk in context.records} == initial_ids

    switched = await context.client.post(
        "/api/v1/data/process/1", json={"W_qalam": not initial_mode}
    )
    assert switched.status_code == 200, switched.text
    assert switched.json()["processed_files"] == 1
    assert initial_ids.isdisjoint(chunk.chunk_id for chunk in context.records)
    assert await context.vector.get_indexed_documents_count() == 0
    indexed = await context.client.post("/api/v1/nlp/index/push/1", json={})
    assert indexed.status_code == 200
    assert await context.vector.get_indexed_documents_count() == 1


async def test_failed_vector_cleanup_keeps_existing_language_chunks(
    processing_context,
):
    context = processing_context
    response = await context.client.post(
        "/api/v1/data/process/1", json={"W_qalam": True}
    )
    assert response.status_code == 200
    indexed = await context.client.post("/api/v1/nlp/index/push/1", json={})
    assert indexed.status_code == 200
    original_ids = {chunk.chunk_id for chunk in context.records}
    context.chunk_model.delete_chunk_by_asset_id.reset_mock()
    context.vector.delete_vectors_by_asset_id = AsyncMock(return_value=False)

    response = await context.client.post(
        "/api/v1/data/process/1", json={"W_qalam": False}
    )
    assert response.status_code == 400
    assert {chunk.chunk_id for chunk in context.records} == original_ids
    assert all(
        chunk.chunk_metadata["processing_mode"] == "qalam" for chunk in context.records
    )
    context.chunk_model.delete_chunk_by_asset_id.assert_not_awaited()
    assert await context.vector.get_indexed_documents_count() == 1


async def test_qalam_rejects_non_pdf_before_deleting_chunks(processing_context):
    context = processing_context
    context.asset.unique_asset_name = "notes.txt"
    response = await context.client.post(
        "/api/v1/data/process/1", json={"W_qalam": True, "do_reset": 1}
    )
    assert response.status_code == 400
    assert response.json()["unsupported_files"] == ["notes.txt"]
    context.chunk_model.delete_chunk_by_project_id.assert_not_awaited()
    context.chunk_model.delete_chunk_by_asset_id.assert_not_awaited()
    context.qalam_factory.assert_not_called()


@pytest.mark.parametrize("W_qalam", [True, False])
async def test_empty_extraction_fails_processing_job(processing_context, W_qalam):
    context = processing_context
    context.qalam_factory.return_value.to_json = lambda: json.dumps({"pages": []})
    context.baseline_loader.return_value.load.return_value = []

    response = await context.client.post(
        "/api/v1/data/process/jobs/1", json={"W_qalam": W_qalam}
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    job = await context.client.get(f"/api/v1/data/process/status/{job_id}")
    assert job.json()["state"] == "failed"
    assert job.json()["result"]["processed_files"] == 0
    assert job.json()["result"]["inserted_chunks"] == 0
    context.chunk_model.delete_chunk_by_asset_id.assert_not_awaited()
    assert not context.records


async def test_empty_extraction_keeps_previous_chunks_and_vectors(processing_context):
    context = processing_context
    await context.client.post("/api/v1/data/process/1", json={"W_qalam": True})
    await context.client.post("/api/v1/nlp/index/push/1", json={})
    previous_ids = {chunk.chunk_id for chunk in context.records}
    context.chunk_model.delete_chunk_by_asset_id.reset_mock()
    context.baseline_loader.return_value.load.return_value = []

    response = await context.client.post(
        "/api/v1/data/process/1", json={"W_qalam": False}
    )
    assert response.status_code == 400
    assert response.json()["failed_files"] == 1
    assert {chunk.chunk_id for chunk in context.records} == previous_ids
    assert await context.vector.get_indexed_documents_count() == 1
    context.chunk_model.delete_chunk_by_asset_id.assert_not_awaited()


@pytest.mark.parametrize("background", [False, True])
async def test_empty_project_cannot_be_indexed(processing_context, background):
    context = processing_context
    route = "jobs" if background else "push"
    response = await context.client.post(f"/api/v1/nlp/index/{route}/1", json={})
    if background:
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        job = await context.client.get(f"/api/v1/nlp/index/status/{job_id}")
        assert job.json()["state"] == "failed"
    else:
        assert response.status_code == 400
        assert "Process a document" in response.json()["detail"]
    context.embedding.embed_text.assert_not_called()
    collections = await context.vector.list_collections()
    assert not collections.collections
