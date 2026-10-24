#!/usr/bin/env python3
"""Bounded OFFLINE P4-D Stage A smoke harness (owner-approved code slice only).

Implements the harness slice described in
``docs/plans/migration/20261021-phase4d-stage-a-execution-addendum.md``:

- Exactly the OpenCode Go route ``https://opencode.ai/inference/go/openai/v1``
  and generator ``mimo-v2.6-flash`` for both implementations: the existing
  baseline ``QwenClient`` versus the opt-in ``PydanticAIClient`` adapter.
- Nine sequential logical operations: text, stream and cancellation while
  blocked awaiting the next upstream delta, per implementation, then the
  existing JSON-object structured output (baseline), adapter tool structured
  output, and native-json-schema structured output (adapter).
- One total transport attempt per call (SDK ``max_retries=0`` plus dedicated
  harness client subclasses whose async methods run as isolated per-instance
  copies binding the client module's ``settings`` global to a per-instance
  view with ``retry.max_retries == 1``), and structured output repair
  explicitly capped at one extra call. No module-level settings object is ever
  mutated; the shared ``src.config.settings`` singleton is untouched, and
  overlapping harness runs cannot observe each other's configuration.
- Narrowed offline guarantee — SDK transport only: the builders accept a
  synthetic handler plus the shared admission and construct the only permitted
  SDK transport themselves — a harness-owned in-memory ``httpx.MockTransport``.
  No ``httpx`` transport can be injected, so every SDK request rides the same
  in-memory admission gate. This is NOT an unconditional offline claim about
  arbitrary code: the synthetic handler is TRUSTED caller code explicitly
  outside the guarantee — it receives the full request (including the
  Authorization header and body), so it must not perform I/O, must not retain
  requests, and harness runs must be OS-isolated. Before shared admission runs
  on every request, the transport validates the exact per-implementation
  honest User-Agent and the opaque session header (never the raw conversation
  id); the adapter boundary therefore requires ``conversation_scope`` or every
  request is refused.
- Awaited construction cleanup: both builders are ``async``. If a constructor
  fails after earlier resources were allocated, the builder awaits their close
  on the owning loop before re-raising — no detached background cleanup task
  exists.
- One shared transport admission: at most 12 outbound generation POSTs across
  all nine operations (transport retries and structured repairs alike); the
  13th request is refused inside the transport before the synthetic handler
  runs. Each admitted request records the SHA-256 digest of its exact outbound
  wire payload (digest only; the body itself is never stored) and a synthetic
  admission reservation computed from the declared offline ceilings
  (4096-byte input, 2048-token output) at owner-supplied offline rates,
  accounted with ``Decimal``. Missing usage retains its reservation;
  reservations are never released. These are synthetic offline admission
  allocations, NOT model token counts and NOT billing guarantees.

Synthetic offline byte ceiling: the full outbound JSON body must round-trip as
ASCII and be at most 4096 bytes. This bounds the offline harness's request
shape only; it is NOT a model input-token bound, no tokenization or billing
claim is made, and live token/billing accounting is unavailable.

Fail-fast runs: the first operation error (authentication, route, capability
or otherwise) stops the run immediately and re-raises; no further request is
sent after a rejection.

LIVE EXECUTION IS NOT IMPLEMENTED AND FAILS CLOSED. ``main()`` refuses
unconditionally: account/quota confirmations and a separate stage-specific run
approval are still required (see the execution addendum). Nothing in this
module reads environment variables, ``.env``, or any credential store, and the
runtime key is accepted only as an explicit in-memory argument that must be a
synthetic value — never provide real keys to the offline harness.

Privacy: no prompt, response, header, session, or key value is ever logged or
returned; metadata is sanitized counts, fixed strings, Decimal amounts and
SHA-256 digests only. Each run derives a fresh conversation id (a fresh UUID,
never persisted or sent raw); only its opaque per-conversation hash reaches the
wire as ``x-opencode-session``.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import sys
import time
import types
import uuid
from collections.abc import Awaitable, Callable
from contextlib import aclosing, suppress
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from queue import SimpleQueue
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# PEP 563 string annotations make @dataclass resolve ClassVar/InitVar through
# ``sys.modules[__name__].__dict__`` during class creation. Spec-based
# execution without loader registration (the lightweight-import probe) must
# still find an entry here, or ``dataclasses`` crashes on
# ``sys.modules.get(cls.__module__).__dict__``. Loaders that register the real
# module first (runpy, the test loader) are untouched by ``setdefault``.
sys.modules.setdefault(__name__, types.ModuleType(__name__))

# --- frozen Stage A wire contract (execution addendum) ---
GO_BASE_URL = "https://opencode.ai/inference/go/openai/v1"
GO_MODEL = "mimo-v2.6-flash"
CHAT_COMPLETIONS_PATH = GO_BASE_URL + "/chat/completions"
SESSION_HEADER = "x-opencode-session"
TEMPERATURE = 0.7
MAX_OUTPUT_TOKENS = 2048
REQUEST_TIMEOUT_SECONDS = 30.0
# Synthetic offline request-shape ceiling: at most 4096 ASCII body bytes per
# admitted request. NOT a model input-token bound; no tokenization claim.
MAX_INPUT_BODY_BYTES = 4096
# At most 12 outbound POSTs across all nine operations (9 first calls plus up
# to 3 structured repairs); one total transport attempt per call.
MAX_POST_ATTEMPTS = 12
TOTAL_TRANSPORT_ATTEMPTS = 1
MAX_STRUCTURED_REPAIRS = 1
# Overall stop clock checked before each operation (addendum: 30-minute stop).
OVERALL_STOP_SECONDS = 30 * 60.0
# Synthetic offline admission allocations, not a billing-cap claim.
QUOTA_VALUE_LIMIT = Decimal("1.00")
CASH_LIMIT = Decimal("0.00")

USER_AGENT_BASELINE = "qna-medical-referenced/0.1.0 (qwen baseline client; phase4d stage-a smoke)"
STRUCTURED_MODES = ("tool", "native-json-schema")

PROMPT_TEXT = "Reply with exactly: smoke ok"
PROMPT_STREAM = "Count from one to twenty, one number per line"

LIVE_EXECUTION_REFUSAL = (
    "phase4_go_smoke: LIVE EXECUTION IS BLOCKED. Stage A run approval is not granted; "
    "owner account/quota confirmations (addendum items 1-3) and a separate "
    "stage-specific run confirmation are required first. This slice provides the "
    "offline harness components only; no live CLI entrypoint exists."
)


class SmokeHarnessError(Exception):
    """Fail-closed harness error carrying a fixed, content-free reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AdmissionError(SmokeHarnessError):
    """A request was refused by shared admission before leaving the process."""


