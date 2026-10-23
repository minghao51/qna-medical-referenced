"""Offline contract tests for the pydantic-ai DeepEval judge wrapper.

Every request lands on an in-memory ``httpx.MockTransport`` under the synthetic
``synthetic.invalid`` base URL with a synthetic key; no live endpoint is ever
contacted. Judge settings are patched on the real settings singleton, mirroring
``tests/unit/evals/test_judge_lifecycle.py``.
"""

import asyncio
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from pydantic import SecretStr
from pydantic_ai.exceptions import ModelHTTPError

from src.config.settings import settings
from src.evals.pydantic_ai_judge import PydanticAIJudgeModel
from src.infra.llm import pydantic_ai_client
from src.infra.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.infra.usage import capture_usage

BASE_URL = "https://synthetic.invalid/v1"
API_KEY = "synthetic-not-a-key"
MODEL = "judge-pydantic-ai-model"
PROMPT = "synthetic judge prompt: rate the answer from one to ten"

Handler = Callable[[httpx.Request], httpx.Response]


def text_completion(content: str | None) -> dict[str, Any]:
    return {
        "id": "synthetic",
        "object": "chat.completion",
        "created": 0,
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content, "refusal": None},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
    }


class _CountingTransport(httpx.MockTransport):
    """MockTransport that counts transport-level closes."""

    def __init__(self, handler: Handler) -> None:
        super().__init__(handler)
        self.close_calls = 0

    async def aclose(self) -> None:
        self.close_calls += 1
        await super().aclose()


def install_mock_transport(monkeypatch, handler: Handler) -> _CountingTransport:
    """Route the adapter's owned HTTP client onto an in-memory transport.

    The patched constructor subclasses ``httpx.AsyncClient`` so the OpenAI SDK's
    own ``isinstance`` checks still see a real client class.
    """
    transport = _CountingTransport(handler)
    real_async_client = httpx.AsyncClient

    class _MockedAsyncClient(real_async_client):  # type: ignore[misc, valid-type]
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(transport=transport, **kwargs)

    monkeypatch.setattr(pydantic_ai_client.httpx, "AsyncClient", _MockedAsyncClient)
    return transport


@pytest.fixture
def judge_settings(monkeypatch):
    """Synthetic judge settings and adapter route, restored after each test."""
    monkeypatch.setattr(settings.llm, "judge_temperature", 0.35)
    monkeypatch.setattr(settings.llm, "judge_max_tokens", 321)
    monkeypatch.setattr(settings.deepeval, "deepeval_metric_timeout_seconds", 17)
    monkeypatch.setattr(settings.llm, "judge_model_light_pydantic_ai", MODEL)
    monkeypatch.setattr(settings.llm, "pydantic_ai_base_url", BASE_URL)
    monkeypatch.setattr(settings.llm, "pydantic_ai_api_key", SecretStr(API_KEY))
    monkeypatch.setattr(settings.retry, "max_retries", 3)
    monkeypatch.setattr(settings.retry, "retry_delay", 0.0)
    return settings


@pytest.mark.asyncio
async def test_constructor_uses_judge_settings_and_requested_pydantic_ai_model(
    monkeypatch, judge_settings
):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=text_completion("synthetic verdict"))

    install_mock_transport(monkeypatch, handle)
    model = PydanticAIJudgeModel(judge_settings.llm.judge_model_light_pydantic_ai)
    try:
        judge = model.client
        assert model.get_model_name() == judge_settings.llm.judge_model_light_pydantic_ai
        assert judge.model == judge_settings.llm.judge_model_light_pydantic_ai
        assert judge._temperature == judge_settings.llm.judge_temperature
        assert judge._max_tokens == judge_settings.llm.judge_max_tokens
        assert judge._timeout == judge_settings.deepeval.deepeval_metric_timeout_seconds
        assert judge._raw_prompt is True
        # The adapter wraps AsyncOpenAI with zero SDK retries so its own bounded
        # settings.retry loop is the only retry layer.
        assert judge._openai_client.max_retries == 0

        assert await model.a_generate(PROMPT) == "synthetic verdict"
        body = json.loads(requests[0].content)
        assert body["model"] == judge_settings.llm.judge_model_light_pydantic_ai
        assert body["temperature"] == judge_settings.llm.judge_temperature
        wire_max_tokens = (
            body["max_completion_tokens"] if "max_completion_tokens" in body else body["max_tokens"]
        )
        assert wire_max_tokens == judge_settings.llm.judge_max_tokens
    finally:
        await model.aclose()


@pytest.mark.asyncio
async def test_request_body_carries_judge_prompt_verbatim_without_system_message(
    monkeypatch, judge_settings
):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=text_completion("synthetic verdict"))

    install_mock_transport(monkeypatch, handle)
    model = PydanticAIJudgeModel(MODEL)
    try:
        assert await model.a_generate(PROMPT) == "synthetic verdict"
        request = requests[0]
        body = json.loads(request.content)
        assert body["messages"] == [{"role": "user", "content": PROMPT}]
        assert all(message["role"] != "system" for message in body["messages"])
        assert "instructions" not in body
        serialized = request.content.decode()
        assert PROMPT in serialized
        assert SYSTEM_PROMPT not in serialized
        assert USER_PROMPT_TEMPLATE.splitlines()[0] not in serialized
        assert "Reference Information:" not in serialized
    finally:
        await model.aclose()


