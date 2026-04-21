from fastapi import FastAPI
from routes import base , data, checker
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings


# comments are code that is removed form the tutorial
# from dotenv import load_dotenv # before router cause router needs it to work proberly
# load_dotenv(".env")



app = FastAPI()

@app.on_event("startup")
async def start_db_client():
    settings = get_settings()
     
     
    app.mongo_db_connection = AsyncIOMotorClient(settings.MONGO_URL)
    app.db_client = app.mongo_db_connection[settings.MONGO_DATABASE]


@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongo_db_connection.close()

app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(checker.check_router)


