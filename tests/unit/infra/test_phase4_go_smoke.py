"""Offline guarantees for the P4-D Stage A Go smoke harness.

Drives ``scripts/manual/phase4_go_smoke.py`` through importlib over in-memory
fake transports only: no network, no credentials, no live SDK paths. Verified
against synthetic handlers riding the exact allowlisted Go route string (a
MockTransport never opens a socket): the narrowed builder wiring (every SDK
request rides a harness-built in-memory MockTransport, no transport is
injectable, while the trusted handler stays explicitly outside that
guarantee), header validation before admission (exact per-implementation
User-Agent plus opaque session, never the raw conversation
id), the shared admission gate (POST cap, exact route, ASCII byte ceiling,
retained reservations, exact wire-payload digests), fail-fast abort after a
rejected request, per-instance settings isolation with overlapping runs, the
blocked-next-read cancellation regression, awaited construction-failure
cleanup inside the owning event loop, and structured repair bounds.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from queue import SimpleQueue
from types import ModuleType
from typing import Any

import httpx
import openai
import pydantic_ai
import pytest
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior

from src.config import settings as app_settings
from src.infra.llm import pydantic_ai_client, qwen_client
from src.infra.llm.conversation_context import conversation_scope, opaque_session_id

_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "manual" / "phase4_go_smoke.py"
_MODULE_NAME = "phase4_go_smoke_under_test"


def _load_harness_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Phase 4 Go smoke harness script could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


HARNESS = _load_harness_module()

SYNTHETIC_API_KEY = "synthetic-not-a-key"
GO_CHAT_COMPLETIONS = HARNESS.GO_BASE_URL + "/chat/completions"
# Synthetic fixture rates only (owner-confirmed rates are a live-run input).
SYNTHETIC_INPUT_RATE = Decimal("0.14")
SYNTHETIC_OUTPUT_RATE = Decimal("0.28")
_SSE_HEADERS = {"content-type": "text/event-stream"}


def _admission(**kwargs: Any) -> Any:
    rates = kwargs.pop(
        "rates",
        HARNESS.QuotaRates(
            input_per_million=SYNTHETIC_INPUT_RATE,
            output_per_million=SYNTHETIC_OUTPUT_RATE,
        ),
    )
    return HARNESS.TransportAdmission(rates, **kwargs)


def _counting_handler(seen: list[httpx.Request]) -> Any:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    return handle


def _gate_headers(session: Any, user_agent: str) -> dict[str, str]:
    """Valid harness identity headers: honest UA plus the opaque session."""
    return {"user-agent": user_agent, HARNESS.SESSION_HEADER: session.opaque_session()}


def _gated_transport(
    seen: list[httpx.Request],
    admission: Any,
    session: Any,
    *,
    user_agent: str = HARNESS.USER_AGENT_BASELINE,
) -> Any:
    return HARNESS.offline_transport(
        _counting_handler(seen),
        admission,
        expected_user_agent=user_agent,
        expected_session=session,
    )


def _completion(content: str | None, *, tool_args: str | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content, "refusal": None}
    finish = "stop"
    if tool_args is not None:
        finish = "tool_calls"
        message["tool_calls"] = [
            {
                "id": "call_synthetic",
                "type": "function",
                "function": {"name": "final_result", "arguments": tool_args},
            }
        ]
    return {
        "id": "synthetic",
        "object": "chat.completion",
        "created": 0,
        "model": HARNESS.GO_MODEL,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }


def _sse_chunk(
    delta: dict[str, Any] | None,
    *,
    finish: str | None = None,
    **extra: Any,
) -> str:
    payload: dict[str, Any] = {
        "id": "synthetic",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": HARNESS.GO_MODEL,
        "choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}],
    }
    payload.update(extra)
    return "data: " + json.dumps(payload) + "\n\n"


def _sse_bytes(*deltas: str, usage: dict[str, int] | None = None) -> bytes:
    parts = [_sse_chunk({"content": delta}) for delta in deltas]
    parts.append(_sse_chunk({}, finish="stop"))
    if usage is not None:
        parts.append(_sse_chunk(None, choices=[], usage=usage))
    parts.append("data: [DONE]\n\n")
    return "".join(parts).encode("utf-8")


class _SseBody(httpx.AsyncByteStream):
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def __aiter__(self):
        yield self._payload


class _BlockedAfterFirstDelta(httpx.AsyncByteStream):
    """SSE body serving one delta, then blocking until its read is cancelled.

    ``pending_read`` is set the moment the body's next upstream read is
    entered and suspended (``Event.set`` never yields, so the consumer is
    parked inside that blocked read when the cancel helper observes the
    event). ``read_cancelled`` is the actual cancellation proof: it can only
    be set when CancelledError is delivered inside the blocked next-read
    await.
    """

    def __init__(self, pending_read: asyncio.Event) -> None:
        self.pending_read = pending_read
        self.closed = asyncio.Event()
        self.read_cancelled = asyncio.Event()

    async def __aiter__(self):
        yield _sse_chunk({"content": "1"}).encode("utf-8")
        # Signal before suspending: set + await is atomic (no yield in
        # between), so the cancel delivered on this event lands inside the
        # blocked await below, never mid-teardown.
        self.pending_read.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.read_cancelled.set()
            raise

    async def aclose(self) -> None:
        self.closed.set()


def _stage_a_handler(
    seen: list[httpx.Request],
    *,
    block_stream_on_request: set[int] | None = None,
    blocked_streams: list[_BlockedAfterFirstDelta] | None = None,
    cancel_read_events: list[asyncio.Event] | None = None,
) -> Any:
    """Dispatch a synthetic OpenAI-compatible response from the request body.

    Every handled request asserts the client modules' ``settings`` globals are
    untouched: per-instance isolation must hold mid-flight, including while two
    harness runs overlap. Streaming requests whose 1-based request number is in
    ``block_stream_on_request`` are served a body that blocks after its first
    delta (the runner's cancel legs must cancel that blocked next read); each
    blocked body receives the next event from ``cancel_read_events`` in serve
    order — the same pre-allocated sequence the harness hands its cancel legs,
    so the helper awaits the read that is actually pending. Other stream
    requests complete normally.
    """
    block_numbers = block_stream_on_request or set()
    served_blocked = {"count": 0}

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert qwen_client.settings is app_settings
        assert pydantic_ai_client.settings is app_settings
        body = json.loads(request.content)
        if body.get("stream"):
            if len(seen) in block_numbers:
                if cancel_read_events is None:
                    pending_read = asyncio.Event()
                else:
                    pending_read = cancel_read_events[served_blocked["count"]]
                    served_blocked["count"] += 1
                blocked = _BlockedAfterFirstDelta(pending_read=pending_read)
                if blocked_streams is not None:
                    blocked_streams.append(blocked)
                return httpx.Response(200, headers=_SSE_HEADERS, stream=blocked)
            # Full fake usage contract: all three token fields, like a
            # provider that reports usage. A partial usage payload makes the
            # production clients honestly report incomplete usage (status
            # "incomplete"), which would surface as missing usage in the run
            # metadata instead of a fully reported stream operation.
            return httpx.Response(
                200,
                headers=_SSE_HEADERS,
                stream=_SseBody(
                    _sse_bytes(
                        "1",
                        "2",
                        "3",
                        usage={
                            "prompt_tokens": 3,
                            "completion_tokens": 5,
                            "total_tokens": 8,
                        },
                    )
                ),
            )
        if body.get("tools"):
            return httpx.Response(
                200,
                json=_completion(None, tool_args=json.dumps({"answer": "structured answer"})),
            )
        wire_format = (body.get("response_format") or {}).get("type")
        if wire_format in {"json_object", "json_schema"}:
            return httpx.Response(
                200, json=_completion(json.dumps({"answer": "structured answer"}))
            )
        return httpx.Response(200, json=_completion("smoke ok"))

    return handle


def _wire_max_tokens(body: dict[str, Any]) -> Any:
    value = body.get("max_tokens")
    return value if value is not None else body.get("max_completion_tokens")


async def _build_stage_a_harness(
    admission: Any,
    session: Any,
    *,
    block_stream_on_request: set[int] | None = None,
    blocked_streams: list[_BlockedAfterFirstDelta] | None = None,
) -> tuple[Any, list[httpx.Request]]:
    seen: list[httpx.Request] = []
    # One pre-allocated event per cancel leg, in leg order. The same events go
    # to the harness (popped by the cancel helper, one per leg) and to the
    # fake handler (attached to each blocked stream body in serve order), so
    # cancellation synchronizes on the actual pending read, not on timing.
    cancel_read_events = [asyncio.Event(), asyncio.Event()]
    cancel_read_signals: Any = SimpleQueue()
    for event in cancel_read_events:
        cancel_read_signals.put(event)
    handler = _stage_a_handler(
        seen,
        block_stream_on_request=block_stream_on_request,
        blocked_streams=blocked_streams,
        cancel_read_events=cancel_read_events,
    )
    baseline = await HARNESS.build_baseline_qwen_client(
        api_key=SYNTHETIC_API_KEY,
        handler=handler,
        admission=admission,
        session=session,
    )
    adapter = await HARNESS.build_adapter_pydantic_ai_client(
        api_key=SYNTHETIC_API_KEY,
        handler=handler,
        admission=admission,
        session=session,
    )
    harness = HARNESS.StageAHarness(
        baseline=baseline,
        adapter=adapter,
        admission=admission,
        session=session,
        cancel_read_signals=cancel_read_signals,
    )
    return harness, seen


# ---------------------------------------------------------------------------
# Fail-closed defaults and lightweight import
# ---------------------------------------------------------------------------


def test_harness_module_import_is_lightweight():
    probe = (
        "import importlib.util, json, sys;"
        "spec = importlib.util.spec_from_file_location("
        f"'phase4_go_smoke_probe', {str(_SCRIPT_PATH)!r});"
        "module = importlib.util.module_from_spec(spec);"
        "spec.loader.exec_module(module);"
        "print(json.dumps([name for name in "
        "('src', 'src.config', 'openai', 'httpx', 'pydantic', 'pydantic_ai') "
        "if name in sys.modules]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=120, check=True
    )
    assert json.loads(result.stdout.strip().splitlines()[-1]) == []


def test_cli_entrypoint_and_main_fail_closed_without_live_execution():
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH)], capture_output=True, text=True, timeout=120
    )
    assert result.returncode != 0
    assert "BLOCKED" in result.stderr
    assert HARNESS.main([]) != 0


@pytest.mark.asyncio
async def test_builders_fail_closed_on_missing_or_invalid_inputs():
    session = HARNESS.fresh_stage_a_session()
    admission = _admission()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    with pytest.raises(HARNESS.SmokeHarnessError):
        await HARNESS.build_baseline_qwen_client(
            api_key="", handler=handler, admission=admission, session=session
        )
    with pytest.raises(HARNESS.SmokeHarnessError):
        await HARNESS.build_baseline_qwen_client(
            api_key=None, handler=handler, admission=admission, session=session
        )
    with pytest.raises(HARNESS.SmokeHarnessError):
        await HARNESS.build_baseline_qwen_client(
            api_key=SYNTHETIC_API_KEY, handler=None, admission=admission, session=session
        )
    with pytest.raises(HARNESS.SmokeHarnessError):
        await HARNESS.build_baseline_qwen_client(
            api_key=SYNTHETIC_API_KEY, handler=handler, admission=None, session=session
        )
    with pytest.raises(HARNESS.SmokeHarnessError):
        await HARNESS.build_baseline_qwen_client(
            api_key=SYNTHETIC_API_KEY, handler=handler, admission=admission, session=None
        )
    with pytest.raises(HARNESS.SmokeHarnessError):
        await HARNESS.build_adapter_pydantic_ai_client(
            api_key="", handler=handler, admission=admission, session=session
        )
    with pytest.raises(HARNESS.SmokeHarnessError):
        await HARNESS.build_adapter_pydantic_ai_client(
            api_key=SYNTHETIC_API_KEY,
            handler=42,
            admission=admission,
            session=session,
        )
    with pytest.raises(HARNESS.SmokeHarnessError):
        await HARNESS.build_adapter_pydantic_ai_client(
            api_key=SYNTHETIC_API_KEY, handler=handler, admission=admission, session=None
        )


@pytest.mark.asyncio
async def test_builder_api_accepts_no_transport_argument():
    """Narrowed wiring: no transport can be injected at all (SDK transport
    is always the harness-built in-memory MockTransport)."""
    session = HARNESS.fresh_stage_a_session()
    admission = _admission()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    with pytest.raises(TypeError):
        await HARNESS.build_baseline_qwen_client(
            api_key=SYNTHETIC_API_KEY,
            transport=httpx.AsyncHTTPTransport(),
            handler=handler,
            admission=admission,
            session=session,
        )
    with pytest.raises(TypeError):
        await HARNESS.build_adapter_pydantic_ai_client(
            api_key=SYNTHETIC_API_KEY,
            transport=httpx.AsyncHTTPTransport(),
            handler=handler,
            admission=admission,
            session=session,
        )
    # The only transport the harness produces is its in-memory MockTransport.
    transport = HARNESS.offline_transport(
        handler,
        admission,
        expected_user_agent=HARNESS.USER_AGENT_BASELINE,
        expected_session=session,
    )
    assert isinstance(transport, httpx.MockTransport)


# ---------------------------------------------------------------------------
# Shared transport admission
# ---------------------------------------------------------------------------


def test_admission_caps_twelve_posts_and_refuses_thirteenth_before_handler():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []
    transport = _gated_transport(seen, admission, session)
    headers = _gate_headers(session, HARNESS.USER_AGENT_BASELINE)
    with httpx.Client(transport=transport) as client:
        for _ in range(HARNESS.MAX_POST_ATTEMPTS):
            response = client.post(
                GO_CHAT_COMPLETIONS, json={"model": HARNESS.GO_MODEL}, headers=headers
            )
            assert response.status_code == 200
        with pytest.raises(HARNESS.AdmissionError) as excinfo:
            client.post(GO_CHAT_COMPLETIONS, json={"model": HARNESS.GO_MODEL}, headers=headers)
    assert excinfo.value.reason == "post_cap_reached"
    assert len(seen) == HARNESS.MAX_POST_ATTEMPTS
    assert admission.attempts == HARNESS.MAX_POST_ATTEMPTS
    assert admission.remaining_attempts() == 0
    assert len(admission.payload_digests()) == HARNESS.MAX_POST_ATTEMPTS


def test_admission_rejects_oversized_and_non_ascii_bodies_before_handler():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []
    transport = _gated_transport(seen, admission, session)
    headers = _gate_headers(session, HARNESS.USER_AGENT_BASELINE)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(HARNESS.AdmissionError) as oversized:
            client.post(
                GO_CHAT_COMPLETIONS,
                content=b"a" * (HARNESS.MAX_INPUT_BODY_BYTES + 1),
                headers={"content-type": "application/json", **headers},
            )
        with pytest.raises(HARNESS.AdmissionError) as non_ascii:
            client.post(
                GO_CHAT_COMPLETIONS,
                content="{'x': 'caf\u00e9'}".encode(),
                headers={"content-type": "application/json", **headers},
            )
    assert oversized.value.reason == "request_body_exceeds_byte_ceiling"
    assert non_ascii.value.reason == "request_body_not_ascii"
    assert seen == []
    assert admission.attempts == 0


def test_admission_rejects_off_route_and_non_post_requests_before_handler():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []
    transport = _gated_transport(seen, admission, session)
    headers = _gate_headers(session, HARNESS.USER_AGENT_BASELINE)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(HARNESS.AdmissionError) as off_host:
            client.post("https://elsewhere.invalid/v1/chat/completions", json={}, headers=headers)
        with pytest.raises(HARNESS.AdmissionError) as off_path:
            client.post(HARNESS.GO_BASE_URL + "/responses", json={}, headers=headers)
        with pytest.raises(HARNESS.AdmissionError) as wrong_method:
            client.get(GO_CHAT_COMPLETIONS, headers=headers)
    assert off_host.value.reason == "route_not_allowlisted"
    assert off_path.value.reason == "route_not_allowlisted"
    assert wrong_method.value.reason == "non_post_request"
    assert seen == []
    assert admission.attempts == 0


def test_offline_transport_rejects_bad_identity_headers_before_admission():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []
    transport = _gated_transport(seen, admission, session)
    good = _gate_headers(session, HARNESS.USER_AGENT_BASELINE)
    cases = [
        # Missing User-Agent.
        ("unexpected_user_agent", {k: v for k, v in good.items() if k != "user-agent"}),
        # Wrong User-Agent (not this transport's per-implementation agent).
        ("unexpected_user_agent", _gate_headers(session, "some-other-agent/1.0")),
        # Missing session header.
        (
            "session_header_missing_or_mismatch",
            {k: v for k, v in good.items() if k != HARNESS.SESSION_HEADER},
        ),
        # Session header that is not the opaque value for this run.
        (
            "session_header_missing_or_mismatch",
            {**good, HARNESS.SESSION_HEADER: "qna-not-the-opaque-value"},
        ),
        # Raw conversation id on the session header (opaque value required).
        (
            "session_header_missing_or_mismatch",
            {**good, HARNESS.SESSION_HEADER: session.conversation_id},
        ),
        # Raw conversation id smuggled in any other header.
        (
            "raw_conversation_id_on_wire",
            {**good, "x-synthetic-echo": session.conversation_id},
        ),
    ]
    with httpx.Client(transport=transport) as client:
        for reason, headers in cases:
            with pytest.raises(HARNESS.AdmissionError) as excinfo:
                client.post(GO_CHAT_COMPLETIONS, json={}, headers=headers)
            assert excinfo.value.reason == reason
    assert seen == []  # the synthetic handler never ran
    assert admission.attempts == 0  # header validation precedes admission


def test_admission_decimal_reservations_retained_on_missing_usage():
    admission = _admission()
    expected_per_call = (
        Decimal(HARNESS.MAX_INPUT_BODY_BYTES) * SYNTHETIC_INPUT_RATE
        + Decimal(HARNESS.MAX_OUTPUT_TOKENS) * SYNTHETIC_OUTPUT_RATE
    ) / Decimal(1_000_000)
    assert admission.per_call_quota_reservation == expected_per_call

    admission.gate("POST", GO_CHAT_COMPLETIONS, b"{}")
    assert admission.reserved_quota_value == expected_per_call
    assert admission.reserved_cash == Decimal("0")
    assert len(admission.payload_digests()) == 1

    admission.settle(reported_input_tokens=None, reported_output_tokens=None)
    assert admission.reserved_quota_value == expected_per_call
    assert admission.missing_usage_count == 1

    admission.settle(reported_input_tokens=10, reported_output_tokens=5)
    assert admission.reserved_quota_value == expected_per_call
    assert admission.metadata()["missing_usage_count"] == 1


def test_admission_requires_owner_rates_and_refuses_when_quota_headroom_gone():
    with pytest.raises(HARNESS.SmokeHarnessError):
        HARNESS.TransportAdmission(None)
    with pytest.raises(HARNESS.SmokeHarnessError):
        HARNESS.QuotaRates(
            input_per_million=Decimal("-1"), output_per_million=SYNTHETIC_OUTPUT_RATE
        )

    tiny = _admission(quota_limit=Decimal("0.01"))
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []
    transport = _gated_transport(seen, tiny, session)
    headers = _gate_headers(session, HARNESS.USER_AGENT_BASELINE)
    with httpx.Client(transport=transport) as client:
        for _ in range(8):
            client.post(GO_CHAT_COMPLETIONS, json={"messages": []}, headers=headers)
        with pytest.raises(HARNESS.AdmissionError) as excinfo:
            client.post(GO_CHAT_COMPLETIONS, json={"messages": []}, headers=headers)
    assert excinfo.value.reason == "quota_reservation_exceeded"
    assert len(seen) == 8

    cash = _admission(
        rates=HARNESS.QuotaRates(
            input_per_million=SYNTHETIC_INPUT_RATE,
            output_per_million=SYNTHETIC_OUTPUT_RATE,
            cash_input_per_million=Decimal("1000"),
        )
    )
    with pytest.raises(HARNESS.AdmissionError) as cash_refused:
        cash.gate("POST", GO_CHAT_COMPLETIONS, b"{}")
    assert cash_refused.value.reason == "cash_reservation_exceeded"


# ---------------------------------------------------------------------------
# Per-instance settings isolation (no module settings swap, overlap-safe)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_calls_never_swap_module_settings():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []
    handler = _stage_a_handler(seen)
    baseline = await HARNESS.build_baseline_qwen_client(
        api_key=SYNTHETIC_API_KEY, handler=handler, admission=admission, session=session
    )
    adapter = await HARNESS.build_adapter_pydantic_ai_client(
        api_key=SYNTHETIC_API_KEY, handler=handler, admission=admission, session=session
    )
    try:
        with conversation_scope(session.conversation_id):
            await baseline.a_generate(HARNESS.PROMPT_TEXT, context="")
            await adapter.a_generate(HARNESS.PROMPT_TEXT, context="")
    finally:
        await baseline.aclose()
        await adapter.aclose()
    assert len(seen) == 2  # the handler's mid-flight asserts saw real settings
    assert qwen_client.settings is app_settings
    assert pydantic_ai_client.settings is app_settings
    # The one-attempt budget lives in the per-instance view, not any module.
    assert baseline._settings_view.retry.max_retries == HARNESS.TOTAL_TRANSPORT_ATTEMPTS == 1
    assert adapter._settings_view.retry.max_retries == 1


@pytest.mark.asyncio
async def test_overlapping_runs_stay_isolated_without_module_settings_swap():
    qwen_before = qwen_client.settings
    pa_before = pydantic_ai_client.settings

    def failing_handler(seen: list[httpx.Request]) -> Any:
        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            assert qwen_client.settings is app_settings
            assert pydantic_ai_client.settings is app_settings
            return httpx.Response(500, json={"error": {"message": "synthetic"}})

        return handle

    admission_a = _admission()
    session_a = HARNESS.fresh_stage_a_session()
    seen_a: list[httpx.Request] = []
    handler_a = failing_handler(seen_a)
    harness_a = HARNESS.StageAHarness(
        baseline=await HARNESS.build_baseline_qwen_client(
            api_key=SYNTHETIC_API_KEY, handler=handler_a, admission=admission_a, session=session_a
        ),
        adapter=await HARNESS.build_adapter_pydantic_ai_client(
            api_key=SYNTHETIC_API_KEY, handler=handler_a, admission=admission_a, session=session_a
        ),
        admission=admission_a,
        session=session_a,
    )
    admission_b = _admission()
    session_b = HARNESS.fresh_stage_a_session()
    harness_b, seen_b = await _build_stage_a_harness(
        admission_b, session_b, block_stream_on_request={3, 6}
    )

    results = await asyncio.gather(
        HARNESS.run_stage_a_operations(harness_a),
        HARNESS.run_stage_a_operations(harness_b),
        return_exceptions=True,
    )
    try:
        # Run A failed fast on its first rejected request; run B still ran all
        # nine operations against its own per-instance configuration. Neither
        # run ever swapped the client modules' settings globals.
        assert isinstance(results[0], openai.APIStatusError)
        assert isinstance(results[1], dict)
        assert admission_a.attempts == 1
        assert len(seen_a) == 1
        assert admission_b.attempts == 9
        assert len(seen_b) == 9
        assert qwen_client.settings is qwen_before is app_settings
        assert pydantic_ai_client.settings is pa_before is app_settings
    finally:
        await harness_a.aclose()
        await harness_b.aclose()


# ---------------------------------------------------------------------------
# Wire contract: exact route/model, honest headers, runtime key only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clients_wire_exact_route_honest_headers_and_opaque_session():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []
    handler = _stage_a_handler(seen)
    baseline = await HARNESS.build_baseline_qwen_client(
        api_key=SYNTHETIC_API_KEY, handler=handler, admission=admission, session=session
    )
    adapter = await HARNESS.build_adapter_pydantic_ai_client(
        api_key=SYNTHETIC_API_KEY, handler=handler, admission=admission, session=session
    )
    try:
        with conversation_scope(session.conversation_id):
            await baseline.a_generate(HARNESS.PROMPT_TEXT, context="")
            await adapter.a_generate(HARNESS.PROMPT_TEXT, context="")
            await baseline.a_generate(HARNESS.PROMPT_TEXT, context="")
    finally:
        await baseline.aclose()
        await adapter.aclose()

    baseline_requests = [
        request for request in seen if request.headers["user-agent"] == HARNESS.USER_AGENT_BASELINE
    ]
    adapter_requests = [
        request
        for request in seen
        if request.headers["user-agent"] == pydantic_ai_client.USER_AGENT
    ]
    assert len(baseline_requests) == 2
    assert len(adapter_requests) == 1
    expected_session = opaque_session_id(session.conversation_id)
    assert expected_session != session.conversation_id
    for request in seen:
        assert str(request.url) == GO_CHAT_COMPLETIONS
        assert request.headers["authorization"] == f"Bearer {SYNTHETIC_API_KEY}"
        assert request.headers["x-opencode-session"] == expected_session
        assert session.conversation_id not in str(request.headers)
        assert request.headers["user-agent"] != "OpenAI/Python"
        body = json.loads(request.content)
        assert body["model"] == HARNESS.GO_MODEL
        assert body["temperature"] == HARNESS.TEMPERATURE == 0.7
        assert _wire_max_tokens(body) == HARNESS.MAX_OUTPUT_TOKENS == 2048
    # Per-request headers never mutate shared client defaults.
    assert adapter._http_client.headers.get("x-opencode-session") is None
    assert "x-opencode-session" not in adapter._openai_client.default_headers


@pytest.mark.asyncio
async def test_adapter_requests_without_conversation_scope_are_refused_before_admission():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []
    adapter = await HARNESS.build_adapter_pydantic_ai_client(
        api_key=SYNTHETIC_API_KEY,
        handler=_stage_a_handler(seen),
        admission=admission,
        session=session,
    )
    try:
        # No conversation_scope: the mandatory opaque session header is absent,
        # so the harness transport refuses before admission (fail closed). The
        # SDK/pydantic-ai stack wraps the refusal as a connection-level error;
        # the fail-closed proof is that nothing was admitted or sent.
        with pytest.raises(ModelAPIError):
            await adapter.a_generate(HARNESS.PROMPT_TEXT, context="")
    finally:
        await adapter.aclose()
    assert seen == []
    assert admission.attempts == 0


# ---------------------------------------------------------------------------
# Attempt bounds: one total transport attempt, structured repair <= 1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("implementation", ["baseline", "adapter"])
async def test_only_one_total_transport_attempt_per_call(implementation: str):
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(500, json={"error": {"message": "synthetic"}})

    if implementation == "baseline":
        client = await HARNESS.build_baseline_qwen_client(
            api_key=SYNTHETIC_API_KEY, handler=handle, admission=admission, session=session
        )
        expected_error: type[Exception] = openai.APIStatusError
    else:
        client = await HARNESS.build_adapter_pydantic_ai_client(
            api_key=SYNTHETIC_API_KEY, handler=handle, admission=admission, session=session
        )
        expected_error = ModelHTTPError
    try:
        # Adapter requests need the run's conversation boundary bound (the
        # harness transport refuses unscoped adapter requests before
        # admission); the baseline ignores it (build-time default headers).
        with conversation_scope(session.conversation_id):
            with pytest.raises(expected_error):
                await client.a_generate(HARNESS.PROMPT_TEXT, context="")
    finally:
        await client.aclose()
    assert len(seen) == 1
    assert admission.attempts == 1


@pytest.mark.asyncio
async def test_adapter_structured_repair_is_bounded_to_one_extra_call():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []
    tool_args_plan = [
        json.dumps({"answer": 123}),  # invalid -> exactly one repair
        json.dumps({"answer": "structured answer"}),
        json.dumps({"answer": 123}),  # every later call stays invalid
    ]
    calls = {"count": 0}

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        args = tool_args_plan[min(calls["count"], len(tool_args_plan) - 1)]
        calls["count"] += 1
        return httpx.Response(200, json=_completion(None, tool_args=args))

    client = await HARNESS.build_adapter_pydantic_ai_client(
        api_key=SYNTHETIC_API_KEY, handler=handle, admission=admission, session=session
    )
    try:
        with conversation_scope(session.conversation_id):
            result = await client.a_generate_structured(
                HARNESS.PROMPT_TEXT, HARNESS.smoke_answer_model(), context=""
            )
            assert result.answer == "structured answer"
            with pytest.raises(UnexpectedModelBehavior):
                await client.a_generate_structured(
                    HARNESS.PROMPT_TEXT, HARNESS.smoke_answer_model(), context=""
                )
    finally:
        await client.aclose()
    # First op: initial + one repair. Second op: initial + one repair, then
    # the explicitly pinned budget of 1 stops the retries.
    assert admission.attempts == 4
    assert len(seen) == 4


@pytest.mark.asyncio
async def test_adapter_native_json_schema_malformed_output_is_bounded():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_completion("not-json"))

    client = await HARNESS.build_adapter_pydantic_ai_client(
        api_key=SYNTHETIC_API_KEY, handler=handle, admission=admission, session=session
    )
    client.structured_mode = "native-json-schema"
    try:
        with conversation_scope(session.conversation_id):
            with pytest.raises(UnexpectedModelBehavior):
                await client.a_generate_structured(
                    HARNESS.PROMPT_TEXT, HARNESS.smoke_answer_model(), context=""
                )
    finally:
        await client.aclose()
    # Malformed native-json-schema output never exceeds initial + one repair.
    assert 1 <= len(seen) <= 1 + HARNESS.MAX_STRUCTURED_REPAIRS
    assert admission.attempts == len(seen)


@pytest.mark.asyncio
async def test_baseline_structured_validation_failure_does_not_repair():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_completion("not-json"))

    client = await HARNESS.build_baseline_qwen_client(
        api_key=SYNTHETIC_API_KEY, handler=handle, admission=admission, session=session
    )
    try:
        with pytest.raises(ValueError):
            await client.a_generate_structured(
                HARNESS.PROMPT_TEXT, HARNESS.smoke_answer_model(), context=""
            )
    finally:
        await client.aclose()
    assert len(seen) == 1
    assert admission.attempts == 1


# ---------------------------------------------------------------------------
# Cancellation legs: cancel the blocked next read, close/drain, keep reservation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("implementation", ["baseline", "adapter"])
async def test_cancellation_leg_cancels_blocked_next_read_keeps_reservation(implementation: str):
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    pending_read = asyncio.Event()
    blocked = _BlockedAfterFirstDelta(pending_read=pending_read)

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=_SSE_HEADERS, stream=blocked)

    if implementation == "baseline":
        client = await HARNESS.build_baseline_qwen_client(
            api_key=SYNTHETIC_API_KEY, handler=handle, admission=admission, session=session
        )
    else:
        client = await HARNESS.build_adapter_pydantic_ai_client(
            api_key=SYNTHETIC_API_KEY, handler=handle, admission=admission, session=session
        )
    try:
        # The adapter leg requires the run's conversation boundary for the
        # mandatory opaque session header; the baseline leg ignores it.
        with conversation_scope(session.conversation_id):
            outcome = await HARNESS.cancel_stream_after_first_delta(
                lambda: client.a_generate_stream(HARNESS.PROMPT_STREAM, context=""),
                pending_next_read=pending_read,
            )
    finally:
        await client.aclose()
    assert outcome == "cancelled_awaiting_next_delta"
    # Actual cancellation proof: the cancellation was delivered inside the
    # blocked next-read await, and the stream close still ran afterwards.
    assert blocked.read_cancelled.is_set()
    assert blocked.closed.is_set()
    assert admission.attempts == 1
    admission.settle(reported_input_tokens=None, reported_output_tokens=None)
    assert admission.reserved_quota_value == admission.per_call_quota_reservation
    assert admission.metadata()["missing_usage_count"] == 1


# ---------------------------------------------------------------------------
# Nine sequential operations over fake transports, sanitized metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nine_operations_run_over_fake_transports_with_sanitized_metadata():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    blocked: list[_BlockedAfterFirstDelta] = []
    harness, seen = await _build_stage_a_harness(
        admission, session, block_stream_on_request={3, 6}, blocked_streams=blocked
    )
    try:
        metadata = await HARNESS.run_stage_a_operations(harness)
    finally:
        await harness.aclose()

    expected_ops = [
        "baseline_text",
        "baseline_stream",
        "baseline_stream_cancel",
        "adapter_text",
        "adapter_stream",
        "adapter_stream_cancel",
        "baseline_structured_json_object",
        "adapter_structured_tool",
        "adapter_structured_native_json_schema",
    ]
    assert [op["op"] for op in metadata["ops"]] == expected_ops
    outcomes = {op["op"]: op["outcome"] for op in metadata["ops"]}
    assert outcomes["baseline_stream_cancel"] == "cancelled_awaiting_next_delta"
    assert outcomes["adapter_stream_cancel"] == "cancelled_awaiting_next_delta"
    assert all(outcomes[name] == "ok" for name in expected_ops if not name.endswith("cancel"))

    # Blocked-read cancellation proof for both cancel legs of the real run.
    assert len(blocked) == 2
    for fake in blocked:
        assert fake.read_cancelled.is_set()
        assert fake.closed.is_set()

    # Shared admission: exactly nine POSTs, all on the allowlisted route with
    # the frozen generation settings.
    assert admission.attempts == 9
    assert metadata["admission"]["post_attempts_admitted"] == 9
    assert all(str(request.url) == GO_CHAT_COMPLETIONS for request in seen)
    for request in seen:
        body = json.loads(request.content)
        assert body["model"] == HARNESS.GO_MODEL
        assert body["temperature"] == 0.7
        assert _wire_max_tokens(body) == 2048

    assert "offline" not in metadata  # no unconditional offline claim
    assert metadata["transport_mode"] == "sdk_transport_mock"
    assert metadata["handler_boundary"] == "trusted_callback_os_isolated_no_io"
    assert metadata["route"] == HARNESS.GO_BASE_URL
    assert metadata["model"] == HARNESS.GO_MODEL
    assert metadata["input_ceiling_bytes"] == HARNESS.MAX_INPUT_BODY_BYTES == 4096
    assert metadata["admission"]["per_call_input_ceiling_bytes"] == 4096
    expected_committed = Decimal("0.00114688") * 9
    assert admission.reserved_quota_value == expected_committed
    assert admission.reserved_quota_value <= Decimal("1.00")
    # Only the two cancelled legs report no usage (their reservations are
    # retained); every completed operation reports full usage because the fake
    # usage contract includes all three token fields.
    assert metadata["admission"]["missing_usage_count"] == 2
    for op in metadata["ops"]:
        if not op["op"].endswith("cancel"):
            assert op["usage_reported"] is True
            assert op["attempts_admitted"] == 1
        # Every admitted request froze its exact wire payload as a digest.
        assert len(op["payload_sha256"]) == 1
        assert len(op["payload_sha256"][0]) == 64
        int(op["payload_sha256"][0], 16)
    assert len({digest for op in metadata["ops"] for digest in op["payload_sha256"]}) >= 5

    # Sanitized metadata only: hashes and counts, never content or secrets.
    dump = json.dumps(metadata)
    forbidden = [
        SYNTHETIC_API_KEY,
        session.conversation_id,
        session.opaque_session(),
        HARNESS.PROMPT_TEXT,
        HARNESS.PROMPT_STREAM,
        "smoke ok",
        "structured answer",
        "Bearer ",
    ]
    assert all(value not in dump for value in forbidden)
    assert set(metadata["frozen_hashes"]) == {
        "system_prompt_sha256",
        "user_prompt_template_sha256",
        "prompt_text_sha256",
        "prompt_stream_sha256",
        "answer_schema_sha256",
    }
    assert all(len(value) == 64 for value in metadata["frozen_hashes"].values())


@pytest.mark.asyncio
async def test_payload_digests_freeze_exact_wire_payloads_deterministically():
    digest_sequences: list[list[list[str]]] = []
    for _ in range(2):
        admission = _admission()
        session = HARNESS.fresh_stage_a_session()
        blocked: list[_BlockedAfterFirstDelta] = []
        # The cancel legs must run against blocking transport bodies: the
        # pending-read signal then makes their cancellation deterministic, and
        # digests cover exactly the same request payloads as the real run.
        harness, _seen = await _build_stage_a_harness(
            admission, session, block_stream_on_request={3, 6}, blocked_streams=blocked
        )
        try:
            metadata = await HARNESS.run_stage_a_operations(harness)
        finally:
            await harness.aclose()
        assert len(blocked) == 2
        for fake in blocked:
            assert fake.read_cancelled.is_set()
            assert fake.closed.is_set()
        digest_sequences.append([op["payload_sha256"] for op in metadata["ops"]])
    # The digests are of the exact wire payloads: identical runs over identical
    # requests produce identical digest sequences, so any assembly change (in
    # either implementation) shows up as a changed digest.
    assert digest_sequences[0] == digest_sequences[1]
    assert all(len(op_digests) == 1 for run in digest_sequences for op_digests in run)


# ---------------------------------------------------------------------------
# Fail-fast run: stop on the first rejected operation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_aborts_after_first_failed_operation():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(401, json={"error": {"message": "synthetic denial"}})

    harness = HARNESS.StageAHarness(
        baseline=await HARNESS.build_baseline_qwen_client(
            api_key=SYNTHETIC_API_KEY, handler=handle, admission=admission, session=session
        ),
        adapter=await HARNESS.build_adapter_pydantic_ai_client(
            api_key=SYNTHETIC_API_KEY, handler=handle, admission=admission, session=session
        ),
        admission=admission,
        session=session,
    )
    try:
        with pytest.raises(openai.APIStatusError):
            await HARNESS.run_stage_a_operations(harness)
    finally:
        await harness.aclose()
    # Fail fast: exactly the first operation's request went out; the rejected
    # run never sent any later operation (addendum stop condition).
    assert len(seen) == 1
    assert admission.attempts == 1


# ---------------------------------------------------------------------------
# Construction-failure cleanup: allocated resources are closed, not leaked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_baseline_builder_failure_closes_resources_inside_active_loop_before_raise(
    monkeypatch: pytest.MonkeyPatch,
):
    """Async failure injection: closes complete before the failure escapes.

    Runs inside an active event loop (the previously uncovered branch): the
    builder must await cleanup of every allocated resource on the owning loop
    before re-raising — never a detached background cleanup task.
    """
    events: list[str] = []
    builder_task = asyncio.current_task()
    closed = {"sync_http": False, "async_http": False}
    real_sync_close = httpx.Client.close
    real_async_aclose = httpx.AsyncClient.aclose

    def record_sync_close(self: httpx.Client) -> None:
        closed["sync_http"] = True
        events.append(f"sync_closed:{asyncio.current_task() is builder_task}")
        real_sync_close(self)

    async def record_async_aclose(self: httpx.AsyncClient) -> None:
        closed["async_http"] = True
        events.append(f"async_closed:{asyncio.current_task() is builder_task}")
        await real_async_aclose(self)

    monkeypatch.setattr(httpx.Client, "close", record_sync_close)
    monkeypatch.setattr(httpx.AsyncClient, "aclose", record_async_aclose)

    class _BoomAsyncOpenAI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            events.append("constructor_failed")
            raise RuntimeError("synthetic construction failure")

    monkeypatch.setattr(openai, "AsyncOpenAI", _BoomAsyncOpenAI)
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    with pytest.raises(RuntimeError, match="synthetic construction failure"):
        await HARNESS.build_baseline_qwen_client(
            api_key=SYNTHETIC_API_KEY, handler=handler, admission=admission, session=session
        )
    # Every resource allocated before the failure was already closed, inside
    # the builder's own task, by the time the raise escaped the awaited setup
    # boundary (a scheduled background task could not have run yet).
    assert events[0] == "constructor_failed"
    # The SDK and its supplied HTTP client may both close the same transport;
    # every close must complete in the setup task before the failure escapes.
    assert set(events[1:]) == {"sync_closed:True", "async_closed:True"}
    assert closed["sync_http"] is True
    assert closed["async_http"] is True


@pytest.mark.asyncio
async def test_adapter_builder_failure_closes_resources_inside_active_loop_before_raise(
    monkeypatch: pytest.MonkeyPatch,
):
    """Async failure injection: the owned httpx client closes before raising."""
    events: list[str] = []
    builder_task = asyncio.current_task()
    closed = {"async_http": False}
    real_async_aclose = httpx.AsyncClient.aclose

    async def record_async_aclose(self: httpx.AsyncClient) -> None:
        closed["async_http"] = True
        events.append(f"async_closed:{asyncio.current_task() is builder_task}")
        await real_async_aclose(self)

    monkeypatch.setattr(httpx.AsyncClient, "aclose", record_async_aclose)

    class _BoomAgent:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            events.append("constructor_failed")
            raise RuntimeError("synthetic construction failure")

    monkeypatch.setattr(pydantic_ai, "Agent", _BoomAgent)
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    with pytest.raises(RuntimeError, match="synthetic construction failure"):
        await HARNESS.build_adapter_pydantic_ai_client(
            api_key=SYNTHETIC_API_KEY, handler=handler, admission=admission, session=session
        )
    # Cleanup ran to completion in the builder's own task before the failure
    # escaped; no pending background cleanup exists at raise time.
    assert events == ["constructor_failed", "async_closed:True"]
    assert closed["async_http"] is True


# ---------------------------------------------------------------------------
# Pre-checks refuse before any network activity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_precheck_refuses_before_network_when_post_cap_exhausted():
    admission = _admission()
    for _ in range(HARNESS.MAX_POST_ATTEMPTS):
        admission.gate("POST", GO_CHAT_COMPLETIONS, b"{}")
    session = HARNESS.fresh_stage_a_session()
    harness, _seen = await _build_stage_a_harness(admission, session)
    try:
        with pytest.raises(HARNESS.SmokeHarnessError) as excinfo:
            await HARNESS.run_stage_a_operations(harness)
    finally:
        await harness.aclose()
    assert excinfo.value.reason == "post_cap_reached_precheck"
    assert admission.attempts == HARNESS.MAX_POST_ATTEMPTS