@dataclass(frozen=True)
class QuotaRates:
    """Owner-supplied synthetic offline admission rates (per 1M units).

    Applied to the declared offline ceilings (4096-byte input, 2048-token
    output) purely to bound this harness's own admission allocation. These are
    NOT verified provider prices: no billing or tokenization claim is made,
    live accounting is unavailable, and live execution remains blocked.
    """

    input_per_million: Decimal
    output_per_million: Decimal
    cash_input_per_million: Decimal = Decimal("0")
    cash_output_per_million: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for value in (
            self.input_per_million,
            self.output_per_million,
            self.cash_input_per_million,
            self.cash_output_per_million,
        ):
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise SmokeHarnessError("invalid_quota_rate")


class TransportAdmission:
    """Shared POST cap plus synthetic Decimal admission reservations.

    Every outbound generation POST passes through :meth:`gate` inside the
    harness-owned transport before the synthetic handler runs. Admission
    records the SHA-256 digest of the exact outbound payload and reserves a
    synthetic allocation from the declared offline ceilings (``MAX_INPUT_BODY_BYTES``
    + ``MAX_OUTPUT_TOKENS``) at the supplied rates for every admitted request,
    including cancelled ones. Reported usage is recorded as sanitized metadata
    only; missing usage retains its reservation, and reservations are never
    released.
    """

    def __init__(
        self,
        rates: QuotaRates,
        *,
        quota_limit: Decimal = QUOTA_VALUE_LIMIT,
        cash_limit: Decimal = CASH_LIMIT,
        max_post_attempts: int = MAX_POST_ATTEMPTS,
    ) -> None:
        if not isinstance(rates, QuotaRates):
            raise SmokeHarnessError("owner_supplied_quota_rates_required")
        for value in (quota_limit, cash_limit):
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise SmokeHarnessError("invalid_admission_limit")
        if not isinstance(max_post_attempts, int) or isinstance(max_post_attempts, bool):
            raise SmokeHarnessError("invalid_post_cap")
        if max_post_attempts < 1:
            raise SmokeHarnessError("invalid_post_cap")
        self.rates = rates
        self.quota_limit = quota_limit
        self.cash_limit = cash_limit
        self.max_post_attempts = max_post_attempts
        million = Decimal(1_000_000)
        self.per_call_quota_reservation = (
            Decimal(MAX_INPUT_BODY_BYTES) * rates.input_per_million
            + Decimal(MAX_OUTPUT_TOKENS) * rates.output_per_million
        ) / million
        self.per_call_cash_reservation = (
            Decimal(MAX_INPUT_BODY_BYTES) * rates.cash_input_per_million
            + Decimal(MAX_OUTPUT_TOKENS) * rates.cash_output_per_million
        ) / million
        self._attempts = 0
        self._reserved_quota = Decimal("0")
        self._reserved_cash = Decimal("0")
        self._payload_digests: list[str] = []
        self._settlements: list[dict[str, Any]] = []

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def reserved_quota_value(self) -> Decimal:
        return self._reserved_quota

    @property
    def reserved_cash(self) -> Decimal:
        return self._reserved_cash

    def remaining_attempts(self) -> int:
        return self.max_post_attempts - self._attempts

    def payload_digests(self) -> tuple[str, ...]:
        """SHA-256 digests of every admitted request's exact outbound payload."""
        return tuple(self._payload_digests)

    def gate(self, method: str, url: str, body: bytes) -> None:
        """Validate and admit one outbound request; raise before any send."""
        if method.upper() != "POST":
            raise AdmissionError("non_post_request")
        if url != CHAT_COMPLETIONS_PATH:
            raise AdmissionError("route_not_allowlisted")
        try:
            body.decode("ascii")
        except UnicodeDecodeError:
            raise AdmissionError("request_body_not_ascii") from None
        if len(body) > MAX_INPUT_BODY_BYTES:
            raise AdmissionError("request_body_exceeds_byte_ceiling")
        if self._attempts >= self.max_post_attempts:
            raise AdmissionError("post_cap_reached")
        if self._reserved_quota + self.per_call_quota_reservation > self.quota_limit:
            raise AdmissionError("quota_reservation_exceeded")
        if self._reserved_cash + self.per_call_cash_reservation > self.cash_limit:
            raise AdmissionError("cash_reservation_exceeded")
        self._attempts += 1
        self._reserved_quota += self.per_call_quota_reservation
        self._reserved_cash += self.per_call_cash_reservation
        # Freeze the exact wire payload as a digest only (never the body).
        self._payload_digests.append(hashlib.sha256(body).hexdigest())

    def settle(
        self,
        *,
        reported_input_tokens: int | None,
        reported_output_tokens: int | None,
    ) -> None:
        """Record reported usage as metadata; never release reservations."""
        usage_reported = (
            isinstance(reported_input_tokens, int)
            and not isinstance(reported_input_tokens, bool)
            and reported_input_tokens >= 0
            and isinstance(reported_output_tokens, int)
            and not isinstance(reported_output_tokens, bool)
            and reported_output_tokens >= 0
        )
        self._settlements.append(
            {
                "usage_reported": usage_reported,
                "input_tokens": reported_input_tokens if usage_reported else None,
                "output_tokens": reported_output_tokens if usage_reported else None,
            }
        )

    @property
    def missing_usage_count(self) -> int:
        return sum(1 for item in self._settlements if not item["usage_reported"])

    def metadata(self) -> dict[str, Any]:
        return {
            "post_cap": self.max_post_attempts,
            "post_attempts_admitted": self._attempts,
            "post_attempts_remaining": self.remaining_attempts(),
            "per_call_input_ceiling_bytes": MAX_INPUT_BODY_BYTES,
            "per_call_output_ceiling_tokens": MAX_OUTPUT_TOKENS,
            "reserved_quota_value": str(self._reserved_quota),
            "quota_value_limit": str(self.quota_limit),
            "reserved_cash": str(self._reserved_cash),
            "cash_limit": str(self.cash_limit),
            "settlements": list(self._settlements),
            "missing_usage_count": self.missing_usage_count,
            "billing_cap_claim": None,
        }


