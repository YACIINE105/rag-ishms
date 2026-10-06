import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Unit/API tests must never load native models or download weights.
for module_name, class_name in (
    ("llama_cpp", "Llama"),
    ("sentence_transformers", "CrossEncoder"),
):
    module = ModuleType(module_name)
    setattr(module, class_name, MagicMock())
    sys.modules[module_name] = module

from helpers import config

SETTINGS = SimpleNamespace(
    LOG_LEVEL="INFO",
    HTTP_ACCESS_LOG_SAMPLE_RATE=0.1,
    INPUT_MAX_CHARACTERS=100,
    EMBEDDING_MODEL_ID="test-embed",
    APP_VERSION="test-version",
    APP_NAME="test",
    FILE_ALLOWED_TYPES=["application/pdf", "text/plain"],
    FILE_MAX_SIZE=1,
    FILE_CHHUNK_SIZE=1024,
    RERANK_WARNING_THRESHOLD=0.0,
    QDRANT_URL=None,
    QDRANT_API_KEY=None,
    VECTOR_DB_PATH="test-vectors",
    VECTOR_DB_DISTANCE_METRIC="cosine",
    EMBEDDING_MODEL_SIZE=2,
    VECTOR_DB_PGVEC_INDEX_THRESHOLD=2,
)
config.get_settings = lambda: SETTINGS


@pytest.fixture
def settings():
    return SETTINGS
