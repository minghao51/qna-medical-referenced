"""Pydantic AI adapter contract tests over in-memory fake transport only.

Every request lands on an ``httpx.MockTransport`` handler under the synthetic
``synthetic.invalid`` base URL with a synthetic key; no live endpoint is ever
contacted. The ``deny_live_models`` fixture additionally sets pydantic-ai's
``ALLOW_MODEL_REQUESTS = False`` so an accidental real request fails closed
even if the fake transport were bypassed.
"""

import asyncio
import hashlib
import json
from contextlib import aclosing, contextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import pydantic_ai.models
import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel, SecretStr
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from src.infra import llm
from src.infra.llm import pydantic_ai_client
from src.infra.llm.conversation_context import conversation_scope, opaque_session_id
from src.infra.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.infra.llm.pydantic_ai_client import PydanticAIClient
from src.infra.usage import capture_usage, usage_call

BASE_URL = "https://synthetic.invalid/v1"
API_KEY = "synthetic-not-a-key"
MODEL = "synthetic-model"
PROMPT = "synthetic prompt"
CONTEXT = "synthetic reference context"
USER_AGENT = "qna-medical-referenced/0.1.0 (pydantic-ai 2.31.0 adapter)"


def test_transient_classification_by_http_status():
    """Status-bearing errors classify by status only: 408/429/5xx transient."""
    cases = {400: False, 404: False, 418: False, 408: True, 429: True, 500: True, 503: True}
    for status, expected in cases.items():
        exc = ModelHTTPError(status_code=status, model_name=MODEL, body=None)
        assert pydantic_ai_client._is_transient(exc) is expected, status


def test_transient_classification_connection_level_model_api_error():
    """Status-less connection-level ModelAPIError stays transient."""
    exc = ModelAPIError(model_name=MODEL, message="synthetic connection failure")
    assert pydantic_ai_client._is_transient(exc) is True


def test_transient_classification_timeout_and_httpx_errors():
    assert pydantic_ai_client._is_transient(TimeoutError("synthetic timeout")) is True
    assert pydantic_ai_client._is_transient(httpx.ConnectTimeout("synthetic")) is True
    assert pydantic_ai_client._is_transient(ValueError("synthetic local error")) is False


STREAM_HEADERS = {"content-type": "text/event-stream"}


class Answer(BaseModel):
    answer: str


def fake_settings(mode: str = "tool", max_retries: int = 3, retry_delay: float = 0.0):
    return SimpleNamespace(
        llm=SimpleNamespace(
            pydantic_ai_model=MODEL,
            pydantic_ai_base_url=BASE_URL,
            pydantic_ai_api_key=SecretStr(API_KEY),
            pydantic_ai_temperature=0.7,
            pydantic_ai_max_tokens=2048,
            pydantic_ai_timeout_seconds=30.0,
            pydantic_ai_structured_output_mode=mode,
        ),
        retry=SimpleNamespace(max_retries=max_retries, retry_delay=retry_delay),
    )


@pytest.fixture
def adapter_settings(monkeypatch):
    config = fake_settings()
    monkeypatch.setattr(pydantic_ai_client, "settings", config)
    return config


def make_client(handler) -> PydanticAIClient:
    """Build a PydanticAIClient whose HTTP client rides a MockTransport."""
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sdk = AsyncOpenAI(
        base_url=BASE_URL, api_key=API_KEY, http_client=http, max_retries=0, timeout=30.0
    )
    model = OpenAIChatModel(MODEL, provider=OpenAIProvider(openai_client=sdk))
    client = PydanticAIClient.__new__(PydanticAIClient)
    client.model = MODEL
    client._temperature = 0.7
    client._max_tokens = 2048
    client._raw_prompt = False
    client._timeout = 30.0
    client._http_client = http
    client._openai_client = sdk
    client._model = model
    client._text_agent = Agent(model, instructions=SYSTEM_PROMPT)
    client._structured_agents = {}
    return client


