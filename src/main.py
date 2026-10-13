from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from controllers.BaseController import BaseController
from helpers.config import get_settings
from routes import base, data, health, nlp
from stores.llm import CrossEncoderReranker, LLMProviderFactory
from stores.llm.rerankers.http_reranker import HTTPReranker
from stores.llm.templates import TemplateParser
from stores.VectorDB import VectorDBPRoviderFactory
from utils.jobs import IndexJobs
from utils.logging import RequestContextMiddleware, configure_logging
from utils.metrics import setup_metrics
from utils.observability import get_client

configure_logging(get_settings().LOG_LEVEL)

# comments are code that is removed form the tutorial
# from dotenv import load_dotenv # before router cause router needs it to work properly
# load_dotenv(".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP LOGIC ---
    settings = get_settings()
    app.state.index_jobs = IndexJobs(
        Path(BaseController().base_dir) / "assets" / "jobs.json"
    )

    postgres_conn = URL.create(
        "postgresql+asyncpg",
        username=settings.POSTGRES_USERNAME,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_HOST,
        port=int(settings.POSTGRES_PORT),
        database=settings.POSTGRES_MAIN_DATABASE,
    )
    app.db_engine = create_async_engine(
        postgres_conn,
        connect_args={"timeout": 3, "command_timeout": 3},
    )

    # Setup MongoDB
    # app.mongo_db_connection = AsyncIOMotorClient(settings.MONGO_URL)
    # app.db_client = app.mongo_db_connection[settings.MONGO_DATABASE]
    app.db_client = sessionmaker(
        app.db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Setup LLM Factory
    llm_provider_factory = LLMProviderFactory(settings)

    # setup vector db factory
    vector_db_provider_factory = VectorDBPRoviderFactory(settings)

    # Setup generation client
    if getattr(settings, "GENERATION_BASE_URL", None):
        app.generation_client = llm_provider_factory.create(
            provider=settings.GENERATION_PROVIDER, role="generation"
        )
    else:
        app.generation_client = llm_provider_factory.create(
            provider=settings.GENERATION_PROVIDER
        )
    app.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    # Setup embedding client
    app.embedding_client = llm_provider_factory.create(
        provider=settings.EMBEDDING_PROVIDER
    )
    app.embedding_client.set_embedding_model(
        model_id=settings.EMBEDDING_MODEL_ID,
        embedding_size=settings.EMBEDDING_MODEL_SIZE,
    )

    # setup vector db client
    app.vector_db_client = vector_db_provider_factory.create(settings.VECTOR_DB_BACKEND)

    # PostgreSQL uses the session factory; Qdrant retains its local storage path.
    if settings.VECTOR_DB_BACKEND == "PGVector":
        app.vector_db_client.db_client = app.db_client

    if getattr(settings, "RERANKER_ENABLED", True) and getattr(
        settings, "RERANKER_BASE_URL", None
    ):
        app.reranker_client = HTTPReranker(
            base_url=settings.RERANKER_BASE_URL,
            model_name=settings.RERANKER_MODEL_ID,
            api_key=settings.RERANKER_API_KEY,
            timeout=settings.RERANKER_TIMEOUT_SECONDS,
            max_length=settings.RERANKER_MAX_LENGTH,
        )
    elif getattr(settings, "RERANKER_ENABLED", True):
        app.reranker_client = (
            CrossEncoderReranker(
                model_name=settings.RERANKER_MODEL_ID,
                batch_size=settings.RERANKER_BATCH_SIZE,
            )
            if hasattr(settings, "RERANKER_MODEL_ID")
            else CrossEncoderReranker()
        )
    else:
        app.reranker_client = None
    await app.vector_db_client.connect()

    app.template_parser = TemplateParser(
        language=settings.PRIMARY_LANG, default_language=settings.DEFAULT_LANG
    )

    try:
        yield
    finally:
        try:
            await app.vector_db_client.disconnect()
        finally:
            await app.db_engine.dispose()
            if getattr(settings, "RERANKER_BASE_URL", None) and app.reranker_client:
                app.reranker_client.close()
            client = get_client()
            if client:
                await run_in_threadpool(client.shutdown)
                get_client.cache_clear()


# Pass the lifespan context manager into the FastAPI instance
app = FastAPI(lifespan=lifespan)

# addiung the middleware
setup_metrics(app=app)
app.add_middleware(
    RequestContextMiddleware,
    access_sample_rate=get_settings().HTTP_ACCESS_LOG_SAMPLE_RATE,
)

# Include your routers
app.include_router(base.base_router)
app.include_router(data.data_router)
# app.include_router(checker.drug_check_router)
# app.include_router(checker.isbar_gen_router)
app.include_router(nlp.nlp_router)
app.include_router(health.health_router)
