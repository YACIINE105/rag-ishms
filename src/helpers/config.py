from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
    LANGFUSE_PROMPT_LABEL: str | None = None
    APP_ENVIRONMENT: str = "development"
    API_AUTH_ENABLED: bool = False
    API_CLIENTS: dict[str, dict] = {}
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=1, le=10000)
    RATE_LIMIT_BURST: int = Field(default=60, ge=1, le=10000)
    INDEX_BATCH_DELAY_SECONDS: float = Field(default=0, ge=0, le=60)
    GUARDRAILS_ENABLED: bool = True
    RERANK_POOL: int = Field(default=30, ge=1, le=200)
    RERANKER_ENABLED: bool = True
    RERANK_MIN_SCORE: float | None = None
    APP_NAME: str
    APP_VERSION: str
    LOG_LEVEL: str = "INFO"
    HTTP_ACCESS_LOG_SAMPLE_RATE: float = 0.1
    RERANK_WARNING_THRESHOLD: float = 0.0
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None

    FILE_ALLOWED_TYPES: list
    FILE_MAX_SIZE: int
    FILE_CHHUNK_SIZE: int  # as a limit / for memory effiency

    DEFAULT_LANG: str = "en"
    PRIMARY_LANG: str = "en"

    ################ DB CONFIG ################
    MONGO_URL: str | None = None
    MONGO_DATABASE: str | None = None

    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DATABASE: str

    ################ LLM CONFIG ################
    GENERATION_PROVIDER: str
    EMBEDDING_PROVIDER: str

    GENERATION_BASE_URL: str | None = None
    GENERATION_API_KEY: str | None = None
    RERANKER_MODEL_ID: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_BATCH_SIZE: int = Field(default=16, ge=1, le=256)
    OPENAI_BASE_URL: str = None
    OPENAI_API_KEY: str = None

    COHERE_API_KEY: str = None

    GOOGLE_AI_API_KEY: str = None

    NARA_API_KEY: str = None
    NARA_BASE_URL: str | None = None

    OPENROUTER_API_KEY: str = None
    OPENROUTER_BASE_URL: str = None

    GENERATION_MODEL_ID_LITTERAL: List[str] = None
    GENERATION_MODEL_ID: str = None
    GENERATION_MODEL_PATH: str = None
    GENERATION_MODEL_TEMPERATURE: float = None

    EMBEDDING_MODEL_ID_LITTERAL: List[str] = None
    EMBEDDING_MODEL_ID: str = None
    EMBEDDING_MODEL_PATH: str = None
    EMBEDDING_MODEL_SIZE: int = None

    INPUT_MAX_CHARACTERS: int = None
    MAX_OUTPUT_TOKENS: int = None

    LLAMA_CPP_N_GPU_LAYERS: int = 0
    LLAMA_CPP_N_CTX: int = 4096
    LLama_CPP_API_KEY: str | None = None
    LLAMA_CPP_URL: str | None = None

    ################ VECTOR DB CONFIG ################
    VECTOR_DB_BACKEND_LITTERAL: List[str] = None
    VECTOR_DB_BACKEND: str
    VECTOR_DB_DISTANCE_METRIC: str
    VECTOR_DB_PATH: str
    VECTOR_DB_PGVEC_INDEX_THRESHOLD: int

    @model_validator(mode="after")
    def validate_clients(self):
        if self.LANGFUSE_ENABLED and not (
            self.LANGFUSE_PUBLIC_KEY and self.LANGFUSE_SECRET_KEY
        ):
            raise ValueError("Langfuse keys are required when tracing is enabled")
        if self.API_AUTH_ENABLED and not self.API_CLIENTS:
            raise ValueError("API_CLIENTS is required when authentication is enabled")
        for key, client in self.API_CLIENTS.items():
            if (
                len(key) < 24
                or not isinstance(client.get("user_id"), str)
                or not client["user_id"].strip()
            ):
                raise ValueError(
                    "API clients require keys of at least 24 characters and a user_id"
                )
            projects = client.get("projects")
            if (
                not isinstance(projects, list)
                or not projects
                or (
                    projects != ["*"]
                    and any(type(p) is not int or p < 1 for p in projects)
                )
            ):
                raise ValueError('API clients require positive project IDs or ["*"]')
        return self

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