def sse_chunk(delta: dict[str, Any] | None, *, finish: str | None = None, **extra: Any) -> str:
    payload: dict[str, Any] = {
        "id": "synthetic",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": MODEL,
        "choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}],
    }
    payload.update(extra)
    return "data: " + json.dumps(payload) + "\n\n"


def sse_stream_bytes(*deltas: str, usage: dict[str, int] | None = None) -> bytes:
    parts = [sse_chunk({"content": delta}) for delta in deltas]
    parts.append(sse_chunk({}, finish="stop"))
    if usage is not None:
        parts.append(sse_chunk(None, choices=[], usage=usage))
    parts.append("data: [DONE]\n\n")
    return "".join(parts).encode("utf-8")


class SseBody(httpx.AsyncByteStream):
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def __aiter__(self):
        yield self._payload


class BlockedAfterFirstDelta(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = asyncio.Event()

    async def __aiter__(self):
        yield sse_chunk({"content": "prefix"}).encode("utf-8")
        await asyncio.Event().wait()

    async def aclose(self):
        self.closed.set()


class BrokenAfterFirstDelta(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield sse_chunk({"content": "prefix"}).encode("utf-8")
        raise httpx.RemoteProtocolError("synthetic mid-stream failure")


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


def tool_completion(arguments: str) -> dict[str, Any]:
    return {
        "id": "synthetic",
        "object": "chat.completion",
        "created": 0,
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "refusal": None,
                    "tool_calls": [
                        {
                            "id": "call_synthetic",
                            "type": "function",
                            "function": {"name": "final_result", "arguments": arguments},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 7, "completion_tokens": 9, "total_tokens": 16},
    }


@contextmanager
def denied_model_requests():
    original = pydantic_ai.models.ALLOW_MODEL_REQUESTS
    pydantic_ai.models.ALLOW_MODEL_REQUESTS = False
    try:
        yield
    finally:
        pydantic_ai.models.ALLOW_MODEL_REQUESTS = original


@pytest.fixture
def deny_live_models():
    with denied_model_requests():
        yield


@pytest.mark.asyncio
async def test_a_generate_reproduces_prompt_messages_and_request_settings(adapter_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=text_completion("synthetic answer"))

    client = make_client(handle)
    try:
        assert await client.a_generate(PROMPT, context=CONTEXT) == "synthetic answer"
        assert len(requests) == 1
        request = requests[0]
        assert str(request.url) == f"{BASE_URL}/chat/completions"
        assert request.headers["user-agent"] == USER_AGENT
        assert request.headers["user-agent"] != "pydantic-ai/2.31.0"
        assert request.headers["authorization"] == f"Bearer {API_KEY}"
        assert "x-opencode-session" not in request.headers
        body = json.loads(request.content)
        assert body["model"] == MODEL
        assert body["temperature"] == adapter_settings.llm.pydantic_ai_temperature
        wire_max_tokens = (
            body["max_completion_tokens"] if "max_completion_tokens" in body else body["max_tokens"]
        )
        assert wire_max_tokens == adapter_settings.llm.pydantic_ai_max_tokens
        assert body["messages"] == [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(context=CONTEXT, prompt=PROMPT),
            },
        ]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_session_header_is_stable_per_conversation_and_absent_outside_scope(
    adapter_settings,
):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=text_completion("ok"))

    client = make_client(handle)
    try:
        with conversation_scope("user-123"):
            await client.a_generate(PROMPT)
            await client.a_generate(PROMPT)
        with conversation_scope("user-456"):
            await client.a_generate(PROMPT)
        await client.a_generate(PROMPT)

        sessions = [request.headers.get("x-opencode-session") for request in requests]
        assert sessions[0] == sessions[1] == opaque_session_id("user-123")
        assert sessions[0] == "qna-" + hashlib.sha256(b"user-123").hexdigest()[:16]
        assert sessions[2] == opaque_session_id("user-456")
        assert sessions[2] != sessions[0]
        assert sessions[3] is None
        # Per-request headers never mutate the shared client defaults.
        assert client._http_client.headers.get("x-opencode-session") is None
        assert "x-opencode-session" not in client._openai_client.default_headers
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_yields_deltas_individually_and_accumulates(adapter_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers=STREAM_HEADERS,
            stream=SseBody(
                sse_stream_bytes(
                    "Hel",
                    "lo ",
                    "world",
                    usage={"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
                )
            ),
        )

    client = make_client(handle)
    try:
        deltas = [token async for token in client.a_generate_stream(PROMPT, context=CONTEXT)]
        assert len(deltas) >= 2
        assert "".join(deltas) == "Hello world"
        assert len(requests) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_failure_after_first_delta_is_never_retried(adapter_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, headers=STREAM_HEADERS, stream=BrokenAfterFirstDelta())

    client = make_client(handle)
    try:
        generator = client.a_generate_stream(PROMPT, context=CONTEXT)
        assert await anext(generator) == "prefix"
        with pytest.raises(Exception):
            async for _ in generator:
                pass
        assert len(requests) == 1  # No partial-output retry after a delta was emitted.
    finally:
        await generator.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_transient_failure_before_first_delta_is_retried(adapter_settings):
    requests: list[httpx.Request] = []
    state = {"failed": True}

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if state["failed"]:
            state["failed"] = False
            return httpx.Response(500, json={"error": {"message": "synthetic"}})
        return httpx.Response(
            200,
            headers=STREAM_HEADERS,
            stream=SseBody(sse_stream_bytes("a", "b")),
        )

    client = make_client(handle)
    try:
        deltas = [token async for token in client.a_generate_stream(PROMPT, context=CONTEXT)]
        assert deltas == ["a", "b"]
        assert len(requests) == 2  # One retried 500, then success.
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_stream_cancellation_keeps_owned_client_usable(adapter_settings):
    requests: list[httpx.Request] = []
    state = {"blocked": True}
    blocked_body: BlockedAfterFirstDelta | None = None

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal blocked_body
        requests.append(request)
        if state["blocked"]:
            blocked_body = BlockedAfterFirstDelta()
            return httpx.Response(200, headers=STREAM_HEADERS, stream=blocked_body)
        return httpx.Response(200, json=text_completion("usable again"))

    client = make_client(handle)
    try:
        # pydantic-ai streams use anyio cancel scopes bound to the task that
        # opened them: the stream must be consumed by ONE task (the chat use
        # case consumes `a_generate_stream` in a single task), so cancel that
        # consuming task itself while it is parked awaiting the next upstream
        # chunk — mirroring the production `aclosing` cleanup boundary.
        first_delta = asyncio.Event()
        seen: list[str] = []

        async def consume() -> None:
            async with aclosing(client.a_generate_stream(PROMPT, context=CONTEXT)) as stream:
                async for delta in stream:
                    seen.append(delta)
                    first_delta.set()

        task = asyncio.create_task(consume())
        await asyncio.wait_for(first_delta.wait(), timeout=5)
        await asyncio.sleep(0.05)  # let the consumer park inside the blocked read
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert seen == ["prefix"]
        # The cancelled stream must have released the blocked transport body.
        assert blocked_body is not None
        assert blocked_body.closed.is_set()
        assert not client._http_client.is_closed
        state["blocked"] = False
        assert await client.a_generate(PROMPT, context=CONTEXT) == "usable again"
        assert len(requests) == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_structured_tool_mode_sends_tools_validates_and_records_usage(adapter_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, json=tool_completion(json.dumps({"answer": "synthetic structured"}))
        )

    client = make_client(handle)
    try:
        with capture_usage() as captured:
            result = await client.a_generate_structured(PROMPT, Answer, context=CONTEXT)
        assert result == Answer(answer="synthetic structured")
        body = json.loads(requests[0].content)
        assert body["tools"], "tool mode must advertise the structured-output tool"
        assert body["tools"][0]["function"]["name"] == "final_result"
        assert "response_format" not in body
        usage = captured.usage_by_role["generation"]
        assert usage["total_tokens"] == 16
        assert usage["status"] == "reported"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_structured_tool_mode_invalid_arguments_fail_closed(adapter_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=tool_completion(json.dumps({"answer": 123})))

    client = make_client(handle)
    try:
        with pytest.raises(UnexpectedModelBehavior):
            await client.a_generate_structured(PROMPT, Answer, context=CONTEXT)
        # Bounded framework output retries happened, then the run failed loudly.
        assert len(requests) >= 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_structured_native_json_schema_mode_selected_from_settings_and_validates(
    monkeypatch,
):
    monkeypatch.setattr(pydantic_ai_client, "settings", fake_settings(mode="native-json-schema"))
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=text_completion(json.dumps({"answer": "native answer"})))

    client = make_client(handle)
    try:
        result = await client.a_generate_structured(PROMPT, Answer, context=CONTEXT)
        assert result == Answer(answer="native answer")
        body = json.loads(requests[0].content)
        assert body["response_format"]["type"] == "json_schema"
        assert "answer" in json.dumps(body["response_format"]["json_schema"]["schema"])
        assert not body.get("tools")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_nonstream_transient_500_is_retried_then_succeeds(adapter_settings):
    requests: list[httpx.Request] = []
    state = {"failed": True}

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if state["failed"]:
            state["failed"] = False
            return httpx.Response(500, json={"error": {"message": "synthetic"}})
        return httpx.Response(200, json=text_completion("recovered"))

    client = make_client(handle)
    try:
        assert await client.a_generate(PROMPT, context=CONTEXT) == "recovered"
        assert len(requests) == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_nonstream_400_fails_immediately_without_retry(adapter_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(400, json={"error": {"message": "synthetic"}})

    client = make_client(handle)
    try:
        with pytest.raises(ModelHTTPError) as excinfo:
            await client.a_generate(PROMPT, context=CONTEXT)
        assert excinfo.value.status_code == 400
        assert len(requests) == 1
    finally:
        await client.aclose()


class _EmptyRunAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, user_prompt: str, *, model_settings: Any = None):
        self.calls += 1
        return SimpleNamespace(
            output="",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1, total_tokens=2),
        )


