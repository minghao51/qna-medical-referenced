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
import hashlib
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
    assert "REFUSED" in result.stderr
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


# ---------------------------------------------------------------------------
# Gated live-capable runner: synthetic delegates only, zero network
# ---------------------------------------------------------------------------


class _RecordingSyncDelegate:
    """Trusted test fake for the sync live delegate (records wire requests)."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.closed = asyncio.Event()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"ok": True})

    def close(self) -> None:
        self.closed.set()


class _RecordingAsyncDelegate:
    """Trusted test fake for the async live delegate (records wire requests)."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"ok": True})

    async def aclose(self) -> None:
        pass


class _LiveBlockedSseBody(httpx.AsyncByteStream):
    """SSE body serving one delta, then blocking until its read is cancelled."""

    def __init__(self) -> None:
        self.read_cancelled = asyncio.Event()
        self.closed = asyncio.Event()

    async def __aiter__(self):
        yield _sse_chunk({"content": "1"}).encode("utf-8")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.read_cancelled.set()
            raise

    async def aclose(self) -> None:
        self.closed.set()


class _LiveFakeAsyncDelegate:
    """OpenAI-compatible fake async delegate for gated-live end-to-end runs.

    With ``block_stream_request_numbers`` the matching 1-based overall
    request numbers are served bodies that block after their first delta
    (the live cancel helper cancels that blocked next read), mirroring the
    offline blocked-stream fixtures. Other stream requests complete normally,
    so plain drain legs are never blocked.
    """

    def __init__(
        self,
        *,
        text_content: str = "smoke ok",
        block_stream_request_numbers: frozenset[int] | set[int] | None = None,
    ) -> None:
        self.text_content = text_content
        self.block_stream_request_numbers = frozenset(block_stream_request_numbers or ())
        self.requests: list[httpx.Request] = []
        self.blocked_bodies: list[_LiveBlockedSseBody] = []
        self.closed = asyncio.Event()

    async def aclose(self) -> None:
        self.closed.set()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        if body.get("stream"):
            if len(self.requests) in self.block_stream_request_numbers:
                blocked = _LiveBlockedSseBody()
                self.blocked_bodies.append(blocked)
                return httpx.Response(200, headers=_SSE_HEADERS, stream=blocked)
            return httpx.Response(
                200,
                headers=_SSE_HEADERS,
                stream=_SseBody(
                    _sse_bytes(
                        "1",
                        "2",
                        "3",
                        usage={"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
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
        return httpx.Response(200, json=_completion(self.text_content))


def _patch_live_delegates(
    monkeypatch: pytest.MonkeyPatch,
    sync_delegate: Any,
    async_delegate: Any,
) -> None:
    """Trusted test boundary: replace the default live delegates with fakes.

    The live transports default their delegates to
    ``httpx.HTTPTransport(trust_env=False)`` / ``AsyncHTTPTransport``; patching
    those classes is the test-owned seam (mirroring the offline trusted-handler
    boundary). The fakes perform no I/O, so no network is possible.
    """
    monkeypatch.setattr(httpx, "HTTPTransport", lambda **kwargs: sync_delegate)
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: async_delegate)


def test_live_gate_constants_and_placeholder_denylist_are_frozen():
    assert HARNESS.LIVE_TRANSPORT_MODE == "live_https_gate"
    assert HARNESS.CANCELLED_LIVE_OUTCOME == "cancelled_after_first_delta_live"
    assert HARNESS.CANCELLED_LIVE_OUTCOME in HARNESS._OPERATION_OUTCOMES
    assert HARNESS.LIVE_API_KEY_ENV == "APP__LLM__PYDANTIC_AI_API_KEY"
    assert HARNESS.LIVE_QUOTA_RATES_BASIS == "p4a_historical_reference_not_verified_billing"
    assert HARNESS.LIVE_REFERENCE_RATES.input_per_million == Decimal("0.14")
    assert HARNESS.LIVE_REFERENCE_RATES.output_per_million == Decimal("0.28")
    assert HARNESS.LIVE_REFERENCE_RATES.cash_input_per_million == Decimal("0")
    assert HARNESS.LIVE_REFERENCE_RATES.cash_output_per_million == Decimal("0")
    assert "your-opencode-go-key-here" in HARNESS._LIVE_PLACEHOLDER_API_KEYS


def test_main_refuses_without_live_flag_or_unknown_tokens(capsys: pytest.CaptureFixture[str]):
    for argv in ([], ["--owner-confirmed"], ["--live", "--wat"], ["--live", "extra"]):
        assert HARNESS.main(argv) == 2
        assert HARNESS.LIVE_EXECUTION_REFUSAL in capsys.readouterr().err


def test_main_live_without_owner_confirmation_refuses(capsys: pytest.CaptureFixture[str]):
    assert HARNESS.main(["--live"]) == 2
    assert HARNESS.LIVE_EXECUTION_REFUSAL in capsys.readouterr().err


def test_main_live_with_missing_env_key_fails_closed_without_client_construction(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.delenv(HARNESS.LIVE_API_KEY_ENV, raising=False)
    calls: list[str] = []

    async def _no_run(api_key: str) -> dict[str, Any]:
        calls.append(api_key)
        return {}

    monkeypatch.setattr(HARNESS, "run_stage_a_live", _no_run)
    assert HARNESS.main(["--live", "--owner-confirmed"]) == 2
    assert "missing_live_api_key_env" in capsys.readouterr().err
    assert calls == []  # no client construction happens before the key resolves


def test_main_live_with_placeholder_env_key_fails_closed_without_client_construction(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setenv(HARNESS.LIVE_API_KEY_ENV, "your-opencode-go-key-here")
    calls: list[str] = []

    async def _no_run(api_key: str) -> dict[str, Any]:
        calls.append(api_key)
        return {}

    monkeypatch.setattr(HARNESS, "run_stage_a_live", _no_run)
    assert HARNESS.main(["--live", "--owner-confirmed"]) == 2
    assert "placeholder_live_api_key" in capsys.readouterr().err
    assert calls == []


def test_main_live_success_prints_sanitized_metadata_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setenv(HARNESS.LIVE_API_KEY_ENV, "  synthetic-live-key  ")
    received: dict[str, str] = {}

    async def _run(run: Any) -> dict[str, Any]:
        received["api_key"] = run.api_key
        return {"z": 1, "run": "p4d-stage-a-smoke"}

    monkeypatch.setattr(HARNESS, "run_stage_a_live", _run)
    assert HARNESS.main(["--live", "--owner-confirmed"]) == 0
    # The CLI path goes through the REAL authorization gate: the env key is
    # resolved (and stripped) by authorize_stage_a_live, not by the stub.
    assert received["api_key"] == "synthetic-live-key"  # env-only source, stripped
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"z": 1, "run": "p4d-stage-a-smoke"}


def test_main_live_failures_exit_1_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setenv(HARNESS.LIVE_API_KEY_ENV, "synthetic-live-key")

    async def _harness_error(api_key: str) -> dict[str, Any]:
        raise HARNESS.SmokeHarnessError("fixed_harness_reason")

    monkeypatch.setattr(HARNESS, "run_stage_a_live", _harness_error)
    assert HARNESS.main(["--live", "--owner-confirmed"]) == 1
    assert capsys.readouterr().err.strip() == "fixed_harness_reason"

    async def _other_error(api_key: str) -> dict[str, Any]:
        raise ValueError("raw detail must never print")

    monkeypatch.setattr(HARNESS, "run_stage_a_live", _other_error)
    assert HARNESS.main(["--live", "--owner-confirmed"]) == 1
    assert capsys.readouterr().err.strip() == "ValueError"


def test_resolve_live_api_key_reads_mapping_strips_and_fails_closed():
    assert (
        HARNESS.resolve_live_api_key({HARNESS.LIVE_API_KEY_ENV: "  synthetic-key  "})
        == "synthetic-key"
    )
    with pytest.raises(HARNESS.SmokeHarnessError) as missing:
        HARNESS.resolve_live_api_key({})
    assert missing.value.reason == "missing_live_api_key_env"
    with pytest.raises(HARNESS.SmokeHarnessError) as empty:
        HARNESS.resolve_live_api_key({HARNESS.LIVE_API_KEY_ENV: "   "})
    assert empty.value.reason == "missing_live_api_key_env"
    with pytest.raises(HARNESS.SmokeHarnessError) as placeholder:
        HARNESS.resolve_live_api_key({HARNESS.LIVE_API_KEY_ENV: "your-opencode-go-key-here"})
    assert placeholder.value.reason == "placeholder_live_api_key"


def test_resolve_live_api_key_defaults_to_os_environ(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(HARNESS.LIVE_API_KEY_ENV, "synthetic-from-os-environ")
    assert HARNESS.resolve_live_api_key() == "synthetic-from-os-environ"


def _sync_live_gate(
    admission: Any,
    session: Any,
    delegate: Any,
    *,
    user_agent: str = HARNESS.USER_AGENT_BASELINE,
) -> Any:
    return HARNESS.LiveGateTransport(
        admission,
        expected_user_agent=user_agent,
        expected_session=session,
        delegate=delegate,
    )


def test_live_gate_transport_rejects_bad_identity_headers_before_delegate():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    delegate = _RecordingSyncDelegate()
    transport = _sync_live_gate(admission, session, delegate)
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
    assert delegate.requests == []  # the delegate never ran
    assert admission.attempts == 0  # header validation precedes admission


def test_live_gate_transport_refuses_off_route_and_non_post_before_delegate():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    delegate = _RecordingSyncDelegate()
    transport = _sync_live_gate(admission, session, delegate)
    good = _gate_headers(session, HARNESS.USER_AGENT_BASELINE)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(HARNESS.AdmissionError) as off_host:
            client.post("https://elsewhere.invalid/v1/chat/completions", json={}, headers=good)
        with pytest.raises(HARNESS.AdmissionError) as off_path:
            client.post(HARNESS.GO_BASE_URL + "/responses", json={}, headers=good)
        with pytest.raises(HARNESS.AdmissionError) as wrong_method:
            client.get(GO_CHAT_COMPLETIONS, headers=good)
    assert off_host.value.reason == "route_not_allowlisted"
    assert off_path.value.reason == "route_not_allowlisted"
    assert wrong_method.value.reason == "non_post_request"
    assert delegate.requests == []
    assert admission.attempts == 0


def test_live_gate_transport_enforces_post_cap_before_delegate():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    delegate = _RecordingSyncDelegate()
    transport = _sync_live_gate(admission, session, delegate)
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
    assert len(delegate.requests) == HARNESS.MAX_POST_ATTEMPTS
    assert admission.attempts == HARNESS.MAX_POST_ATTEMPTS
    assert admission.remaining_attempts() == 0


def test_live_gate_transport_refuses_oversize_and_non_ascii_bodies_before_delegate():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    delegate = _RecordingSyncDelegate()
    transport = _sync_live_gate(admission, session, delegate)
    good = _gate_headers(session, HARNESS.USER_AGENT_BASELINE)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(HARNESS.AdmissionError) as oversized:
            client.post(
                GO_CHAT_COMPLETIONS,
                content=b"a" * (HARNESS.MAX_INPUT_BODY_BYTES + 1),
                headers={"content-type": "application/json", **good},
            )
        with pytest.raises(HARNESS.AdmissionError) as non_ascii:
            client.post(
                GO_CHAT_COMPLETIONS,
                content="{'x': 'caf\u00e9'}".encode(),
                headers={"content-type": "application/json", **good},
            )
    assert oversized.value.reason == "request_body_exceeds_byte_ceiling"
    assert non_ascii.value.reason == "request_body_not_ascii"
    assert delegate.requests == []
    assert admission.attempts == 0


def test_live_gate_transport_admits_and_records_exact_payload_digest():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    delegate = _RecordingSyncDelegate()
    transport = _sync_live_gate(admission, session, delegate)
    body = b'{"model": "mimo-v2.6-flash", "stream": false}'
    with httpx.Client(transport=transport) as client:
        response = client.post(
            GO_CHAT_COMPLETIONS,
            content=body,
            headers={
                "content-type": "application/json",
                **_gate_headers(session, HARNESS.USER_AGENT_BASELINE),
            },
        )
    assert response.status_code == 200
    assert len(delegate.requests) == 1  # delegate called exactly once
    assert admission.attempts == 1
    assert admission.payload_digests() == (hashlib.sha256(body).hexdigest(),)


@pytest.mark.asyncio
async def test_async_live_gate_transport_refuses_before_delegate_and_admits_with_digest():
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    delegate = _RecordingAsyncDelegate()
    transport = HARNESS.AsyncLiveGateTransport(
        admission,
        expected_user_agent=HARNESS.USER_AGENT_BASELINE,
        expected_session=session,
        delegate=delegate,
    )
    good = _gate_headers(session, HARNESS.USER_AGENT_BASELINE)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(HARNESS.AdmissionError) as wrong_ua:
            await client.post(
                GO_CHAT_COMPLETIONS,
                json={},
                headers={k: v for k, v in good.items() if k != "user-agent"},
            )
        with pytest.raises(HARNESS.AdmissionError) as missing_session:
            await client.post(
                GO_CHAT_COMPLETIONS,
                json={},
                headers={k: v for k, v in good.items() if k != HARNESS.SESSION_HEADER},
            )
        with pytest.raises(HARNESS.AdmissionError) as raw_id:
            await client.post(
                GO_CHAT_COMPLETIONS,
                json={},
                headers={**good, "x-synthetic-echo": session.conversation_id},
            )
        with pytest.raises(HARNESS.AdmissionError) as off_route:
            await client.post(
                "https://elsewhere.invalid/v1/chat/completions", json={}, headers=good
            )
        with pytest.raises(HARNESS.AdmissionError) as oversize:
            await client.post(
                GO_CHAT_COMPLETIONS,
                content=b"a" * (HARNESS.MAX_INPUT_BODY_BYTES + 1),
                headers={"content-type": "application/json", **good},
            )
        body = b'{"model": "mimo-v2.6-flash"}'
        response = await client.post(
            GO_CHAT_COMPLETIONS,
            content=body,
            headers={"content-type": "application/json", **good},
        )
    assert wrong_ua.value.reason == "unexpected_user_agent"
    assert missing_session.value.reason == "session_header_missing_or_mismatch"
    assert raw_id.value.reason == "raw_conversation_id_on_wire"
    assert off_route.value.reason == "route_not_allowlisted"
    assert oversize.value.reason == "request_body_exceeds_byte_ceiling"
    assert response.status_code == 200
    assert len(delegate.requests) == 1
    assert admission.attempts == 1
    assert admission.payload_digests() == (hashlib.sha256(body).hexdigest(),)


@pytest.mark.asyncio
async def test_live_baseline_builder_sends_one_gated_post_with_identity_headers(
    monkeypatch: pytest.MonkeyPatch,
):
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    async_delegate = _LiveFakeAsyncDelegate()
    _patch_live_delegates(monkeypatch, _RecordingSyncDelegate(), async_delegate)
    client = await HARNESS.build_baseline_qwen_client_live(
        api_key=SYNTHETIC_API_KEY, admission=admission, session=session
    )
    try:
        await client.a_generate(HARNESS.PROMPT_TEXT, context="")
    finally:
        await client.aclose()
    assert len(async_delegate.requests) == 1  # exactly ONE POST
    request = async_delegate.requests[0]
    assert str(request.url) == GO_CHAT_COMPLETIONS
    assert request.headers["user-agent"] == HARNESS.USER_AGENT_BASELINE
    assert request.headers[HARNESS.SESSION_HEADER] == opaque_session_id(session.conversation_id)
    assert admission.attempts == 1


@pytest.mark.asyncio
async def test_live_adapter_builder_sends_one_gated_post_with_identity_headers(
    monkeypatch: pytest.MonkeyPatch,
):
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    async_delegate = _LiveFakeAsyncDelegate()
    _patch_live_delegates(monkeypatch, _RecordingSyncDelegate(), async_delegate)
    client = await HARNESS.build_adapter_pydantic_ai_client_live(
        api_key=SYNTHETIC_API_KEY, admission=admission, session=session
    )
    try:
        with conversation_scope(session.conversation_id):
            await client.a_generate(HARNESS.PROMPT_TEXT, context="")
    finally:
        await client.aclose()
    assert len(async_delegate.requests) == 1  # exactly ONE POST
    request = async_delegate.requests[0]
    assert str(request.url) == GO_CHAT_COMPLETIONS
    assert request.headers["user-agent"] == pydantic_ai_client.USER_AGENT
    assert request.headers[HARNESS.SESSION_HEADER] == opaque_session_id(session.conversation_id)
    assert admission.attempts == 1


@pytest.mark.asyncio
async def test_live_adapter_structured_modes_respect_structured_mode_selection(
    monkeypatch: pytest.MonkeyPatch,
):
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    async_delegate = _LiveFakeAsyncDelegate()
    _patch_live_delegates(monkeypatch, _RecordingSyncDelegate(), async_delegate)
    client = await HARNESS.build_adapter_pydantic_ai_client_live(
        api_key=SYNTHETIC_API_KEY, admission=admission, session=session
    )
    try:
        client.structured_mode = "tool"
        with conversation_scope(session.conversation_id):
            result = await client.a_generate_structured(
                HARNESS.PROMPT_TEXT, HARNESS.smoke_answer_model(), context=""
            )
        assert result.answer == "structured answer"
        client.structured_mode = "native-json-schema"
        with conversation_scope(session.conversation_id):
            native = await client.a_generate_structured(
                HARNESS.PROMPT_TEXT, HARNESS.smoke_answer_model(), context=""
            )
        assert native.answer == "structured answer"
    finally:
        await client.aclose()
    assert admission.attempts == 2
    tool_body = json.loads(async_delegate.requests[0].content)
    assert tool_body["tools"]
    native_body = json.loads(async_delegate.requests[1].content)
    assert native_body["response_format"]["type"] == "json_schema"


class _BlockedLiveFakeStream:
    """Fake live stream: one nonempty delta, then a blocked read until cancel."""

    def __init__(self) -> None:
        self.read_cancelled = asyncio.Event()
        self.closed = asyncio.Event()
        self._emitted = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._emitted:
            self._emitted = True
            return "1"
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.read_cancelled.set()
            raise
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.closed.set()


@pytest.mark.asyncio
async def test_cancel_stream_live_cancels_after_first_delta_without_retry():
    streams: list[_BlockedLiveFakeStream] = []

    def make_stream() -> _BlockedLiveFakeStream:
        stream = _BlockedLiveFakeStream()
        streams.append(stream)
        return stream

    outcome = await HARNESS.cancel_stream_live(make_stream, settle_seconds=0.01)
    assert outcome == HARNESS.CANCELLED_LIVE_OUTCOME
    assert len(streams) == 1  # no retry after content: exactly one stream opened
    # Where the cancel lands is best-effort in live mode (see the nine-op
    # test note); the guarantee is one stream, cancelled and closed.
    assert streams[0].closed.is_set()


class _NeverYieldingLiveStream:
    """Fake live stream whose first upstream read blocks forever (timeout path)."""

    def __init__(self) -> None:
        self.read_cancelled = asyncio.Event()
        self.closed = asyncio.Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.read_cancelled.set()
            raise
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.closed.set()


@pytest.mark.asyncio
async def test_cancel_stream_live_times_out_failing_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(HARNESS, "REQUEST_TIMEOUT_SECONDS", 0.05)
    stream = _NeverYieldingLiveStream()
    with pytest.raises(asyncio.TimeoutError):
        await HARNESS.cancel_stream_live(lambda: stream, settle_seconds=0.01)
    # Fail closed: the pending consumer task was cancelled and its stream closed.
    assert stream.read_cancelled.is_set()
    assert stream.closed.is_set()


class _EmptyFirstDeltaLiveStream:
    """Fake live stream whose first delta is empty (must fail closed)."""

    def __init__(self) -> None:
        self.closed = asyncio.Event()
        self._emitted = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._emitted:
            self._emitted = True
            return ""
        return "2"

    async def aclose(self) -> None:
        self.closed.set()


@pytest.mark.asyncio
async def test_cancel_stream_live_fails_closed_on_empty_first_delta(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(HARNESS, "REQUEST_TIMEOUT_SECONDS", 0.05)
    stream = _EmptyFirstDeltaLiveStream()
    with pytest.raises(HARNESS.SmokeHarnessError) as excinfo:
        await HARNESS.cancel_stream_live(lambda: stream, settle_seconds=0.01)
    assert excinfo.value.reason == "empty_first_stream_delta"
    assert stream.closed.is_set()


def test_stage_a_ops_live_mirror_offline_operation_shape():
    offline = [(spec.name, spec.provider, spec.structured_mode) for spec in HARNESS._STAGE_A_OPS]
    live = [(spec.name, spec.provider, spec.structured_mode) for spec in HARNESS._STAGE_A_OPS_LIVE]
    assert live == offline
    assert len(live) == 9
    assert {mode for _, _, mode in live if mode is not None} == set(HARNESS.STRUCTURED_MODES)


@pytest.mark.asyncio
async def test_run_stage_a_live_nine_ops_over_fake_delegates_with_timings(
    monkeypatch: pytest.MonkeyPatch,
):
    # Cancel legs are the 3rd and 6th overall requests; drain legs complete.
    async_delegate = _LiveFakeAsyncDelegate(block_stream_request_numbers={3, 6})
    sync_delegate = _RecordingSyncDelegate()
    _patch_live_delegates(monkeypatch, sync_delegate, async_delegate)
    run = HARNESS.authorize_stage_a_live(
        owner_confirmed=True, environ={HARNESS.LIVE_API_KEY_ENV: "synthetic-live-key"}
    )
    metadata = await HARNESS.run_stage_a_live(run)

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
    assert outcomes["baseline_stream_cancel"] == HARNESS.CANCELLED_LIVE_OUTCOME
    assert outcomes["adapter_stream_cancel"] == HARNESS.CANCELLED_LIVE_OUTCOME
    assert all(outcomes[name] == "ok" for name in expected_ops if not name.endswith("cancel"))
    assert metadata["transport_mode"] == HARNESS.LIVE_TRANSPORT_MODE == "live_https_gate"
    assert metadata["quota_rates_basis"] == HARNESS.LIVE_QUOTA_RATES_BASIS
    assert metadata["admission"]["billing_cap_claim"] is None
    for op in metadata["ops"]:
        assert isinstance(op["duration_seconds"], float)
        if op["op"].endswith("_stream") and not op["op"].endswith("cancel"):
            assert isinstance(op["first_delta_seconds"], float)
        else:
            assert "first_delta_seconds" not in op
    # Nine admitted POSTs over the fake delegate; the cancel legs consumed
    # nothing from the (default empty) cancel_read_signals queue - they ran.
    assert len(async_delegate.requests) == 9
    assert sync_delegate.requests == []
    assert all(str(request.url) == GO_CHAT_COMPLETIONS for request in async_delegate.requests)
    assert metadata["admission"]["post_attempts_admitted"] == 9
    assert metadata["admission"]["missing_usage_count"] == 2
    # Live-mode cancellation is best-effort by design: WHERE the cancel lands
    # (blocked read vs. settle sleep) is not deterministic without the offline
    # pre-allocated read signals, so the blocked-read delivery proof is owned
    # by the offline tests. The live contract: the stream was cancelled, its
    # body closed, and no retry was sent (exactly nine requests above).
    assert len(async_delegate.blocked_bodies) == 2
    for fake in async_delegate.blocked_bodies:
        assert fake.closed.is_set()


@pytest.mark.asyncio
async def test_live_run_metadata_never_contains_canary_key_or_conversation_id(
    monkeypatch: pytest.MonkeyPatch,
):
    canary = "qna-live-canary-never-in-metadata"
    api_key = "synthetic-live-credential-9f2b"
    async_delegate = _LiveFakeAsyncDelegate(text_content=canary)
    _patch_live_delegates(monkeypatch, _RecordingSyncDelegate(), async_delegate)
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()
    baseline = await HARNESS.build_baseline_qwen_client_live(
        api_key=api_key, admission=admission, session=session
    )
    adapter = await HARNESS.build_adapter_pydantic_ai_client_live(
        api_key=api_key, admission=admission, session=session
    )
    harness = HARNESS.StageAHarness(
        baseline=baseline,
        adapter=adapter,
        admission=admission,
        session=session,
    )
    try:
        metadata = await HARNESS.run_stage_a_operations(
            harness,
            ops=(HARNESS._STAGE_A_OPS_LIVE[0],),
            transport_mode=HARNESS.LIVE_TRANSPORT_MODE,
            timings=True,
            quota_rates_basis=HARNESS.LIVE_QUOTA_RATES_BASIS,
        )
    finally:
        await harness.aclose()
    assert metadata["ops"][0]["outcome"] == "ok"
    dump = json.dumps(metadata)
    assert canary not in dump
    assert api_key not in dump
    assert session.conversation_id not in dump
    assert session.opaque_session() not in dump


@pytest.mark.asyncio
async def test_authorize_stage_a_live_refuses_without_owner_confirmation():
    environ = {HARNESS.LIVE_API_KEY_ENV: "synthetic-live-key"}
    with pytest.raises(HARNESS.SmokeHarnessError) as excinfo:
        HARNESS.authorize_stage_a_live(owner_confirmed=False, environ=environ)
    assert excinfo.value.reason == "owner_confirmation_required"
    # Refusal precedes credential resolution entirely.
    with pytest.raises(HARNESS.SmokeHarnessError) as missing:
        HARNESS.authorize_stage_a_live(owner_confirmed=True, environ={})
    assert missing.value.reason == "missing_live_api_key_env"


@pytest.mark.asyncio
async def test_live_identity_scan_rejects_raw_conversation_id_anywhere_on_wire(
    monkeypatch: pytest.MonkeyPatch,
):
    """P2 review repair: raw-ID enforcement spans URL, header names, body."""
    session = HARNESS.fresh_stage_a_session()
    raw = session.conversation_id
    opaque = session.opaque_session()
    admission = _admission()
    async_delegate = _LiveFakeAsyncDelegate()
    transport = HARNESS.AsyncLiveGateTransport(
        admission,
        expected_user_agent=pydantic_ai_client.USER_AGENT,
        expected_session=session,
        delegate=async_delegate,
    )

    def make_request(url: str, extra_headers: dict[str, str] | None = None, body: bytes = b"{}"):
        return httpx.Request(
            "POST",
            url,
            headers={
                "User-Agent": pydantic_ai_client.USER_AGENT,
                HARNESS.SESSION_HEADER: opaque,
                **(extra_headers or {}),
            },
            content=body,
        )

    base_url = GO_CHAT_COMPLETIONS
    variants = {
        "url_substring": make_request(f"{base_url}?trace={raw}"),
        "header_name": make_request(base_url, extra_headers={f"x-{raw}": "1"}),
        "header_value_substring": make_request(base_url, extra_headers={"x-trace": f"pre-{raw}"}),
        "body": make_request(base_url, body=json.dumps({"user": raw}).encode("utf-8")),
    }
    for label, request in variants.items():
        with pytest.raises(HARNESS.AdmissionError) as excinfo:
            await transport.handle_async_request(request)
        assert excinfo.value.reason == "raw_conversation_id_on_wire", label
    assert async_delegate.requests == []  # refused BEFORE delegation, zero calls


@pytest.mark.asyncio
async def test_live_run_metadata_records_live_handler_boundary(
    monkeypatch: pytest.MonkeyPatch,
):
    # Through the real gated live runner: the live handler_boundary value
    # must reach the metadata (never the offline no-I/O description).
    async_delegate = _LiveFakeAsyncDelegate()
    _patch_live_delegates(monkeypatch, _RecordingSyncDelegate(), async_delegate)
    run = HARNESS.authorize_stage_a_live(
        owner_confirmed=True, environ={HARNESS.LIVE_API_KEY_ENV: "synthetic-live-key"}
    )
    metadata = await HARNESS.run_stage_a_live(run)
    assert metadata["handler_boundary"] == "live_https_delegate_gate_only_no_retention"
    assert metadata["transport_mode"] == HARNESS.LIVE_TRANSPORT_MODE
    assert metadata["quota_rates_basis"] == HARNESS.LIVE_QUOTA_RATES_BASIS
    assert metadata["admission"]["post_attempts_admitted"] == 9


@pytest.mark.asyncio
async def test_baseline_live_builder_failure_closes_adopted_delegates(
    monkeypatch: pytest.MonkeyPatch,
):
    """P2 review repair: construction failure must not leak the delegates."""
    sync_delegate = _RecordingSyncDelegate()
    async_delegate = _LiveFakeAsyncDelegate()
    _patch_live_delegates(monkeypatch, sync_delegate, async_delegate)
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()

    import openai as openai_module

    def _explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("synthetic construction failure")

    monkeypatch.setattr(openai_module, "AsyncOpenAI", _explode)
    with pytest.raises(RuntimeError):
        await HARNESS.build_baseline_qwen_client_live(
            api_key="synthetic-live-key", admission=admission, session=session
        )
    # The awaited cleanup chain reached both adopted transports' delegates.
    assert sync_delegate.closed.is_set()
    assert async_delegate.closed.is_set()


@pytest.mark.asyncio
async def test_adapter_live_builder_failure_closes_adopted_delegate(
    monkeypatch: pytest.MonkeyPatch,
):
    sync_delegate = _RecordingSyncDelegate()
    async_delegate = _LiveFakeAsyncDelegate()
    _patch_live_delegates(monkeypatch, sync_delegate, async_delegate)
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()

    import openai as openai_module

    def _explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("synthetic construction failure")

    monkeypatch.setattr(openai_module, "AsyncOpenAI", _explode)
    with pytest.raises(RuntimeError):
        await HARNESS.build_adapter_pydantic_ai_client_live(
            api_key="synthetic-live-key", admission=admission, session=session
        )
    assert async_delegate.closed.is_set()


def test_stage_a_live_run_handle_rejects_forgery_and_redacts_representation():
    """Direct construction fails closed; the repr never exposes the key."""
    with pytest.raises(HARNESS.SmokeHarnessError) as excinfo:
        HARNESS.StageALiveRun(api_key="raw-forged-key")
    assert excinfo.value.reason == "unauthorized_live_run_handle"
    run = HARNESS.authorize_stage_a_live(
        owner_confirmed=True, environ={HARNESS.LIVE_API_KEY_ENV: "synthetic-secret-key"}
    )
    assert run.api_key == "synthetic-secret-key"
    assert "synthetic-secret-key" not in repr(run)
    assert repr(run) == "StageALiveRun(<authorized-redacted>)"


@pytest.mark.asyncio
async def test_baseline_live_builder_failure_creating_second_transport_closes_first(
    monkeypatch: pytest.MonkeyPatch,
):
    """A failure constructing the async transport must not leak the sync one."""
    sync_delegate = _RecordingSyncDelegate()
    async_delegate = _LiveFakeAsyncDelegate()
    _patch_live_delegates(monkeypatch, sync_delegate, async_delegate)
    admission = _admission()
    session = HARNESS.fresh_stage_a_session()

    real_sync_cls, _real_async_cls = HARNESS._live_transport_classes()

    class _ExplodingAsyncTransport:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("synthetic transport failure")

    monkeypatch.setattr(
        HARNESS, "_live_transport_classes", lambda: (real_sync_cls, _ExplodingAsyncTransport)
    )
    with pytest.raises(RuntimeError):
        await HARNESS.build_baseline_qwen_client_live(
            api_key="synthetic-live-key", admission=admission, session=session
        )
    assert sync_delegate.closed.is_set()
    # The exploding async transport never got a delegate to close.
    assert not async_delegate.closed.is_set()


@pytest.mark.asyncio
async def test_run_stage_a_operations_attaches_partial_metadata_on_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    """Fail fast AND report incompleteness: partial metadata must survive."""
    async_delegate = _LiveFakeAsyncDelegate()
    _patch_live_delegates(monkeypatch, _RecordingSyncDelegate(), async_delegate)
    run = HARNESS.authorize_stage_a_live(
        owner_confirmed=True, environ={HARNESS.LIVE_API_KEY_ENV: "synthetic-live-key"}
    )
    # The very first op raises a non-harness exception (route capability
    # rejection shape); the partial metadata must still be attached.
    original = HARNESS._STAGE_A_OPS_LIVE
    failing_first = HARNESS._OpSpec(
        "baseline_text",
        "baseline-qwen",
        None,
        lambda harness: (_ for _ in ()).throw(RuntimeError("synthetic rejection")),
    )
    monkeypatch.setattr(HARNESS, "_STAGE_A_OPS_LIVE", (failing_first, *original[1:]))
    with pytest.raises(RuntimeError) as excinfo:
        await HARNESS.run_stage_a_live(run)
    partial = getattr(excinfo.value, "partial_metadata", None)
    assert isinstance(partial, dict)
    # The failed op is recorded with its sanitized error identity only.
    assert [op["op"] for op in partial["ops"]] == ["baseline_text"]
    assert partial["ops"][0]["outcome"] == "error"
    assert partial["ops"][0]["error_kind"] == "RuntimeError"
    assert partial["admission"]["post_attempts_admitted"] == 0
    assert "frozen_hashes" in partial


def test_main_prints_incomplete_partial_report_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setenv(HARNESS.LIVE_API_KEY_ENV, "synthetic-live-key")

    class _RouteRejection(RuntimeError):
        pass

    def _run_with_partial(run: Any) -> Any:
        raise _RouteRejection("detail-never-printed")

    async def _runner(run: Any) -> dict[str, Any]:
        return _run_with_partial(run)

    def _boom(run: Any) -> dict[str, Any]:
        exc = _RouteRejection("detail-never-printed")
        exc.partial_metadata = {"ops": [{"op": "baseline_text", "outcome": "ok"}]}  # type: ignore[attr-defined]
        raise exc

    monkeypatch.setattr(HARNESS, "run_stage_a_live", _boom)
    assert HARNESS.main(["--live", "--owner-confirmed"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "incomplete"
    assert payload["error_kind"] == "_RouteRejection"
    assert payload["partial_metadata"]["ops"][0]["op"] == "baseline_text"
    assert "detail-never-printed" not in json.dumps(payload)

    # Without partial metadata the failure path stays sanitized type-only.
    monkeypatch.setattr(HARNESS, "run_stage_a_live", _runner)
    assert HARNESS.main(["--live", "--owner-confirmed"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "_RouteRejection\n"
