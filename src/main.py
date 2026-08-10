from contextlib import asynccontextmanager
from fastapi import FastAPI
from routes import base, data, checker, nlp
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings
from stores.llm import LLMProviderFactory
from stores.VectorDB import VectorDBPRoviderFactory
from stores.llm.templates import TemplateParser



# comments are code that is removed form the tutorial
# from dotenv import load_dotenv # before router cause router needs it to work properly
# load_dotenv(".env")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP LOGIC ---
    settings = get_settings()
     
    # Setup MongoDB
    app.mongo_db_connection = AsyncIOMotorClient(settings.MONGO_URL)
    app.db_client = app.mongo_db_connection[settings.MONGO_DATABASE]
    
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
        model_id=settings.EMBEDDING_MODEL_PATH,
        embedding_size=settings.EMBEDDING_MODEL_SIZE
    )
    
    #setup vector db client 
    app.vector_db_client = vector_db_provider_factory.create(settings.VECTOR_DB_BACKEND)
    app.vector_db_client.connect()
    
    app.template_parser = TemplateParser(language =settings.PRIMARY_LANG,
                                         default_language = settings.DEFAULT_LANG)
    
    
    
    # Yield control back to FastAPI. The app starts serving requests here.
    yield
    
    # --- SHUTDOWN LOGIC ---
    # This block runs when the FastAPI application is stopped
    app.mongo_db_connection.close()
    app.vector_db_client.disconnect()


# Pass the lifespan context manager into the FastAPI instance
app = FastAPI(lifespan=lifespan)

# Include your routers
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(checker.drug_check_router)
app.include_router(checker.isbar_gen_router)
app.include_router(nlp.nlp_router)