@pytest.mark.asyncio
async def test_empty_output_raises_value_error(adapter_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        pytest.fail("empty-output guard must not require a provider request")

    client = make_client(handle)
    stub = _EmptyRunAgent()
    client._text_agent = stub
    try:
        with capture_usage() as captured:
            with pytest.raises(ValueError, match="Empty response from Pydantic AI adapter"):
                await client.a_generate(PROMPT, context=CONTEXT)
        assert stub.calls == 1
        assert requests == []
        assert captured.usage_by_role["generation"]["total_tokens"] == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_aclose_closes_owned_client(adapter_settings):
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=text_completion("ok"))

    client = make_client(handle)
    assert not client._http_client.is_closed
    await client.aclose()
    assert client._http_client.is_closed


def test_factory_constructs_pydantic_ai_client_with_synthetic_settings(monkeypatch):
    config = SimpleNamespace(
        llm=SimpleNamespace(
            provider="pydantic-ai",
            pydantic_ai_model=MODEL,
            pydantic_ai_base_url=BASE_URL,
            pydantic_ai_api_key=SecretStr(API_KEY),
            pydantic_ai_temperature=0.7,
            pydantic_ai_max_tokens=2048,
            pydantic_ai_timeout_seconds=30.0,
        ),
    )
    monkeypatch.setattr(llm, "settings", config)
    monkeypatch.setattr(pydantic_ai_client, "settings", config)

    client = llm.get_client()
    assert isinstance(client, PydanticAIClient)
    assert client.model == MODEL
    assert isinstance(client._text_agent, Agent)

    explicit = llm.get_client(provider="pydantic-ai", model="explicit-model")
    assert explicit.model == "explicit-model"