def test_generate_returns_text_and_records_usage_under_judge_role(monkeypatch, judge_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=text_completion("synthetic verdict"))

    install_mock_transport(monkeypatch, handle)
    model = PydanticAIJudgeModel(MODEL)
    try:
        with capture_usage() as captured:
            assert model.generate(PROMPT) == "synthetic verdict"
        assert len(requests) == 1
        assert captured.usage_by_role["judge"] == {
            "input_tokens": 3,
            "output_tokens": 5,
            "total_tokens": 8,
            "status": "reported",
            "source": "provider_sdk",
        }
        assert captured.unknowns == []
    finally:
        asyncio.run(model.aclose())


@pytest.mark.asyncio
async def test_a_generate_returns_text_and_records_usage_under_judge_role(
    monkeypatch, judge_settings
):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=text_completion("synthetic verdict"))

    install_mock_transport(monkeypatch, handle)
    model = PydanticAIJudgeModel(MODEL)
    model.usage_role = "judge_heavy"
    try:
        with capture_usage() as captured:
            assert await model.a_generate(PROMPT) == "synthetic verdict"
        assert len(requests) == 1
        assert captured.usage_by_role["judge_heavy"]["total_tokens"] == 8
        assert "judge" not in captured.usage_by_role
    finally:
        await model.aclose()


@pytest.mark.asyncio
async def test_non_transient_client_error_is_not_retried(monkeypatch, judge_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(400, json={"error": {"message": "synthetic"}})

    install_mock_transport(monkeypatch, handle)
    model = PydanticAIJudgeModel(MODEL)
    try:
        with pytest.raises(ModelHTTPError) as excinfo:
            await model.a_generate(PROMPT)
        assert excinfo.value.status_code == 400
        # settings.retry.max_retries is 3 here, so a retry would be visible.
        assert len(requests) == 1
        assert not model.client._http_client.is_closed
    finally:
        await model.aclose()


class _EmptyTextAgent:
    """Stub agent producing the adapter's documented empty-output condition."""

    def __init__(self) -> None:
        self.calls = 0

    async def run(self, user_prompt: str, *, model_settings: Any = None):
        self.calls += 1
        return SimpleNamespace(
            output="",
            usage=SimpleNamespace(input_tokens=1, output_tokens=0, total_tokens=1),
        )


@pytest.mark.asyncio
async def test_empty_model_output_returns_empty_string(monkeypatch, judge_settings):
    def handle(request: httpx.Request) -> httpx.Response:
        pytest.fail("empty-output fallback must not need a provider request")

    install_mock_transport(monkeypatch, handle)
    model = PydanticAIJudgeModel(MODEL)
    stub = _EmptyTextAgent()
    model.client._text_agent = cast(Any, stub)
    try:
        with capture_usage() as captured:
            assert await model.a_generate(PROMPT) == ""
        assert stub.calls == 1
        assert captured.usage_by_role["judge"]["total_tokens"] == 1
    finally:
        await model.aclose()


@pytest.mark.asyncio
async def test_close_is_noop_and_aclose_closes_owned_transport_once(monkeypatch, judge_settings):
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=text_completion("synthetic verdict"))

    transport = install_mock_transport(monkeypatch, handle)
    model = PydanticAIJudgeModel(MODEL)
    http_client = model.client._http_client

    model.close()
    assert transport.close_calls == 0
    assert not http_client.is_closed

    await model.aclose()
    assert http_client.is_closed
    assert transport.close_calls == 1

    # Repeated and nested cleanup must stay silent and must not re-close.
    await model.aclose()
    model.close()
    assert transport.close_calls == 1


@pytest.mark.parametrize(
    "unsafe_model",
    [
        "https://synthetic.invalid/v1",
        "judge@example.invalid",
        "",
        "   ",
        "model name",
        "m" * 201,
    ],
)
def test_constructor_rejects_unsafe_model_identifier(monkeypatch, judge_settings, unsafe_model):
    def build(**kwargs: Any) -> httpx.AsyncClient:
        pytest.fail("an unsafe model identifier must not build a transport")

    monkeypatch.setattr(pydantic_ai_client.httpx, "AsyncClient", build)
    with pytest.raises(ValueError, match="safe supported model name"):
        PydanticAIJudgeModel(unsafe_model)


@pytest.mark.asyncio
async def test_wrapper_public_surface_matches_existing_judge_wrappers(monkeypatch, judge_settings):
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=text_completion("synthetic verdict"))

    install_mock_transport(monkeypatch, handle)
    model = PydanticAIJudgeModel(MODEL)
    try:
        assert model.usage_role == "judge"
        assert model.name == MODEL
        assert model.model is model
        assert model.load_model() is model
        assert model.get_model_name() == MODEL
        assert model.supports_json_mode() is False
        assert model.supports_structured_outputs() is False
        assert model.supports_temperature() is True
    finally:
        await model.aclose()


@pytest.mark.asyncio
async def test_unrelated_value_errors_propagate_instead_of_becoming_empty_strings(
    monkeypatch, judge_settings
):
    install_mock_transport(monkeypatch, lambda request: httpx.Response(200, json={}))
    model = PydanticAIJudgeModel(MODEL)

    async def boom(prompt: str) -> str:
        raise ValueError("synthetic non-empty-output failure")

    monkeypatch.setattr(model.client, "a_generate", boom)
    try:
        with pytest.raises(ValueError, match="synthetic non-empty-output failure"):
            await model.a_generate(PROMPT)
    finally:
        await model.aclose()
