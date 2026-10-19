from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils import observability
from utils.generation import GenerationText
from utils.inference import run_serialized
from utils.logging import request_id_context


@pytest.fixture
def trace_controller():
    return SimpleNamespace(
        app_settings=SimpleNamespace(RERANK_POOL=30),
        generation_client=SimpleNamespace(generation_model_id="local-qwen"),
        get_index_metadata=lambda: {"embedding_fingerprint": "test-index"},
        create_collection_name=lambda project_id: f"collection_test_{project_id}",
        prompt_version=lambda: "rag-test",
    )


@pytest.fixture
def observation(monkeypatch):
    observation = MagicMock()

    @contextmanager
    def span(*args, **kwargs):
        yield observation

    monkeypatch.setattr(observability, "span", span)
    return observation


async def test_answer_captures_redacted_question_answer_and_sources(
    trace_controller, observation
):
    @observability.traced("answer")
    async def answer(self, project, query, limit=5):
        return {
            "answer": "Contact user@example.com",
            "sources": [{"article_number": 2}],
        }

    result = await answer(
        trace_controller, SimpleNamespace(project_id=9), "user@example.com"
    )
    assert result["answer"] == "Contact user@example.com"
    assert observation.update.call_args_list[0].kwargs == {
        "input": {"question": "[REDACTED]"}
    }
    update = observation.update.call_args.kwargs
    assert update["output"] == {
        "answer": "Contact [REDACTED]",
        "sources": [{"article_number": 2}],
    }
    assert update["metadata"]["project_id"] == 9
    assert update["metadata"]["prompt_version"] == "rag-test"


async def test_stream_root_does_not_export_or_consume_iterator(
    trace_controller, observation
):
    stream = iter(["answer"])

    @observability.traced("answer")
    async def answer(self, query):
        return {"stream": stream, "sources": []}

    result = await answer(trace_controller, "question")
    assert result["stream"] is stream
    assert observation.update.call_args.kwargs["output"] == {"sources": []}
    assert next(stream) == "answer"


@pytest.mark.parametrize("positional", [True, False])
async def test_generation_snapshots_input_before_history_mutation(
    observation, positional
):
    def generate_text(prompt, chat_history):
        chat_history.append({"role": "user", "content": prompt})
        chat_history.append({"role": "assistant", "content": "user@example.com"})
        return GenerationText("user@example.com", tokens_in=7, tokens_out=3)

    owner = SimpleNamespace(generation_model_id="local-qwen")
    history = [{"role": "system", "content": "Use the context."}]
    if positional:
        result = await run_serialized(owner, generate_text, "question", history)
    else:
        result = await run_serialized(
            owner, generate_text, prompt="question", chat_history=history
        )
    assert result == "user@example.com" and len(history) == 3
    assert observation.update.call_args_list[0].kwargs["input"] == [
        {"role": "system", "content": "Use the context."},
        {"role": "user", "content": "question"},
    ]
    assert observation.update.call_args.kwargs == {
        "output": "[REDACTED]",
        "usage_details": {"input": 7, "output": 3},
    }


async def test_export_failure_does_not_change_generation(observation, caplog):
    observation.update.side_effect = RuntimeError("Exporter unavailable")

    def generate_text(prompt):
        return GenerationText("answer", tokens_in=2, tokens_out=1)

    result = await run_serialized(SimpleNamespace(), generate_text, "question")
    assert result == "answer" and result.tokens_out == 1
    assert "observability.update.failed" in caplog.text


@pytest.mark.parametrize("fails", [False, True])
async def test_readiness_does_not_create_traces(monkeypatch, fails):
    from threading import get_ident

    caller_thread = get_ident()
    owner = SimpleNamespace()
    trace_client = MagicMock(side_effect=AssertionError("Readiness must not trace"))
    monkeypatch.setattr(observability, "get_client", trace_client)

    def health_check(service):
        assert service == "generation"
        assert get_ident() != caller_thread
        assert owner._operation_lock._is_owned()
        if fails:
            raise RuntimeError("Provider unavailable")
        return True

    if fails:
        with pytest.raises(RuntimeError, match="Provider unavailable"):
            await run_serialized(owner, health_check, "generation")
    else:
        assert await run_serialized(owner, health_check, "generation") is True
    trace_client.assert_not_called()


