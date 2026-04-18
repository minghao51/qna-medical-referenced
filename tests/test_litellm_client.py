from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infra.llm.litellm_client import LiteLLMClient


def _response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def _stream_chunk(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


def test_litellm_client_resolve_model_from_settings(monkeypatch):
    monkeypatch.setattr("src.infra.llm.litellm_client.settings.litellm_model", "openrouter/foo/bar")
    client = LiteLLMClient()
    assert client.model == "openrouter/foo/bar"


def test_litellm_client_resolve_model_from_openrouter_model(monkeypatch):
    monkeypatch.setattr("src.infra.llm.litellm_client.settings.litellm_model", "")
    monkeypatch.setattr("src.infra.llm.litellm_client.settings.openrouter_model", "google/gemma-4-31b-it")
    client = LiteLLMClient()
    assert client.model == "openrouter/google/gemma-4-31b-it"


def test_litellm_client_custom_model():
    client = LiteLLMClient(model="openrouter/custom-model")
    assert client.model == "openrouter/custom-model"


def test_litellm_client_generate(monkeypatch):
    client = LiteLLMClient(model="openrouter/test-model")
    mock_completion = MagicMock(return_value=_response("medical answer"))
    monkeypatch.setattr("src.infra.llm.litellm_client.litellm.completion", mock_completion)

    result = client.generate("What is LDL?", context="LDL is bad cholesterol")

    assert result == "medical answer"
    mock_completion.assert_called_once()
    call_kwargs = mock_completion.call_args
    assert call_kwargs.kwargs["model"] == "openrouter/test-model"
    assert call_kwargs.kwargs["temperature"] == 0.7
    assert call_kwargs.kwargs["max_tokens"] == 2048


def test_litellm_client_generate_retries_on_failure(monkeypatch):
    client = LiteLLMClient(model="openrouter/test-model")
    mock_completion = MagicMock(side_effect=[Exception("timeout"), _response("retry ok")])
    monkeypatch.setattr("src.infra.llm.litellm_client.litellm.completion", mock_completion)
    monkeypatch.setattr("src.infra.llm.litellm_client.time.sleep", lambda _: None)

    result = client.generate("test prompt")
    assert result == "retry ok"
    assert mock_completion.call_count == 2


def test_litellm_client_generate_raises_after_max_retries(monkeypatch):
    client = LiteLLMClient(model="openrouter/test-model")
    mock_completion = MagicMock(side_effect=Exception("persistent failure"))
    monkeypatch.setattr("src.infra.llm.litellm_client.litellm.completion", mock_completion)
    monkeypatch.setattr("src.infra.llm.litellm_client.time.sleep", lambda _: None)

    with pytest.raises(Exception, match="persistent failure"):
        client.generate("test prompt")
    assert mock_completion.call_count == 3


@pytest.mark.asyncio
async def test_litellm_client_a_generate(monkeypatch):
    client = LiteLLMClient(model="openrouter/test-model")
    mock_acompletion = AsyncMock(return_value=_response("async answer"))
    monkeypatch.setattr("src.infra.llm.litellm_client.litellm.acompletion", mock_acompletion)

    result = await client.a_generate("What is HDL?")
    assert result == "async answer"
    mock_acompletion.assert_called_once()


@pytest.mark.asyncio
async def test_litellm_client_a_generate_retries(monkeypatch):
    client = LiteLLMClient(model="openrouter/test-model")
    mock_acompletion = AsyncMock(side_effect=[Exception("fail"), _response("ok")])
    monkeypatch.setattr("src.infra.llm.litellm_client.litellm.acompletion", mock_acompletion)

    result = await client.a_generate("test")
    assert result == "ok"
    assert mock_acompletion.call_count == 2


@pytest.mark.asyncio
async def test_litellm_client_a_generate_stream(monkeypatch):
    client = LiteLLMClient(model="openrouter/test-model")

    async def fake_stream(**kwargs):
        for token in ["Hello", " world", "!"]:
            yield _stream_chunk(token)

    mock_acompletion = AsyncMock(return_value=fake_stream())
    monkeypatch.setattr("src.infra.llm.litellm_client.litellm.acompletion", mock_acompletion)

    chunks = []
    async for token in client.a_generate_stream("test"):
        chunks.append(token)

    assert chunks == ["Hello", " world", "!"]


def test_litellm_client_generate_empty_response_raises(monkeypatch):
    client = LiteLLMClient(model="openrouter/test-model")
    mock_completion = MagicMock(return_value=_response(None))
    monkeypatch.setattr("src.infra.llm.litellm_client.litellm.completion", mock_completion)
    monkeypatch.setattr("src.infra.llm.litellm_client.time.sleep", lambda _: None)

    with pytest.raises(Exception):
        client.generate("test prompt")


def test_get_client_returns_litellm_when_configured(monkeypatch):
    monkeypatch.setattr("src.infra.llm.settings.llm_provider", "litellm")
    monkeypatch.setattr("src.infra.llm.settings.litellm_model", "openrouter/test-model")

    from src.infra.llm import get_client

    client = get_client()
    assert isinstance(client, LiteLLMClient)


def test_get_client_returns_qwen_by_default():
    from src.infra.llm import QwenClient, get_client

    client = get_client()
    assert isinstance(client, QwenClient)
