import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from controllers.NLPController import NLPController, NO_INFORMATION
from models.db_schems import RetrievedDocuments
from utils.generation import GenerationText


@pytest.fixture
def controller():
    embedding=MagicMock(); embedding.embed_text.return_value=[[1.,0.]]; embedding.embedding_size=2
    vector=SimpleNamespace(default_vector_size=2,search_by_vector=AsyncMock(),
        create_collection=AsyncMock(),insert_many=AsyncMock(return_value=True),
        delete_collection=AsyncMock(),get_collection_info=AsyncMock(return_value={"ok":True}))
    vector.search_by_vector.return_value=[RetrievedDocuments(id=i,text=f"text{i}",score=1-i/10,
        metadata={"asset_name":"report.pdf","page":i}) for i in range(4)]
    reranker=MagicMock(); reranker.rerank.return_value=[(2,0.9),(0,0.8)]
    generation=MagicMock(); generation.generate_text.return_value=GenerationText("answer",10,2)
    generation.construct_prompt.side_effect=lambda **kw:kw
    templates=MagicMock(); templates.get.return_value="prompt"
    return NLPController(generation,embedding,vector,reranker,templates)


async def test_reranker_order_limit_and_events(controller,caplog):
    with caplog.at_level(logging.INFO):
        docs=await controller.search_vector_db_collection(SimpleNamespace(project_id=1),"query",limit=2)
    assert [d.id for d in docs]==[2,0]
    assert controller.vector_db_client.search_by_vector.call_args.kwargs["k"]==30
    events={r.message:r for r in caplog.records}
    assert events["retrieve.done"].n_candidates==4
    assert events["rerank.done"].top1_score==0.9


@pytest.mark.parametrize("reranker",[None,[]])
async def test_fallback_truncates(controller,reranker):
    if reranker is None: controller.reranker_client=None
    else: controller.reranker_client.rerank.return_value=[]
    docs=await controller.search_vector_db_collection(SimpleNamespace(project_id=1),"query",limit=2)
    assert [d.id for d in docs]==[0,1]


@pytest.mark.parametrize("vectors",[None,[],[[]]])
async def test_embedding_failures_are_errors(controller,vectors):
    controller.embedding_client.embed_text.return_value=vectors
    with pytest.raises(RuntimeError):
        await controller.search_vector_db_collection(SimpleNamespace(project_id=1),"q")


async def test_vector_and_reranker_failures(controller):
    controller.vector_db_client.search_by_vector.return_value=None
    with pytest.raises(RuntimeError): await controller.search_vector_db_collection(SimpleNamespace(project_id=1),"q")
    controller.vector_db_client.search_by_vector.return_value=[RetrievedDocuments(text="x",score=1)]
    controller.reranker_client.rerank.side_effect=RuntimeError("model unavailable")
    with pytest.raises(RuntimeError): await controller.search_vector_db_collection(SimpleNamespace(project_id=1),"q")


async def test_low_score_and_empty_rag(controller,caplog):
    controller.reranker_client.rerank.return_value=[(0,-1)]
    with caplog.at_level(logging.WARNING):
        await controller.search_vector_db_collection(SimpleNamespace(project_id=1),"q")
    assert any(r.message=="rerank.low_score" for r in caplog.records)
    controller.vector_db_client.search_by_vector.return_value=[]
    result=await controller.answer_rag_query(SimpleNamespace(project_id=1),"q")
    assert result["answer"]==NO_INFORMATION and result["sources"]==[]
    controller.generation_client.generate_text.assert_not_called()


async def test_generation_usage_and_prediction_logs(controller,caplog):
    with caplog.at_level(logging.DEBUG):
        result=await controller.answer_rag_query(SimpleNamespace(project_id=1),"question")
    events={r.message:r for r in caplog.records}
    assert events["generate.done"].tokens_in==10 and events["generate.done"].tokens_out==2
    assert events["prediction.done"].retrieved_ids==[2,0]
    assert events["prediction.done"].query=="question"
    assert result["sources"][0]=={"asset_name":"report.pdf","page":3}


async def test_generation_failure_and_source_variants(controller):
    controller.search_vector_db_collection=AsyncMock(return_value=[
        RetrievedDocuments(text="x",score=1,metadata={}),
        RetrievedDocuments(text="y",score=1,metadata={"asset_name":"text.txt"}),
        RetrievedDocuments(text="z",score=1,metadata={"asset_name":"text.txt"})])
    result=await controller.answer_rag_query(SimpleNamespace(project_id=1),"q")
    assert result["sources"]==[{"asset_name":"text.txt","page":None}]
    controller.generation_client.generate_text.return_value=None
    assert await controller.answer_rag_query(SimpleNamespace(project_id=1),"q") is None
    controller.generation_client.generate_text.side_effect=RuntimeError("failed")
    with pytest.raises(RuntimeError): await controller.answer_rag_query(SimpleNamespace(project_id=1),"q")


async def test_indexing_info_reset_and_empty_embeddings(controller):
    project=SimpleNamespace(project_id=3)
    assert await controller.get_vector_db_collection_info(project)=={"ok":True}
    await controller.reset_vector_db_colection(project)
    controller.vector_db_client.delete_collection.assert_awaited_once_with(collection_name="collection_2_3")
    chunk=SimpleNamespace(chunk_text="test",chunk_metadata={"page":0},chunk_asset_id=1)
    assert await controller.index_into_vector_db(project,[chunk],[9])
    assert controller.vector_db_client.insert_many.call_args.kwargs["metadata"][0]["chunk_id"]==9
    controller.embedding_client.embed_text.return_value=[]
    assert not await controller.index_into_vector_db(project,[chunk],[9])
