import importlib
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.parametrize("backend", ["QDRANT", "PGVector"])
async def test_lifespan_loads_once_and_releases_resources(monkeypatch, backend):
    with patch("utils.logging.configure_logging"):
        main = importlib.import_module("main")
    settings = SimpleNamespace(
        POSTGRES_USERNAME="test",
        POSTGRES_PASSWORD="p@ss%word",
        POSTGRES_HOST="db",
        POSTGRES_PORT=5432,
        POSTGRES_MAIN_DATABASE="rag",
        GENERATION_PROVIDER="OPENAI",
        EMBEDDING_PROVIDER="LLAMA_CPP",
        GENERATION_MODEL_ID="chat",
        EMBEDDING_MODEL_ID="embed",
        EMBEDDING_MODEL_SIZE=2,
        VECTOR_DB_BACKEND=backend,
        PRIMARY_LANG="en",
        DEFAULT_LANG="en",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    engine = SimpleNamespace(dispose=AsyncMock())
    create_engine = MagicMock(return_value=engine)
    monkeypatch.setattr(main, "create_async_engine", create_engine)
    sessions = MagicMock()
    monkeypatch.setattr(main, "sessionmaker", MagicMock(return_value=sessions))
    generation, embedding = MagicMock(), MagicMock()
    factory = MagicMock()
    factory.create.side_effect = [generation, embedding]
    monkeypatch.setattr(main, "LLMProviderFactory", MagicMock(return_value=factory))
    vector = SimpleNamespace(
        db_client="local", connect=AsyncMock(), disconnect=AsyncMock()
    )
    vector_factory = MagicMock()
    vector_factory.create.return_value = vector
    monkeypatch.setattr(
        main, "VectorDBPRoviderFactory", MagicMock(return_value=vector_factory)
    )
    reranker = MagicMock()
    monkeypatch.setattr(main, "CrossEncoderReranker", reranker)
    app = FastAPI()
    async with main.lifespan(app):
        assert app.generation_client is generation
        assert app.embedding_client is embedding
        assert vector.db_client == (sessions if backend == "PGVector" else "local")
        assert create_engine.call_args.args[0].password == "p@ss%word"
        vector.connect.assert_awaited_once()
        reranker.assert_called_once()
        generation.set_generation_model.assert_called_once_with(model_id="chat")
        embedding.set_embedding_model.assert_called_once_with(
            model_id="embed", embedding_size=2
        )
    vector.disconnect.assert_awaited_once()
    engine.dispose.assert_awaited_once()


def test_metrics_endpoint_and_http_correlation():
    from utils.logging import RequestContextMiddleware
    from utils.metrics import setup_metrics

    app = FastAPI()
    setup_metrics(app)
    app.add_middleware(RequestContextMiddleware, access_sample_rate=0)
    with TestClient(app) as client:
        response = client.get("/rag_ishms_metrics_v__0")
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert "http_requests_total" in response.text


def test_alembic_uses_environment_and_escapes_credentials(monkeypatch):
    from alembic.config import Config
    from sqlalchemy.engine import make_url

    from models.db_schems.rag_ishms import schemes

    monkeypatch.setitem(sys.modules, "schemes", schemes)
    for name, value in {
        "POSTGRES_HOST": "db",
        "POSTGRES_USERNAME": "test",
        "POSTGRES_PASSWORD": "p@ss%word",
        "POSTGRES_PORT": "5432",
        "POSTGRES_MAIN_DATABASE": "rag",
    }.items():
        monkeypatch.setenv(name, value)
    config = Config()
    config.set_main_option("sqlalchemy.url", "postgresql://unused")
    path = (
        Path(__file__).resolve().parents[2]
        / "src/models/db_schems/rag_ishms/alembic/env.py"
    )
    with (
        patch("alembic.context.config", config, create=True),
        patch("alembic.context.is_offline_mode", return_value=True),
        patch("alembic.context.configure") as configure,
        patch("alembic.context.begin_transaction"),
        patch("alembic.context.run_migrations") as migrate,
        patch("utils.logging.configure_logging"),
    ):
        runpy.run_path(str(path))
    url = make_url(configure.call_args.kwargs["url"])
    assert url.password == "p@ss%word"
    assert url.host == "db"
    assert url.drivername == "postgresql+psycopg2"
    migrate.assert_called_once()