def test_constructor_rejects_empty_model(monkeypatch):
    config = SimpleNamespace(
        llm=SimpleNamespace(
            provider="pydantic-ai",
            pydantic_ai_model="   ",
            pydantic_ai_base_url=BASE_URL,
            pydantic_ai_api_key=SecretStr(API_KEY),
            pydantic_ai_timeout_seconds=30.0,
        ),
    )
    monkeypatch.setattr(pydantic_ai_client, "settings", config)
    with pytest.raises(ValueError, match="non-empty"):
        pydantic_ai_client.PydanticAIClient()


@pytest.mark.asyncio
async def test_deny_live_models_guard_blocks_all_http_requests(adapter_settings, deny_live_models):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=text_completion("must not be reached"))

    client = make_client(handle)
    try:
        with pytest.raises(RuntimeError, match="Model requests are not allowed"):
            await client.a_generate(PROMPT, context=CONTEXT)
        with pytest.raises(RuntimeError, match="Model requests are not allowed"):
            _ = [token async for token in client.a_generate_stream(PROMPT, context=CONTEXT)]
        with pytest.raises(RuntimeError, match="Model requests are not allowed"):
            await client.a_generate_structured(PROMPT, Answer, context=CONTEXT)
        assert requests == []
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_deny_live_flag_restored_after_adapter_failure(adapter_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500, json={"error": {"message": "synthetic"}})

    client = make_client(handle)
    try:
        with denied_model_requests():
            with pytest.raises(RuntimeError, match="Model requests are not allowed"):
                await client.a_generate(PROMPT, context=CONTEXT)
            assert pydantic_ai.models.ALLOW_MODEL_REQUESTS is False
        assert pydantic_ai.models.ALLOW_MODEL_REQUESTS is True
        assert requests == []
    finally:
        await client.aclose()


