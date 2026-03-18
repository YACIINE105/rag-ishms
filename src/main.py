from fastapi import FastAPI
from dotenv import load_dotenv # before router cause router needs it to work proberly
load_dotenv(".env")
from routes import base

app = FastAPI()
app.include_router(base.base_router)
