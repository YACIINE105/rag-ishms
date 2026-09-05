from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI , Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time