def test_usage_capture_records_pydantic_ai_run_usage():
    response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=3, output_tokens=5, total_tokens=8)
    )
    with capture_usage() as captured:
        with usage_call(provider="pydantic-ai") as call:
            call.record_response(response)
    assert captured.usage_by_role["generation"] == {
        "input_tokens": 3,
        "output_tokens": 5,
        "total_tokens": 8,
        "status": "reported",
        "source": "provider_sdk",
    }
    assert captured.unknowns == []


@pytest.mark.asyncio
async def test_generate_inside_running_loop_requires_async_variant(adapter_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=text_completion("ok"))

    client = make_client(handle)
    try:
        with pytest.raises(RuntimeError, match="a_generate"):
            client.generate(PROMPT, context=CONTEXT)
        with pytest.raises(RuntimeError, match="a_generate_structured"):
            client.generate_structured(PROMPT, Answer, context=CONTEXT)
        assert requests == []
    finally:
        await client.aclose()


def test_generate_outside_event_loop_returns_output(adapter_settings):
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"connection": "close"},
            json=text_completion("sync answer"),
        )

    client = make_client(handle)
    try:
        assert client.generate(PROMPT, context=CONTEXT) == "sync answer"
        assert len(requests) == 1
    finally:
        asyncio.run(client.aclose())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"temperature": 2.5},
        {"temperature": float("nan")},
        {"max_tokens": 0},
        {"max_tokens": True},
        {"timeout_seconds": 0},
        {"timeout_seconds": 601},
    ],
)
def test_constructor_rejects_out_of_bounds_overrides(adapter_settings, kwargs):
    with pytest.raises(ValueError):
        pydantic_ai_client.PydanticAIClient(model=MODEL, **kwargs)


def test_constructor_accepts_in_bounds_overrides(adapter_settings):
    client = pydantic_ai_client.PydanticAIClient(
        model=MODEL, temperature=0.0, max_tokens=1, timeout_seconds=0.5, raw_prompt=True
    )

    assert client._temperature == 0.0
    assert client._max_tokens == 1
    assert client._timeout == 0.5
    assert client._raw_prompt is True