@pytest.fixture
def stream_client(monkeypatch):
    client = MagicMock()
    client.get_current_observation_id.return_value = "parent-id"
    monkeypatch.setattr(observability, "get_client", lambda: client)
    return client


def test_stream_capture_survives_thread_handoff_and_redacts_split_text(
    trace_controller, stream_client
):
    @observability.traced_stream
    def generate(self, prompt, history):
        yield ""
        yield "user@"
        yield "example.com"

    token = request_id_context.set("stream-request")
    try:
        stream = generate(trace_controller, "question", [])
    finally:
        request_id_context.reset(token)
    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(list, stream).result() == ["", "user@", "example.com"]
    assert stream_client.start_observation.call_args.kwargs["trace_context"] == {
        "trace_id": observability.trace_id("stream-request"),
        "parent_span_id": "parent-id",
    }
    observation = stream_client.start_observation.return_value
    updates = [call.kwargs for call in observation.update.call_args_list]
    assert updates[0]["input"] == [{"role": "user", "content": "question"}]
    first_token = [update for update in updates if "completion_start_time" in update]
    assert len(first_token) == 1
    assert isinstance(first_token[0]["completion_start_time"], datetime)
    assert first_token[0]["completion_start_time"].tzinfo is not None
    assert updates[-1]["output"] == "[REDACTED]"
    assert updates[-1]["metadata"]["completed"] is True
    observation.end.assert_called_once()


def test_stream_close_releases_provider_and_marks_partial(
    trace_controller, stream_client
):
    closed = []

    @observability.traced_stream
    def generate(self, prompt, history):
        try:
            yield "partial"
            yield "unused"
        finally:
            closed.append(True)

    stream = generate(trace_controller, "question", [])
    assert next(stream) == "partial"
    stream.close()
    assert closed == [True]
    observation = stream_client.start_observation.return_value
    updates = [call.kwargs for call in observation.update.call_args_list]
    assert any(update.get("output") == "partial" for update in updates)
    assert any(
        update.get("metadata", {}).get("completed") is False for update in updates
    )
    assert updates[-1]["level"] == "WARNING"
    observation.end.assert_called_once()


def test_stream_failure_preserves_error_and_partial_output(
    trace_controller, stream_client
):
    @observability.traced_stream
    def generate(self, prompt, history):
        yield "partial"
        raise ValueError("Sensitive provider error")

    stream = generate(trace_controller, "question", [])
    assert next(stream) == "partial"
    with pytest.raises(ValueError, match="Sensitive provider error"):
        next(stream)
    observation = stream_client.start_observation.return_value
    updates = [call.kwargs for call in observation.update.call_args_list]
    assert {"level": "ERROR", "status_message": "ValueError"} in updates
    assert updates[-1]["output"] == "partial"
    assert updates[-1]["metadata"]["completed"] is False
    observation.end.assert_called_once()


@pytest.mark.parametrize("failure", ["disabled", "start", "update", "end"])
def test_stream_export_failure_does_not_change_tokens(
    trace_controller, stream_client, monkeypatch, failure
):
    if failure == "disabled":
        monkeypatch.setattr(observability, "get_client", lambda: None)
    elif failure == "start":
        stream_client.start_observation.side_effect = RuntimeError("Unavailable")
    else:
        getattr(
            stream_client.start_observation.return_value, failure
        ).side_effect = RuntimeError("Unavailable")

    @observability.traced_stream
    def generate(self, prompt, history):
        yield "answer"

    assert list(generate(trace_controller, "question", [])) == ["answer"]
