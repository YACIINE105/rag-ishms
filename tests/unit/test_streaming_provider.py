from types import SimpleNamespace
from unittest.mock import MagicMock

from stores.llm.providers.OpenAIProvider import OpenAIProvider


def test_real_chunks_and_close():
    provider = OpenAIProvider(api_key="test")
    provider.set_generation_model("future-model")
    response = MagicMock()
    response.__iter__.return_value = iter(
        [
            SimpleNamespace(choices=[]),
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))]
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=" world"))]
            ),
        ]
    )
    provider.client = MagicMock()
    provider.client.chat.completions.create.return_value = response
    history = [{"role": "system", "content": "grounded"}]
    assert list(provider.stream_text("question", history)) == ["hello", " world"]
    assert len(history) == 1
    assert provider.client.chat.completions.create.call_args.kwargs["stream"] is True
    response.close.assert_called_once()
