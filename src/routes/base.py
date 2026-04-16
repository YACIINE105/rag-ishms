from fastapi import FastAPI, APIRouter, Depends, status
from fastapi.responses import JSONResponse
import os
from helpers.config import get_settings, Settings



base_router = APIRouter(
    prefix="/api/v1",
    tags=["api_v1"]
)
@base_router.get("/")
async def welcome(app_settings : Settings =Depends(get_settings)):
    # using depends rather than app_settings directly ensures that the data source is actually available.
    # app_settings = get_settings()
    app_name = app_settings.APP_NAME
    app_version = app_settings.APP_VERSION 
    return JSONResponse(status_code=status.HTTP_200_OK,
        content={                
        "app_name" : app_name,
        "app_verion": app_version
        }
    )

