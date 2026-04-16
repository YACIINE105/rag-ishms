from fastapi import FastAPI
# comments are code that is removed form the tutorial
# from dotenv import load_dotenv # before router cause router needs it to work proberly
# load_dotenv(".env")
from routes import base , data, checker


app = FastAPI()
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(checker.check_router)


