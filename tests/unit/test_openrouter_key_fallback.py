from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from openai import APIError, APIStatusError, OpenAI, RateLimitError
from pydantic import SecretStr, ValidationError

from helpers.config import Settings
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.llm.providers.OpenAIProvider import OpenAIProvider


def required_settings():
    return {
        "APP_NAME": "test",
        "APP_VERSION": "test",
        "FILE_ALLOWED_TYPES": ["application/pdf"],
        "FILE_MAX_SIZE": 1,
        "FILE_CHHUNK_SIZE": 1024,
        "POSTGRES_USERNAME": "test",
        "POSTGRES_PASSWORD": "test",
        "POSTGRES_HOST": "db",
        "POSTGRES_PORT": 5432,
        "POSTGRES_MAIN_DATABASE": "test",
        "GENERATION_PROVIDER": "OPENAI",
        "EMBEDDING_PROVIDER": "OPENAI",
        "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
        "OPENAI_API_KEY": "legacy",
        "COHERE_API_KEY": "",
        "GOOGLE_AI_API_KEY": "",
        "NARA_API_KEY": "",
        "OPENROUTER_API_KEY": "",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "GENERATION_MODEL_ID_LITTERAL": [],
        "GENERATION_MODEL_ID": "test-generation",
        "GENERATION_MODEL_PATH": "",
        "GENERATION_MODEL_TEMPERATURE": 0.2,
        "EMBEDDING_MODEL_ID_LITTERAL": [],
        "EMBEDDING_MODEL_ID": "test-embedding",
        "EMBEDDING_MODEL_PATH": "",
        "EMBEDDING_MODEL_SIZE": 2,
        "INPUT_MAX_CHARACTERS": 100,
        "MAX_OUTPUT_TOKENS": 100,
        "VECTOR_DB_BACKEND_LITTERAL": [],
        "VECTOR_DB_BACKEND": "PGVector",
        "VECTOR_DB_DISTANCE_METRIC": "cosine",
        "VECTOR_DB_PATH": "test",
        "VECTOR_DB_PGVEC_INDEX_THRESHOLD": 100,
        "API_AUTH_ENABLED": False,
    }


def test_key_list_loads_from_env_without_exposing_values(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEYS", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY_INDEX", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        'OPENROUTER_API_KEYS=\'["first-private-key","second-private-key"]\'\n'
        "OPENROUTER_API_KEY_INDEX=1\n"
    )
    settings = Settings(_env_file=env_file, **required_settings())
    assert settings.OPENROUTER_API_KEY_INDEX == 1
    assert [key.get_secret_value() for key in settings.OPENROUTER_API_KEYS] == [
        "first-private-key",
        "second-private-key",
    ]
    assert "first-private-key" not in repr(settings)
    assert "second-private-key" not in settings.model_dump_json()


@pytest.mark.parametrize(
    "keys,index", [(["private-key"], -1), (["private-key"], 1), ([], 1), ([" "], 0)]
)
def test_invalid_key_selection_does_not_echo_credentials(keys, index):
    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            OPENROUTER_API_KEYS=keys,
            OPENROUTER_API_KEY_INDEX=index,
            **required_settings(),
        )
    assert "private-key" not in str(error.value)
    assert "OPENROUTER_API_KEY" in str(error.value)


@pytest.mark.parametrize(
    "role,url,generation_key,expected_keys,expected_key",
    [
        (
            "embedding",
            "https://openrouter.ai/api/v1/",
            None,
            ["second", "first"],
            "second",
        ),
        ("embedding", "https://integrate.api.nvidia.com/v1", None, None, "legacy"),
        (
            "generation",
            "https://openrouter.ai/api/v1",
            "local-private",
            None,
            "local-private",
        ),
        (
            "generation",
            "https://openrouter.ai/api/v1",
            None,
            ["second", "first"],
            "second",
        ),
    ],
)
def test_factory_selects_only_the_matching_endpoint(
    role, url, generation_key, expected_keys, expected_key
):
    settings = SimpleNamespace(
        OPENAI_API_KEY="legacy",
        OPENAI_BASE_URL=url,
        OPENROUTER_API_KEYS=[SecretStr("first"), SecretStr("second")],
        OPENROUTER_API_KEY_INDEX=1,
        GENERATION_BASE_URL="http://local-vllm:8001/v1" if generation_key else None,
        GENERATION_API_KEY=generation_key,
    )
    with patch("stores.llm.LLMProviderFactory.OpenAIProvider") as provider:
        LLMProviderFactory(settings).create("OPENAI", role=role)
    assert provider.call_args.kwargs["api_key"] == expected_key
    assert provider.call_args.kwargs["api_keys"] == expected_keys
    expected_url = settings.GENERATION_BASE_URL or url if role == "generation" else url
    assert provider.call_args.kwargs["api_url"] == expected_url


def test_factory_without_key_list_keeps_existing_credentials():
    settings = SimpleNamespace(
        OPENAI_API_KEY="legacy", OPENAI_BASE_URL="https://openrouter.ai/api/v1"
    )
    with patch("stores.llm.LLMProviderFactory.OpenAIProvider") as provider:
        LLMProviderFactory(settings).create("OPENAI")
    assert provider.call_args.kwargs["api_key"] == "legacy"
    assert provider.call_args.kwargs["api_keys"] is None