@dataclass(frozen=True)
class StageASession:
    """Per-run identity: a fresh conversation id, never logged or sent raw."""

    conversation_id: str

    def opaque_session(self) -> str:
        """Opaque stable per-conversation header value (the only wire form)."""
        _ensure_project_on_path()
        from src.infra.llm.conversation_context import opaque_session_id

        return opaque_session_id(self.conversation_id)


def fresh_stage_a_session() -> StageASession:
    return StageASession(conversation_id=str(uuid.uuid4()))


_answer_model_cache: list[type[Any]] = []


def smoke_answer_model() -> type[Any]:
    """Frozen structured schema: one required ``answer`` string, closed."""
    if _answer_model_cache:
        return _answer_model_cache[0]
    from pydantic import BaseModel, ConfigDict

    class SmokeAnswer(BaseModel):
        model_config = ConfigDict(extra="forbid")

        answer: str

    _answer_model_cache.append(SmokeAnswer)
    return SmokeAnswer


def frozen_input_hashes() -> dict[str, str]:
    """SHA-256 digests of the frozen prompt components and canonical schema.

    The exact per-request wire payloads are frozen separately: the shared
    admission records the digest of every admitted request's exact outbound
    body (see ``TransportAdmission.payload_digests``).
    """
    _ensure_project_on_path()
    from src.infra.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

    schema_json = json.dumps(
        smoke_answer_model().model_json_schema(),
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "system_prompt_sha256": _sha256(SYSTEM_PROMPT),
        "user_prompt_template_sha256": _sha256(USER_PROMPT_TEMPLATE),
        "prompt_text_sha256": _sha256(PROMPT_TEXT),
        "prompt_stream_sha256": _sha256(PROMPT_STREAM),
        "answer_schema_sha256": _sha256(schema_json),
    }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_project_on_path() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


