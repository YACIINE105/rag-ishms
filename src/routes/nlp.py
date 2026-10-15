import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from controllers import NLPController
from controllers.BaseController import BaseController
from helpers.config import get_settings
from models import ChunkModel, ProjectModel
from models.enums import ResponseSignal
from utils.feedback import receipts, save_feedback
from utils.jobs import get_jobs, reserve_project
from utils.logging import request_id_context
from utils.security import authorize

from .schemes import (
    AnswerResponse,
    PushRequest,
    SearchRequest,
    SearchResponse,
)

logger = logging.getLogger("uvicorn.error")


nlp_router = APIRouter(
    prefix="/api/v1/nlp", tags=["api_v1", "nlp"], dependencies=[Depends(authorize)]
)


@nlp_router.post("/index/push/{project_id}", dependencies=[Depends(reserve_project)])
async def index_project(request: Request, project_id: int, push_request: PushRequest):
    do_reset = push_request.do_reset

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.PROJECT_NOT_FOUND_ERROR.value},
        )

    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)

    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        reranker_client=request.app.reranker_client,
    )

    has_records = True
    page_number = 1
    inserted_items_count = 0
    idx = 0
    batch_delay = get_settings().INDEX_BATCH_DELAY_SECONDS
    batch_size = get_settings().INDEX_BATCH_SIZE

    collection_name = nlp_controller.create_collection_name(
        project_id=project.project_id
    )
    # creating collection
    _ = await request.app.vector_db_client.create_collection(
        collection_name=collection_name,
        embedding_size=request.app.embedding_client.embedding_size,
        do_reset=do_reset,
    )

    # setup batching
    total_records_count = await chunk_model.get_all_chunks_count(
        project_id=project.project_id
    )

    logger.info("index.started", extra={"total_chunks": total_records_count})

    while has_records:
        page_chunks = await chunk_model.get_project_chunks(
            project_id=project.project_id, page_number=page_number, page_size=batch_size
        )

        if not page_chunks or len(page_chunks) == 0:
            has_records = False
            break

        chunks_ids = [chunk.chunk_id for chunk in page_chunks]

        idx += len(page_chunks)
        is_inserted = await nlp_controller.index_into_vector_db(
            project=project,
            chunks=page_chunks,
            chunks_ids=chunks_ids,
            do_reset=False,
        )
        page_number += 1

        if not is_inserted:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"signal": ResponseSignal.INSERT_INTO_VECTOR_DB_ERROR.value},
            )

        logger.info(
            "index.batch.done",
            extra={
                "batch_chunks": len(page_chunks),
                "indexed_chunks": inserted_items_count + len(page_chunks),
                "total_chunks": total_records_count,
            },
        )

        inserted_items_count += len(page_chunks)
        if batch_delay:
            await asyncio.sleep(batch_delay)

    # indexing created vectors

    _ = await request.app.vector_db_client.create_vector_index(
        collection_name=collection_name,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseSignal.INSERT_INTO_VECTOR_DB_SUCCESS.value,
            "inserted_items_count": inserted_items_count,
        },
    )


@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: int):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.PROJECT_NOT_FOUND_ERROR.value},
        )

    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        reranker_client=request.app.reranker_client,
    )

    collection_info = await nlp_controller.get_vector_db_collection_info(
        project=project
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseSignal.VECTOR_DB_COLLECTION_RETRIEVED.value,
            "collection_info": collection_info,
        },
    )


@nlp_router.post(
    "/index/search/{project_id}",
    response_model=SearchResponse,
)
async def search_index(
    request: Request, project_id: int, search_request: SearchRequest
):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.PROJECT_NOT_FOUND_ERROR.value},
        )

    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        reranker_client=request.app.reranker_client,
    )

    indexed_vectors = await nlp_controller.search_vector_db_collection(
        project=project, text=search_request.text, limit=search_request.limit
    )

    return SearchResponse(
        signal=ResponseSignal.VECTORS_SEARCH_Success.value,
        indexed_vectors=indexed_vectors,
    )


