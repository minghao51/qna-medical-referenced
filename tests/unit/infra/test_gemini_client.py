from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel


class _TestModel(BaseModel):
    answer: str
    confidence: float


def _gemini_response(text: str):
    return SimpleNamespace(text=text, parsed=None)


def _gemini_structured_response(parsed):
    return SimpleNamespace(text=None, parsed=parsed)


def _gemini_stream_chunk(text: str):
    return SimpleNamespace(text=text)


def _mock_settings():
    return SimpleNamespace(
        llm=SimpleNamespace(
            gemini_api_key=SimpleNamespace(get_secret_value=lambda: "test-api-key"),
            gemini_model_name="gemini-2.5-flash",
        ),
        retry=SimpleNamespace(max_retries=3, retry_delay=0.0),
    )


@pytest.fixture
def mock_genai_client():
    with patch("src.infra.llm.gemini_client.genai.Client") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.models = MagicMock()
        mock_instance.aio = MagicMock()
        mock_instance.aio.models = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


def test_gemini_client_init(mock_genai_client):
    with patch("src.infra.llm.gemini_client.settings", _mock_settings()):
        from src.infra.llm.gemini_client import GeminiClient

        client = GeminiClient()
        assert client.model == "gemini-2.5-flash"


def test_gemini_client_custom_model(mock_genai_client):
    with patch("src.infra.llm.gemini_client.settings", _mock_settings()):
        from src.infra.llm.gemini_client import GeminiClient

        client = GeminiClient(model="gemini-2.5-pro")
        assert client.model == "gemini-2.5-pro"


def test_gemini_client_generate(mock_genai_client):
    mock_genai_client.models.generate_content.return_value = _gemini_response("medical answer")
    with patch("src.infra.llm.gemini_client.settings", _mock_settings()):
        from src.infra.llm.gemini_client import GeminiClient

        client = GeminiClient()
        result = client.generate("What is LDL?", context="LDL info")

        assert result == "medical answer"
        mock_genai_client.models.generate_content.assert_called_once()


def test_gemini_client_generate_empty_raises(mock_genai_client):
    mock_genai_client.models.generate_content.return_value = _gemini_response(None)
    with patch("src.infra.llm.gemini_client.settings", _mock_settings()):
        from src.infra.llm.gemini_client import GeminiClient

        client = GeminiClient()
        with pytest.raises(Exception):
            client.generate("test")


def test_gemini_client_generate_retries(mock_genai_client):
    mock_genai_client.models.generate_content.side_effect = [
        Exception("timeout"),
        _gemini_response("retry ok"),
    ]
    with patch("src.infra.llm.gemini_client.settings", _mock_settings()):
        from src.infra.llm.gemini_client import GeminiClient

        client = GeminiClient()
        result = client.generate("test")
        assert result == "retry ok"
        assert mock_genai_client.models.generate_content.call_count == 2


def test_gemini_client_generate_structured(mock_genai_client):
    parsed = _TestModel(answer="LDL is bad cholesterol", confidence=0.95)
    mock_genai_client.models.generate_content.return_value = _gemini_structured_response(parsed)
    with patch("src.infra.llm.gemini_client.settings", _mock_settings()):
        from src.infra.llm.gemini_client import GeminiClient

        client = GeminiClient()
        result = client.generate_structured("What is LDL?", _TestModel)

        assert isinstance(result, _TestModel)
        assert result.answer == "LDL is bad cholesterol"
        assert result.confidence == 0.95


def test_gemini_client_generate_structured_empty_raises(mock_genai_client):
    mock_genai_client.models.generate_content.return_value = _gemini_structured_response(None)
    with patch("src.infra.llm.gemini_client.settings", _mock_settings()):
        from src.infra.llm.gemini_client import GeminiClient

        client = GeminiClient()
        with pytest.raises(Exception):
            client.generate_structured("test", _TestModel)


@pytest.mark.asyncio
async def test_gemini_client_a_generate(mock_genai_client):
    mock_genai_client.aio.models.generate_content = AsyncMock(
        return_value=_gemini_response("async answer")
    )
    with patch("src.infra.llm.gemini_client.settings", _mock_settings()):
        from src.infra.llm.gemini_client import GeminiClient

        client = GeminiClient()
        result = await client.a_generate("What is HDL?")

        assert result == "async answer"


@pytest.mark.asyncio
async def test_gemini_client_a_generate_structured(mock_genai_client):
    parsed = _TestModel(answer="HDL is good", confidence=0.9)
    mock_genai_client.aio.models.generate_content = AsyncMock(
        return_value=_gemini_structured_response(parsed)
    )
    with patch("src.infra.llm.gemini_client.settings", _mock_settings()):
        from src.infra.llm.gemini_client import GeminiClient

        client = GeminiClient()
        result = await client.a_generate_structured("What is HDL?", _TestModel)

        assert isinstance(result, _TestModel)
        assert result.answer == "HDL is good"


@pytest.mark.asyncio
async def test_gemini_client_a_generate_stream(mock_genai_client):
    async def fake_stream(*args, **kwargs):
        for token in ["Hello", " world", "!"]:
            yield _gemini_stream_chunk(token)

    mock_genai_client.aio.models.generate_content_stream = AsyncMock(return_value=fake_stream())
    with patch("src.infra.llm.gemini_client.settings", _mock_settings()):
        from src.infra.llm.gemini_client import GeminiClient

        client = GeminiClient()
        chunks = []
        async for token in client.a_generate_stream("test"):
            chunks.append(token)

        assert chunks == ["Hello", " world", "!"]


def test_get_client_returns_gemini_when_configured(mock_genai_client):
    with patch(
        "src.infra.llm.settings",
        SimpleNamespace(
            llm=SimpleNamespace(
                provider="gemini",
                gemini_api_key=SimpleNamespace(get_secret_value=lambda: "test-key"),
                gemini_model_name="gemini-2.5-flash",
            ),
            retry=SimpleNamespace(max_retries=3, retry_delay=0.0),
        ),
    ):
        from src.infra.llm import get_client
        from src.infra.llm.gemini_client import GeminiClient

        client = get_client()
        assert isinstance(client, GeminiClient)
