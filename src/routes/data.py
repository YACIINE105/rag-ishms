from fastapi import FastAPI, APIRouter, Depends
import os
from helpers.config import get_settings, Settings



data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"]
)

@data_router.post("/upload")