def offline_transport(
    handler: Callable[[Any], Any],
    admission: TransportAdmission,
    *,
    expected_user_agent: str,
    expected_session: StageASession,
) -> Any:
    """Harness-owned in-memory ``httpx.MockTransport`` (the only transport).

    Every request is validated against the run's identity headers BEFORE the
    shared admission runs: the exact per-implementation honest User-Agent and
    the opaque session header must be present and correct, and the raw
    conversation id must not appear anywhere in the headers. The gate then
    enforces the POST cap, exact route, ASCII byte ceiling and reservations
    before the synthetic handler is called. A ``MockTransport`` never opens a
    socket, so the SDK request path stays in memory. The trusted handler is
    explicitly outside this guarantee: it must not perform I/O, must not
    retain requests, and it runs OS-isolated.
    """
    import httpx

    if not isinstance(expected_session, StageASession):
        raise SmokeHarnessError("missing_or_invalid_session")
    expected_opaque = expected_session.opaque_session()
    raw_conversation_id = expected_session.conversation_id

    def gated(request: httpx.Request) -> Any:
        if request.headers.get("user-agent") != expected_user_agent:
            raise AdmissionError("unexpected_user_agent")
        if request.headers.get(SESSION_HEADER) != expected_opaque:
            raise AdmissionError("session_header_missing_or_mismatch")
        if raw_conversation_id in request.headers.values():
            raise AdmissionError("raw_conversation_id_on_wire")
        admission.gate(request.method, str(request.url), request.content)
        return handler(request)

    return httpx.MockTransport(gated)


def _require_offline_wiring(
    *,
    api_key: str | None,
    handler: Any,
    admission: Any,
    session: Any,
) -> None:
    """Fail fast unless every harness-owned wiring input is present and typed."""
    if not isinstance(api_key, str) or not api_key:
        raise SmokeHarnessError("missing_runtime_api_key")
    if not callable(handler):
        raise SmokeHarnessError("missing_or_invalid_handler")
    if not isinstance(admission, TransportAdmission):
        raise SmokeHarnessError("missing_or_invalid_admission")
    if not isinstance(session, StageASession):
        raise SmokeHarnessError("missing_or_invalid_session")


def _per_instance_settings_view() -> SimpleNamespace:
    """Per-instance stand-in for the client modules' ``settings`` global.

    Pins one total transport attempt (``retry.max_retries == 1``) with no retry
    delay. Each harness client's isolated method copies bind this view instead
    of the module global, so no shared module state is ever mutated and
    overlapping runs observe only their own view.
    """
    return SimpleNamespace(
        retry=SimpleNamespace(max_retries=TOTAL_TRANSPORT_ATTEMPTS, retry_delay=0.0),
    )


def _isolated_settings_method(
    owner: type[Any], name: str, settings_view: SimpleNamespace, instance: Any
) -> Any:
    """Bind a copy of a production client method to a per-instance settings view.

    The harness runs the production implementations unchanged; only the client
    module's ``settings`` global reference is replaced with the instance's view
    in the copy's globals. The real module globals are never read as harness
    configuration nor mutated, so this replaces the former (racy) module
    settings swap with actual instance isolation.
    """
    func = owner.__dict__[name]
    isolated_globals = dict(func.__globals__)
    isolated_globals["settings"] = settings_view
    copied = types.FunctionType(
        func.__code__, isolated_globals, func.__name__, func.__defaults__, func.__closure__
    )
    return types.MethodType(copied, instance)


_harness_qwen_client_class_cache: list[type[Any]] = []


def _harness_qwen_client_class() -> type[Any]:
    """Dedicated baseline subclass with per-instance settings isolation."""
    if _harness_qwen_client_class_cache:
        return _harness_qwen_client_class_cache[0]
    _ensure_project_on_path()
    from src.infra.llm import qwen_client

    class _HarnessQwenClient(qwen_client.QwenClient):
        """Baseline client running the production async methods unchanged.

        Each instance gets copies of exactly the methods that read the client
        module's ``settings`` global for retry bounds; the copies bind the
        per-instance view instead, so no module settings swap exists.
        """

        def __init__(self, settings_view: SimpleNamespace) -> None:
            self._settings_view = settings_view
            for name in ("a_generate", "a_generate_stream", "a_generate_structured"):
                setattr(
                    self,
                    name,
                    _isolated_settings_method(qwen_client.QwenClient, name, settings_view, self),
                )

    _harness_qwen_client_class_cache.append(_HarnessQwenClient)
    return _HarnessQwenClient


