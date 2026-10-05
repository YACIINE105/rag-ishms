"""Readiness checks without generating text or exposing dependency errors."""
import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import text

from helpers.config import Settings, get_settings
from utils.inference import run_serialized

health_router = APIRouter(tags=["health"])
logger = logging.getLogger("uvicorn.error")
CHECK_TIMEOUT = 5


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    db: Literal["ok", "error"]
    vector_db: Literal["ok", "error"]
    llm: Literal["ok", "error"]
    embedding: Literal["ok", "error"]
    reranker: Literal["ok", "error"]
    documents_indexed: int | None
    embedding_model: str | None
    version: str


def consume_check_result(task):
    # Timed-out operations may finish cancelling after the response is sent.
    if not task.cancelled():
        task.exception()


async def checked(name, operation):
    task = asyncio.create_task(operation())
    try:
        done, _ = await asyncio.wait({task}, timeout=CHECK_TIMEOUT)
        if not done:
            task.cancel()
            task.add_done_callback(consume_check_result)
            raise TimeoutError("Readiness deadline exceeded")
        return "ok", task.result()
    except asyncio.CancelledError:
        task.cancel()
        task.add_done_callback(consume_check_result)
        raise
    except Exception:
        logger.warning("Readiness check failed: %s", name)
        return "error", None


@health_router.get("/health", response_model=HealthResponse)
async def health(request: Request, response: Response,
                 settings: Settings = Depends(get_settings)):
    async def database():
        async with request.app.db_client() as session:
            await session.execute(text("SELECT 1"))

    async def vector_database():
        return await request.app.vector_db_client.get_indexed_documents_count()

    async def generation():
        provider = request.app.generation_client
        ready = await run_serialized(provider, provider.health_check, "generation")
        if not ready:
            raise RuntimeError("Generation provider unavailable")

    async def embedding():
        provider = request.app.embedding_client
        ready = await run_serialized(provider, provider.health_check, "embedding")
        if not ready:
            raise RuntimeError("Embedding provider unavailable")

    async def reranker():
        if getattr(request.app.reranker_client, "model", None) is None:
            raise RuntimeError("Reranker unavailable")

    db, vector, llm, embed, rank = await asyncio.gather(
        checked("db", database), checked("vector_db", vector_database),
        checked("llm", generation), checked("embedding", embedding),
        checked("reranker", reranker),
    )
    healthy = all(item[0] == "ok" for item in (db, vector, llm, embed, rank))
    response.status_code = 200 if healthy else 503
    response.headers["Cache-Control"] = "no-store"
    return HealthResponse(
        status="healthy" if healthy else "unhealthy",
        db=db[0], vector_db=vector[0], llm=llm[0],
        embedding=embed[0], reranker=rank[0],
        documents_indexed=vector[1],
        embedding_model=settings.EMBEDDING_MODEL_ID,
        version=settings.APP_VERSION,
    )