@pytest.fixture
def make_provider():
    clients = []

    def create(handler, keys=None):
        keys = keys or ["first-private", "second-private"]
        client = OpenAI(
            api_key=keys[0],
            base_url="https://openrouter.ai/api/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        clients.append(client)
        with patch("stores.llm.providers.OpenAIProvider.OpenAI", return_value=client):
            provider = OpenAIProvider(api_key=keys[0], api_keys=keys)
        provider.set_embedding_model("unchanged-model", 2)
        provider.set_generation_model("unchanged-generator")
        return provider

    yield create
    for client in clients:
        client.close()


def embedding_response():
    return httpx.Response(
        200,
        json={
            "object": "list",
            "model": "unchanged-model",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        },
    )


@pytest.mark.parametrize("status", [402, 429, 403])
def test_limit_uses_next_key_and_remembers_success(make_provider, caplog, status):
    headers = []

    def handler(request):
        authorization = request.headers["authorization"]
        headers.append(authorization)
        if authorization == "Bearer first-private":
            return httpx.Response(
                status,
                json={
                    "error": {
                        "message": "Limit",
                        "metadata": {"limit_source": "openrouter_key_limit"},
                    }
                },
            )
        return embedding_response()

    provider = make_provider(handler)
    assert provider.embed_text(["one"], input_type="passage") == [[0.1, 0.2]]
    assert provider.embed_text("query", input_type="query") == [[0.1, 0.2]]
    assert headers == [
        "Bearer first-private",
        "Bearer second-private",
        "Bearer second-private",
    ]
    assert "first-private" not in caplog.text
    assert "second-private" not in caplog.text


def test_exhausted_keys_are_each_tried_once(make_provider):
    headers = []

    def handler(request):
        headers.append(request.headers["authorization"])
        return httpx.Response(429, json={"error": {"message": "Daily quota"}})

    provider = make_provider(handler, ["first", "second", "third", "first"])
    with pytest.raises(RateLimitError):
        provider.embed_text("document")
    assert headers == ["Bearer first", "Bearer second", "Bearer third"]


@pytest.mark.parametrize("status", [400, 401, 403, 500])
def test_other_failures_do_not_cycle_keys(make_provider, status):
    headers = []

    def handler(request):
        headers.append(request.headers["authorization"])
        return httpx.Response(status, json={"error": {"message": "Other failure"}})

    provider = make_provider(handler)
    with pytest.raises(APIStatusError):
        provider.embed_text("document")
    assert headers == ["Bearer first-private"]


def test_stream_can_fallback_before_any_output(make_provider):
    headers = []

    def handler(request):
        headers.append(request.headers["authorization"])
        if len(headers) == 1:
            return httpx.Response(429, json={"error": {"message": "Limit"}})
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            text='data: {"choices":[{"index":0,"delta":{"content":"answer"}}]}\n\n'
            "data: [DONE]\n\n",
        )

    provider = make_provider(handler)
    assert list(provider.stream_text("question")) == ["answer"]
    assert headers == ["Bearer first-private", "Bearer second-private"]


def test_stream_does_not_replay_after_output_starts(make_provider):
    headers = []

    def handler(request):
        headers.append(request.headers["authorization"])
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            text='data: {"choices":[{"index":0,"delta":{"content":"partial"}}]}\n\n'
            'data: {"error":{"message":"Limit during stream","code":429}}\n\n',
        )

    provider = make_provider(handler)
    stream = provider.stream_text("question")
    assert next(stream) == "partial"
    with pytest.raises(APIError, match="Limit during stream"):
        next(stream)
    assert headers == ["Bearer first-private"]


@pytest.mark.parametrize("role", ["generation", "embedding"])
def test_health_uses_the_successful_key(make_provider, role):
    headers = []

    def handler(request):
        headers.append(request.headers["authorization"])
        if request.headers["authorization"] == "Bearer first-private":
            return httpx.Response(429, json={"error": {"message": "Limit"}})
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"object": "list", "data": []})
        return embedding_response()

    provider = make_provider(handler)
    assert provider.embed_text("document") == [[0.1, 0.2]]
    assert provider.health_check(role)
    assert headers == [
        "Bearer first-private",
        "Bearer second-private",
        "Bearer second-private",
    ]


def test_generation_fallback_keeps_usage(make_provider):
    headers = []

    def handler(request):
        headers.append(request.headers["authorization"])
        if len(headers) == 1:
            return httpx.Response(429, json={"error": {"message": "Limit"}})
        return httpx.Response(
            200,
            json={
                "id": "test-response",
                "object": "chat.completion",
                "created": 0,
                "model": "unchanged-generator",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "answer"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                },
            },
        )

    provider = make_provider(handler)
    answer = provider.generate_text("question")
    assert str(answer) == "answer" and answer.tokens_in == 3 and answer.tokens_out == 2
    assert headers == ["Bearer first-private", "Bearer second-private"]