_harness_adapter_client_class_cache: list[type[Any]] = []


def _harness_adapter_client_class() -> type[Any]:
    """Dedicated adapter subclass with per-instance settings isolation."""
    if _harness_adapter_client_class_cache:
        return _harness_adapter_client_class_cache[0]
    _ensure_project_on_path()
    from src.infra.llm import pydantic_ai_client

    class _HarnessAdapterClient(pydantic_ai_client.PydanticAIClient):
        """Adapter client with per-instance structured-mode selection.

        The production async methods run as isolated copies bound to the
        per-instance settings view; the structured agent is selected from the
        prebuilt per-instance map by ``structured_mode`` (never from shared
        settings) and fails closed on an unknown mode.
        """

        def __init__(self, settings_view: SimpleNamespace) -> None:
            self._settings_view = settings_view
            self.structured_mode: str = "tool"
            for name in ("a_generate", "a_generate_stream", "a_generate_structured"):
                setattr(
                    self,
                    name,
                    _isolated_settings_method(
                        pydantic_ai_client.PydanticAIClient, name, settings_view, self
                    ),
                )

        def _structured_agent(self, response_model: Any) -> Any:
            agent = self._structured_agents.get((response_model, self.structured_mode))
            if agent is None:
                raise SmokeHarnessError("unsupported_structured_mode")
            return agent

    _harness_adapter_client_class_cache.append(_HarnessAdapterClient)
    return _HarnessAdapterClient


async def _aclose_resources(resources: list[Any]) -> None:
    """Best-effort close; construction-failure cleanup never masks the error.

    Builders await this directly on the owning loop before re-raising, so
    every allocated resource is fully closed before the failure escapes the
    setup boundary; no background cleanup task is scheduled.
    """
    for resource in resources:
        with suppress(Exception):
            aclose = getattr(resource, "aclose", None)
            if aclose is not None:
                await aclose()
            else:
                close = getattr(resource, "close", None)
                if close is not None:
                    result = close()
                    if inspect.isawaitable(result):
                        await result