@nlp_router.post(
    "/index/answer/{project_id}",
    response_model=AnswerResponse,
    response_model_exclude_unset=True,
)
async def answer_index(
    request: Request, project_id: int, search_request: SearchRequest
):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.PROJECT_NOT_FOUND_ERROR.value},
        )

    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        reranker_client=request.app.reranker_client,
    )

    result = await nlp_controller.answer_rag_query(
        project=project,
        query=search_request.text,
        limit=search_request.limit,
    )

    if result is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.RAG_ANSWER_FAILED.value,
            },
        )

    answer_request_id = request_id_context.get() or str(uuid4())
    receipts(request.app).remember(
        answer_request_id, project_id, request.state.identity["user_id"]
    )
    return AnswerResponse(
        signal=ResponseSignal.RAG_ANSWER_SUCCESS.value,
        answer=result["answer"],
        sources=result["sources"],
        request_id=answer_request_id,
        prompt_version=result["prompt_version"],
    )


@nlp_router.post("/index/jobs/{project_id}", status_code=202)
async def start_index_job(
    request: Request,
    project_id: int,
    push_request: PushRequest,
    background_tasks: BackgroundTasks,
):
    jobs = get_jobs(request.app)
    try:
        job = jobs.submit(project_id)
    except ValueError as error:
        return JSONResponse(status_code=409, content={"detail": str(error)})
    background_tasks.add_task(
        jobs.run, job["job_id"], index_project, request, project_id, push_request
    )
    return dict(job)


@nlp_router.get("/index/status/{job_id}")
async def index_job_status(request: Request, job_id: str):
    jobs = getattr(request.app.state, "index_jobs", None)
    if jobs is None or job_id not in jobs.records:
        return JSONResponse(
            status_code=404, content={"detail": "Job not found or server restarted"}
        )
    return dict(jobs.records[job_id])


@nlp_router.post("/index/answer/stream/{project_id}")
async def stream_answer(
    request: Request, project_id: int, search_request: SearchRequest
):
    import json

    from fastapi.responses import StreamingResponse

    if not callable(getattr(request.app.generation_client, "stream_text", None)):
        return JSONResponse(
            status_code=501,
            content={
                "detail": "Streaming requires an OpenAI-compatible generation provider"
            },
        )
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)
    if not project:
        return JSONResponse(status_code=404, content={"detail": "Project not found"})
    controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        reranker_client=request.app.reranker_client,
    )
    result = await controller.answer_rag_query(
        project, search_request.text, search_request.limit, stream=True
    )
    request_id = request_id_context.get() or str(uuid4())

    def events():
        yield (
            "event: sources\ndata: "
            + json.dumps(
                {
                    "sources": result["sources"],
                    "request_id": request_id,
                    "prompt_version": result["prompt_version"],
                }
            )
            + "\n\n"
        )
        iterator = result.get("stream")
        try:
            if iterator is None:
                yield (
                    "event: token\ndata: "
                    + json.dumps({"text": result["answer"]})
                    + "\n\n"
                )
            else:
                for token in iterator:
                    yield "event: token\ndata: " + json.dumps({"text": token}) + "\n\n"
            receipts(request.app).remember(
                request_id, project_id, request.state.identity["user_id"]
            )
            yield "event: done\ndata: {}\n\n"
        except Exception:
            logger.exception("generate.stream.failed")
            yield 'event: error\ndata: {"detail":"Generation failed"}\n\n'
        finally:
            if iterator is not None:
                iterator.close()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class FeedbackRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    score: float = Field(ge=-1, le=1, allow_inf_nan=False)
    comment: str = Field(default="", max_length=1500)


@nlp_router.post("/answer/feedback/{project_id}")
async def answer_feedback(request: Request, project_id: int, feedback: FeedbackRequest):
    user_id = request.state.identity["user_id"]
    receipts(request.app).require(feedback.request_id, project_id, user_id)
    return await run_in_threadpool(
        save_feedback,
        Path(BaseController().base_dir) / "assets" / "feedback.jsonl",
        feedback.request_id,
        project_id,
        user_id,
        feedback.score,
        feedback.comment,
    )
