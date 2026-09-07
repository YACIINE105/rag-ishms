from contextlib import asynccontextmanager
from fastapi import FastAPI
from routes import base, data, checker, nlp
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings
from stores.llm import LLMProviderFactory, CrossEncoderReranker
from stores.VectorDB import VectorDBPRoviderFactory
from stores.llm.templates import TemplateParser
from sqlalchemy.ext.asyncio import create_async_engine , AsyncSession
from sqlalchemy.orm  import sessionmaker
from utils.metrics import setup_metrics



# comments are code that is removed form the tutorial
# from dotenv import load_dotenv # before router cause router needs it to work properly
# load_dotenv(".env")

@asynccontextmanager


async def lifespan(app: FastAPI):
    # --- STARTUP LOGIC ---
    settings = get_settings()
     
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    app.db_engine = create_async_engine(postgres_conn)
    
    # Setup MongoDB
    # app.mongo_db_connection = AsyncIOMotorClient(settings.MONGO_URL)
    # app.db_client = app.mongo_db_connection[settings.MONGO_DATABASE]
    app.db_client = sessionmaker(app.db_engine,
                                 class_=AsyncSession,
                                 expire_on_commit=False)
    
    # Setup LLM Factory
    llm_provider_factory = LLMProviderFactory(settings)

    #setup vector db factory
    vector_db_provider_factory = VectorDBPRoviderFactory(settings)
    
    # Setup generation client
    app.generation_client = llm_provider_factory.create(provider=settings.GENERATION_PROVIDER)
    app.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    # Setup embedding client
    app.embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_PROVIDER)
    app.embedding_client.set_embedding_model(
        model_id=settings.EMBEDDING_MODEL_ID,
        embedding_size=settings.EMBEDDING_MODEL_SIZE
    )
    
    #setup vector db client 
    app.vector_db_client = vector_db_provider_factory.create(settings.VECTOR_DB_BACKEND)
    
    app.vector_db_client.db_client = app.db_client
    
    app.reranker_client = CrossEncoderReranker()
    
    await app.vector_db_client.connect()
    
    app.template_parser = TemplateParser(language =settings.PRIMARY_LANG,
                                         default_language = settings.DEFAULT_LANG)
    
    
    
    # Yield control back to FastAPI. The app starts serving requests here.
    yield
    
    # --- SHUTDOWN LOGIC ---
    # This block runs when the FastAPI application is stopped
    # app.mongo_db_connection.close()
    
    await app.db_engine.dispose()
    await app.vector_db_client.disconnect()


# Pass the lifespan context manager into the FastAPI instance
app = FastAPI(lifespan=lifespan)

# addiung the middleware
setup_metrics(app=app)

# Include your routers
app.include_router(base.base_router)
app.include_router(data.data_router)
# app.include_router(checker.drug_check_router)
# app.include_router(checker.isbar_gen_router)
app.include_router(nlp.nlp_router)
