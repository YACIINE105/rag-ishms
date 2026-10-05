import asyncio
import io
import json
import logging
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.logging import (ContextJsonFormatter, RequestContextMiddleware,
                           request_id_context, project_id_context, configure_logging)
from utils.generation import GenerationText, truncate_text
from utils.inference import run_serialized


def test_json_formatter_fields_and_single_line():
    stream=io.StringIO()
    handler=logging.StreamHandler(stream)
    handler.setFormatter(ContextJsonFormatter())
    logger=logging.getLogger("test.structured")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    a=request_id_context.set("r-1"); b=project_id_context.set(42)
    try:
        logger.info("line one\nline two", extra={"tokens_in": 3})
    finally:
        request_id_context.reset(a); project_id_context.reset(b); logger.removeHandler(handler)
    lines=stream.getvalue().splitlines()
    assert len(lines)==1
    record=json.loads(lines[0])
    assert {"timestamp","level","logger","message","request_id","project_id"} <= record.keys()
    assert record["request_id"]=="r-1" and record["project_id"]==42


@pytest.mark.parametrize("incoming,expected", [("client-123","client-123"),("bad id",None),("x"*129,None)])
def test_request_id_reused_or_sanitized(incoming,expected):
    app=FastAPI()
    app.add_middleware(RequestContextMiddleware)
    @app.get("/index/answer/{project_id}")
    async def endpoint(project_id:int):
        return {"id":request_id_context.get(),"project":project_id_context.get()}
    with TestClient(app) as client:
        response=client.get("/index/answer/7", headers={"X-Request-ID":incoming})
    assert response.json()["id"]==response.headers["x-request-id"]
    assert response.json()["project"]==7
    assert response.headers["x-request-id"] != incoming if expected is None else response.headers["x-request-id"]==expected
    assert request_id_context.get() is None


async def test_concurrent_context_and_worker_propagation():
    app=FastAPI(); app.add_middleware(RequestContextMiddleware)
    @app.get("/index/answer/{project_id}")
    async def endpoint(project_id:int):
        await asyncio.sleep(0.01)
        return await run_serialized(SimpleNamespace(), lambda: [request_id_context.get(),project_id_context.get()])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
        responses=await asyncio.gather(*(client.get(f"/index/answer/{i}",headers={"X-Request-ID":f"r-{i}"}) for i in range(5)))
    assert [r.json() for r in responses]==[[f"r-{i}",i] for i in range(5)]


def test_access_sampling_never_drops_prediction_events(caplog):
    app=FastAPI(); app.add_middleware(RequestContextMiddleware,access_sample_rate=0)
    @app.get("/")
    def endpoint():
        logging.getLogger("rag.prediction").info("prediction.done",extra={"query":"q","answer":"a","retrieved_ids":[1]})
        return {}
    with caplog.at_level(logging.INFO),TestClient(app) as client:
        client.get("/")
    assert any(r.message=="prediction.done" for r in caplog.records)
    assert not any(r.message=="http.done" for r in caplog.records)


def test_exception_response_has_request_id(caplog):
    app=FastAPI(); app.add_middleware(RequestContextMiddleware)
    @app.get("/")
    def endpoint():
        raise RuntimeError("failure")
    with TestClient(app) as client:
        response=client.get("/",headers={"X-Request-ID":"error-1"})
    assert response.status_code==500 and response.headers["x-request-id"]=="error-1"


def test_configure_logging_and_truncation(caplog):
    with patch.object(logging.getLogger(),"handlers",[]), patch.object(logging.getLogger(),"level",logging.WARNING):
        configure_logging("INFO")
        assert isinstance(logging.getLogger().handlers[0].formatter,ContextJsonFormatter)
    with caplog.at_level(logging.WARNING):
        assert truncate_text("abcdef",3)=="abc"
    assert any(r.message=="query.truncated" for r in caplog.records)
    text=GenerationText("answer",5,2)
    assert str(text)=="answer" and text.tokens_in==5 and text.tokens_out==2


def test_prediction_events_survive_quiet_root_level():
    stream = io.StringIO()
    with patch.object(logging.getLogger(), "handlers", []), \
         patch.object(logging.getLogger(), "level", logging.INFO), \
         patch("utils.logging.sys.stdout", stream):
        configure_logging("ERROR")
        logging.getLogger("rag.prediction").info("prediction.done", extra={"query": "q", "answer": "a", "retrieved_ids": [1]})
    record = json.loads(stream.getvalue())
    assert record["message"] == "prediction.done"
    assert record["retrieved_ids"] == [1]
