from contextlib import asynccontextmanager
from fastapi import FastAPI
from routes import base, data, checker
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings
from stores.llm import LLMProviderFactory

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

    # Setup generation client
    app.generation_client = llm_provider_factory.create(provider=settings.GENERATION_PROVIDER)
    app.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    # Setup embedding client
    app.embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_PROVIDER)
    app.embedding_client.set_embedding_model(
        settings.EMBEDDING_MODEL_ID, 
        embedding_size=settings.EMBEDDING_MODEL_SIZE
    )
    
    # Yield control back to FastAPI. The app starts serving requests here.
    yield
    
    # --- SHUTDOWN LOGIC ---
    # This block runs when the FastAPI application is stopped
    app.mongo_db_connection.close()


# Pass the lifespan context manager into the FastAPI instance
app = FastAPI(lifespan=lifespan)

# Include your routers
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(checker.drug_check_router)
app.include_router(checker.isbar_gen_router)