async def build_baseline_qwen_client(
    *,
    api_key: str,
    handler: Callable[[Any], Any],
    admission: TransportAdmission,
    session: StageASession,
) -> Any:
    """Existing ``QwenClient`` wired process-locally to the exact Go route.

    Built as a dedicated subclass instance so retry bounds come from a
    per-instance settings view (no module settings are mutated). The builder
    itself constructs the only permitted SDK transport — a harness-owned
    in-memory ``httpx.MockTransport`` whose gate validates this client's
    honest User-Agent and the opaque session header before shared admission —
    so no caller-supplied transport can enter the harness and every SDK
    request rides the in-memory admission gate. The trusted synthetic handler
    is explicitly outside this guarantee (no I/O, no request retention,
    OS-isolated runs). Honest identity headers are client default headers; the
    runtime key lives only in memory. On construction failure the builder
    awaits cleanup of the resources allocated so far before re-raising.
    """
    _require_offline_wiring(api_key=api_key, handler=handler, admission=admission, session=session)
    _ensure_project_on_path()
    import httpx
    from openai import AsyncOpenAI, OpenAI

    transport = offline_transport(
        handler,
        admission,
        expected_user_agent=USER_AGENT_BASELINE,
        expected_session=session,
    )
    # Narrowed SDK-transport guarantee: harness-built in-memory MockTransport.
    if not isinstance(transport, httpx.MockTransport):
        raise SmokeHarnessError("non_mock_transport_refused")

    headers = {
        "User-Agent": USER_AGENT_BASELINE,
        SESSION_HEADER: session.opaque_session(),
    }
    settings_view = _per_instance_settings_view()
    client = _harness_qwen_client_class()(settings_view)
    client.model = GO_MODEL
    allocated: list[Any] = []
    try:
        sync_http = httpx.Client(
            transport=transport,
            follow_redirects=False,
            trust_env=False,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        allocated.append(sync_http)
        client.client = OpenAI(
            base_url=GO_BASE_URL,
            api_key=api_key,
            http_client=sync_http,
            default_headers=headers,
            max_retries=0,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        allocated.append(client.client)
        async_http = httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            trust_env=False,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        allocated.append(async_http)
        client.async_client = AsyncOpenAI(
            base_url=GO_BASE_URL,
            api_key=api_key,
            http_client=async_http,
            default_headers=headers,
            max_retries=0,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except BaseException:
        await _aclose_resources(allocated)
        raise
    return client


async def build_adapter_pydantic_ai_client(
    *,
    api_key: str,
    handler: Callable[[Any], Any],
    admission: TransportAdmission,
    session: StageASession,
) -> Any:
    """Existing ``PydanticAIClient`` wired process-locally to the Go route.

    Same per-instance isolation and builder-owned in-memory ``MockTransport``
    as the baseline builder; the gate enforces the adapter's honest User-Agent and
    the opaque session header, so the run boundary must bind
    ``conversation_scope`` for the session identity or every request is
    refused before admission. Identity headers stay request-scoped inside the
    client. Structured agents are pre-built with the repair budget explicitly
    pinned to at most one retry on both modes and selected per instance via
    ``structured_mode`` (never via shared settings). The trusted handler and
    awaited construction-failure cleanup follow the baseline builder's
    narrowed guarantee.
    """
    _require_offline_wiring(api_key=api_key, handler=handler, admission=admission, session=session)
    _ensure_project_on_path()
    import httpx
    from openai import AsyncOpenAI
    from pydantic_ai import Agent, NativeOutput, ToolOutput
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    from src.infra.llm import pydantic_ai_client
    from src.infra.llm.prompts import SYSTEM_PROMPT

    answer = smoke_answer_model()
    transport = offline_transport(
        handler,
        admission,
        expected_user_agent=pydantic_ai_client.USER_AGENT,
        expected_session=session,
    )
    # Narrowed SDK-transport guarantee: harness-built in-memory MockTransport.
    if not isinstance(transport, httpx.MockTransport):
        raise SmokeHarnessError("non_mock_transport_refused")

    settings_view = _per_instance_settings_view()
    client = _harness_adapter_client_class()(settings_view)
    client.model = GO_MODEL
    client._temperature = TEMPERATURE
    client._max_tokens = MAX_OUTPUT_TOKENS
    client._raw_prompt = False
    client._timeout = REQUEST_TIMEOUT_SECONDS
    allocated: list[Any] = []
    try:
        http_client = httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            trust_env=False,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        allocated.append(http_client)
        client._http_client = http_client
        sdk = AsyncOpenAI(
            base_url=GO_BASE_URL,
            api_key=api_key,
            http_client=http_client,
            max_retries=0,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        client._openai_client = sdk
        model = OpenAIChatModel(GO_MODEL, provider=OpenAIProvider(openai_client=sdk))
        client._model = model
        client._text_agent = Agent(model, instructions=SYSTEM_PROMPT)
        client._structured_agents = {
            (answer, "tool"): Agent(
                model,
                output_type=ToolOutput(answer, max_retries=MAX_STRUCTURED_REPAIRS),
                instructions=SYSTEM_PROMPT,
                retries=MAX_STRUCTURED_REPAIRS,
            ),
            (answer, "native-json-schema"): Agent(
                model,
                output_type=NativeOutput([answer]),
                instructions=SYSTEM_PROMPT,
                retries=MAX_STRUCTURED_REPAIRS,
            ),
        }
    except BaseException:
        await _aclose_resources(allocated)
        raise
    return client


@dataclass(frozen=True)
class StageAHarness:
    """Wired clients plus the one shared admission for a single offline run.

    Both clients are dedicated harness subclasses configured per instance;
    ``aclose`` closes both on the owning loop (drain SDK resources).
    """

    baseline: Any
    adapter: Any
    admission: TransportAdmission
    session: StageASession
    # Pre-allocated per-run cancel-leg read signals: the run's fake transport
    # body sets one exactly when its next upstream read is actually pending,
    # and each cancel helper awaits precisely that event — deterministic
    # synchronization with no settle-delay guessing. Empty by default; a
    # cancel leg without a pre-allocated signal fails closed.
    cancel_read_signals: Any = field(default_factory=SimpleQueue)

    async def aclose(self) -> None:
        """Close both clients on the owning loop (drain SDK resources)."""
        try:
            await self.baseline.aclose()
        finally:
            await self.adapter.aclose()


@dataclass(frozen=True)
class _OpSpec:
    name: str
    provider: str
    structured_mode: str | None
    # Structured factories resolve to the validated SmokeAnswer model, so the
    # awaitable result is Any; the runner only records sanitized outcomes.
    factory: Callable[[StageAHarness], Awaitable[Any]]


async def _drain_stream(make_stream: Callable[[], Any]) -> str:
    async with aclosing(make_stream()) as stream:
        async for _delta in stream:
            pass
    return "ok"


def _take_cancel_read_signal(harness: StageAHarness) -> asyncio.Event:
    """Pop this run's pre-allocated read signal for one cancel leg (fail closed)."""
    try:
        return harness.cancel_read_signals.get_nowait()
    except Exception:
        raise SmokeHarnessError("cancel_read_signal_missing") from None


async def cancel_stream_after_first_delta(
    make_stream: Callable[[], Any],
    *,
    pending_next_read: asyncio.Event,
) -> str:
    """Cancel a stream while it is blocked awaiting the next upstream delta.

    After the first nonempty delta the consumer does NOT stop: it requests the
    next item, so the next upstream read is actually entered and suspended.
    ``pending_next_read`` is the event the run's fake transport body sets
    exactly when that read is pending. ``Event.set`` never yields, so once
    this coroutine observes it, the consumer task is parked inside the blocked
    read and cancelling the task delivers CancelledError exactly there (the
    P4-B blocked-read regression); ``aclosing`` still runs the stream's
    close/drain path afterwards. The synchronization is fully deterministic —
    no settle delay is guessed — and with a body that never blocks the helper
    times out and fails closed instead of cancelling an already-tearing-down
    stream (a cancel landing mid-teardown explodes with cross-task anyio
    cancel-scope errors instead of delivering the blocked-read cancel).
    """
    first_delta = asyncio.Event()
    awaiting_next_delta = asyncio.Event()

    async def consume() -> None:
        async with aclosing(make_stream()) as stream:
            iterator = aiter(stream)
            first = await iterator.__anext__()
            if not first:
                raise SmokeHarnessError("empty_first_stream_delta")
            first_delta.set()
            awaiting_next_delta.set()
            # Suspended here, awaiting the next upstream delta, when cancelled.
            await iterator.__anext__()

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(first_delta.wait(), REQUEST_TIMEOUT_SECONDS)
        await asyncio.wait_for(awaiting_next_delta.wait(), REQUEST_TIMEOUT_SECONDS)
        # Cancel only at the actual pending read: the fake body set this event
        # immediately before suspending on its blocked await, so the consumer
        # is suspended there (no yield in between) when the cancel is sent.
        await asyncio.wait_for(pending_next_read.wait(), REQUEST_TIMEOUT_SECONDS)
    except BaseException:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        raise
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    return "cancelled_awaiting_next_delta"


# Fixed sanitized operation outcomes only. The text operations return the
# model's response string, which must never appear in metadata.
_OPERATION_OUTCOMES = frozenset({"ok", "cancelled_awaiting_next_delta"})

_STAGE_A_OPS: tuple[_OpSpec, ...] = (
    _OpSpec(
        "baseline_text",
        "baseline-qwen",
        None,
        lambda harness: harness.baseline.a_generate(PROMPT_TEXT, context=""),
    ),
    _OpSpec(
        "baseline_stream",
        "baseline-qwen",
        None,
        lambda harness: _drain_stream(
            lambda: harness.baseline.a_generate_stream(PROMPT_STREAM, context="")
        ),
    ),
    _OpSpec(
        "baseline_stream_cancel",
        "baseline-qwen",
        None,
        lambda harness: cancel_stream_after_first_delta(
            lambda: harness.baseline.a_generate_stream(PROMPT_STREAM, context=""),
            pending_next_read=_take_cancel_read_signal(harness),
        ),
    ),
    _OpSpec(
        "adapter_text",
        "adapter-pydantic-ai",
        None,
        lambda harness: harness.adapter.a_generate(PROMPT_TEXT, context=""),
    ),
    _OpSpec(
        "adapter_stream",
        "adapter-pydantic-ai",
        None,
        lambda harness: _drain_stream(
            lambda: harness.adapter.a_generate_stream(PROMPT_STREAM, context="")
        ),
    ),
    _OpSpec(
        "adapter_stream_cancel",
        "adapter-pydantic-ai",
        None,
        lambda harness: cancel_stream_after_first_delta(
            lambda: harness.adapter.a_generate_stream(PROMPT_STREAM, context=""),
            pending_next_read=_take_cancel_read_signal(harness),
        ),
    ),
    _OpSpec(
        "baseline_structured_json_object",
        "baseline-qwen",
        None,
        lambda harness: harness.baseline.a_generate_structured(
            PROMPT_TEXT, smoke_answer_model(), context=""
        ),
    ),
    _OpSpec(
        "adapter_structured_tool",
        "adapter-pydantic-ai",
        "tool",
        lambda harness: harness.adapter.a_generate_structured(
            PROMPT_TEXT, smoke_answer_model(), context=""
        ),
    ),
    _OpSpec(
        "adapter_structured_native_json_schema",
        "adapter-pydantic-ai",
        "native-json-schema",
        lambda harness: harness.adapter.a_generate_structured(
            PROMPT_TEXT, smoke_answer_model(), context=""
        ),
    ),
)


async def run_stage_a_operations(harness: StageAHarness) -> dict[str, Any]:
    """Run the nine Stage A operations sequentially; sanitized metadata only.

    Fail-fast: the first operation error (authentication, route, capability or
    otherwise) stops the run and re-raises; no later request is sent. All
    pre-checks (POST cap headroom, overall stop clock) happen before each
    network operation; the shared admission refuses any 13th POST inside the
    transport before the synthetic handler runs, and an admission refusal
    aborts the run. Client configuration is per-instance (isolated method
    settings views); the run never touches shared module settings.
    """
    _ensure_project_on_path()
    from src.infra.llm.conversation_context import conversation_scope

    ops_metadata: list[dict[str, Any]] = []
    started = time.monotonic()
    with conversation_scope(harness.session.conversation_id):
        for spec in _STAGE_A_OPS:
            if spec.structured_mode is not None:
                if spec.structured_mode not in STRUCTURED_MODES:
                    raise SmokeHarnessError("unsupported_structured_mode")
                harness.adapter.structured_mode = spec.structured_mode
            await _run_operation(harness, spec, ops_metadata, started)
    return {
        "run": "p4d-stage-a-smoke",
        # Narrowed offline guarantee, NOT an unconditional claim: SDK requests
        # ride a harness-built in-memory httpx.MockTransport only, while the
        # synthetic handler is trusted code outside that guarantee (no I/O,
        # no request retention, OS-isolated runs).
        "transport_mode": "sdk_transport_mock",
        "handler_boundary": "trusted_callback_os_isolated_no_io",
        "route": GO_BASE_URL,
        "model": GO_MODEL,
        "temperature": TEMPERATURE,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "input_ceiling_bytes": MAX_INPUT_BODY_BYTES,
        "transport_attempts_per_call": TOTAL_TRANSPORT_ATTEMPTS,
        "structured_repair_cap": MAX_STRUCTURED_REPAIRS,
        "post_cap": MAX_POST_ATTEMPTS,
        "frozen_hashes": frozen_input_hashes(),
        "ops": ops_metadata,
        "admission": harness.admission.metadata(),
    }


async def _run_operation(
    harness: StageAHarness,
    spec: _OpSpec,
    ops_metadata: list[dict[str, Any]],
    started: float,
) -> None:
    entry: dict[str, Any] = {
        "op": spec.name,
        "provider": spec.provider,
        "outcome": "error",
        "error_kind": None,
        "attempts_admitted": 0,
        "payload_sha256": [],
        "usage_reported": False,
        "input_tokens": None,
        "output_tokens": None,
    }
    ops_metadata.append(entry)
    # All validation happens before the operation may touch the transport.
    if harness.admission.remaining_attempts() < 1:
        entry["outcome"] = "refused_precheck"
        raise SmokeHarnessError("post_cap_reached_precheck")
    if time.monotonic() - started > OVERALL_STOP_SECONDS:
        entry["outcome"] = "refused_precheck"
        raise SmokeHarnessError("overall_stop_clock_exceeded")
    from src.infra.usage import capture_usage

    before = harness.admission.attempts
    try:
        with capture_usage() as captured:
            outcome = await spec.factory(harness)
        entry["outcome"] = (
            outcome if isinstance(outcome, str) and outcome in _OPERATION_OUTCOMES else "ok"
        )
        usage = captured.usage_by_role.get("generation") or {}
        if (
            usage.get("status") == "reported"
            and isinstance(usage.get("input_tokens"), int)
            and isinstance(usage.get("output_tokens"), int)
        ):
            entry["usage_reported"] = True
            entry["input_tokens"] = usage["input_tokens"]
            entry["output_tokens"] = usage["output_tokens"]
    except Exception as exc:
        # Fail fast: record the sanitized failure kind, then stop the whole
        # run — route/account/capability rejection must never be followed by
        # further requests (execution addendum stop condition).
        entry["error_kind"] = type(exc).__name__
        raise
    finally:
        entry["attempts_admitted"] = harness.admission.attempts - before
        entry["payload_sha256"] = list(harness.admission.payload_digests()[before:])
        harness.admission.settle(
            reported_input_tokens=entry["input_tokens"] if entry["usage_reported"] else None,
            reported_output_tokens=(entry["output_tokens"] if entry["usage_reported"] else None),
        )


def main(argv: list[str] | None = None) -> int:
    """Fail closed: live execution is not authorized in this slice."""
    print(LIVE_EXECUTION_REFUSAL, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
