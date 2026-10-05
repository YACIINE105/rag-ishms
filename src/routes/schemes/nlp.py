from pydantic import BaseModel, Field, StringConstraints
from typing import Optional, Annotated
from helpers.config import get_settings  # Adjust to your import path
from models.db_schems import RetrievedDocuments


settings = get_settings()


class PushRequest(BaseModel):
    do_reset: Optional[int] = 0


class SearchRequest(BaseModel):
    text: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=settings.INPUT_MAX_CHARACTERS,
        ),
    ]
    limit: Annotated[int, Field(ge=1, le=20)] = 5


class Source(BaseModel):
    asset_name: str
    page: Annotated[int, Field(ge=1)] | None = None


class AnswerResponse(BaseModel):
    signal: str
    answer: str
    sources: list[Source]
    request_id: str
    prompt_version: str


class SearchResponse(BaseModel):
    signal: str
    indexed_vectors: list[RetrievedDocuments]
