"""Small, in-memory collection of provider-reported token usage for one run."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from typing import Any

_ROLES = frozenset(
    {
        "generation",
        "judge",
        "judge_light",
        "judge_heavy",
        "embedder",
        "expansion",
        "enrichment",
    }
)
_FIELDS = ("input_tokens", "output_tokens", "total_tokens")
_MISSING = object()
_REASON_CODES = frozenset(
    {
        "provider_sdk_usage_unavailable",
        "provider_sdk_usage_partial",
        "provider_sdk_usage_invalid",
        "provider_call_failed",
        "provider_sdk_retry_usage_unavailable",
    }
)

# These are the public usage field names returned by the supported SDK response
# objects. Deliberately do not serialize or inspect arbitrary response payloads.
_USAGE_CONTAINERS = {
    "openai": ("usage",),
    "litellm": ("usage",),
    "gemini": ("usage_metadata",),
    "pydantic-ai": ("usage",),
}
_USAGE_FIELDS: dict[str, dict[str, tuple[str, ...]]] = {
    "openai": {
        "input_tokens": ("prompt_tokens", "input_tokens"),
        "output_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
    },
    "litellm": {
        "input_tokens": ("prompt_tokens", "input_tokens"),
        "output_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
    },
    "gemini": {
        "input_tokens": ("prompt_token_count", "input_tokens"),
        "output_tokens": ("candidates_token_count", "output_tokens"),
        "total_tokens": ("total_token_count", "total_tokens"),
    },
    "pydantic-ai": {
        "input_tokens": ("prompt_tokens", "input_tokens"),
        "output_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
    },
}

_current_capture: ContextVar[UsageAccumulator | None] = ContextVar(
    "provider_usage_capture", default=None
)
_current_role: ContextVar[str] = ContextVar("provider_usage_role", default="generation")


def _public_value(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, _MISSING)
    try:
        return getattr(value, name, _MISSING)
    except Exception:
        return _MISSING


def _extract_usage(response: Any, provider: str) -> tuple[dict[str, int], bool]:
    containers = _USAGE_CONTAINERS[provider]
    usage = _MISSING
    for name in containers:
        usage = _public_value(response, name)
        if usage is not _MISSING and usage is not None:
            break
    if usage is _MISSING or usage is None:
        return {}, False

    counts: dict[str, int] = {}
    invalid = False
    for normalized, candidates in _USAGE_FIELDS[provider].items():
        raw = _MISSING
        for candidate in candidates:
            raw = _public_value(usage, candidate)
            if raw is not _MISSING:
                break
        if raw is _MISSING or raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            invalid = True
            continue
        counts[normalized] = raw
    return counts, invalid


class UsageAccumulator:
    """Thread-safe per-run totals; no request, prompt, or response data is retained."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._totals: dict[str, dict[str, Any]] = {}
        self._unknowns: set[str] = set()

    def _record_call(self, role: str, counts: Mapping[str, int], reasons: set[str]) -> None:
        with self._lock:
            current = self._totals.setdefault(
                role,
                {
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "status": "reported",
                    "source": "provider_sdk",
                },
            )
            for field, value in counts.items():
                previous = current[field]
                current[field] = value if previous is None else previous + value
            if reasons:
                current["status"] = "incomplete"
                self._unknowns.update(reasons)

    @property
    def usage_by_role(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {role: dict(values) for role, values in self._totals.items()}

    @property
    def unknowns(self) -> list[str]:
        with self._lock:
            return sorted(self._unknowns)

    def snapshot(self) -> dict[str, Any]:
        return {"usage_by_role": self.usage_by_role, "unknowns": self.unknowns}


class _UsageCall:
    """One SDK attempt; repeated stream chunks replace, rather than add, usage."""

    def __init__(self, accumulator: UsageAccumulator, role: str, provider: str) -> None:
        self._accumulator = accumulator
        self._role = role
        self._provider = provider
        self._counts: dict[str, int] = {}
        self._saw_usage = False
        self._invalid = False
        self._extra_reasons: set[str] = set()
        self._finished = False

    def record_response(self, response: Any) -> None:
        try:
            counts, invalid = _extract_usage(response, self._provider)
            if counts:
                self._saw_usage = True
                self._counts.update(counts)
            self._invalid = self._invalid or invalid
        except Exception:
            self._invalid = True

    def mark_incomplete(self, reason: str) -> None:
        try:
            if reason in _REASON_CODES:
                self._extra_reasons.add(reason)
        except Exception:
            pass

    def finish(self, *, failed: bool = False) -> None:
        if self._finished:
            return
        self._finished = True
        reasons = set(self._extra_reasons)
        if not self._saw_usage:
            reasons.add("provider_sdk_usage_unavailable")
        elif any(field not in self._counts for field in _FIELDS):
            reasons.add("provider_sdk_usage_partial")
        if self._invalid:
            reasons.add("provider_sdk_usage_invalid")
        if failed:
            reasons.add("provider_call_failed")
        try:
            self._accumulator._record_call(self._role, self._counts, reasons)
        except Exception:
            # Usage bookkeeping must never change provider-call behavior.
            pass


def begin_usage_call(*, role: str | None = None, provider: str = "openai") -> _UsageCall | None:
    """Start an attempt tracker; no-op unless inside :func:`capture_usage`."""
    accumulator = _current_capture.get()
    if accumulator is None or provider not in _USAGE_CONTAINERS:
        return None
    selected_role = role or _current_role.get()
    if selected_role not in _ROLES:
        return None
    try:
        return _UsageCall(accumulator, selected_role, provider)
    except Exception:
        return None


def finish_usage_call(call: _UsageCall | None, *, failed: bool = False) -> None:
    """Finish an attempt tracker without allowing collector errors to escape."""
    if call is not None:
        try:
            call.finish(failed=failed)
        except Exception:
            pass


@contextmanager
def usage_call(*, role: str | None = None, provider: str = "openai") -> Iterator[_UsageCall | None]:
    """Track one non-streaming SDK attempt, including failures and cancellation."""
    call = begin_usage_call(role=role, provider=provider)
    try:
        yield call
    except BaseException:
        finish_usage_call(call, failed=True)
        raise
    else:
        finish_usage_call(call)


@contextmanager
def capture_usage() -> Iterator[UsageAccumulator]:
    """Collect allowlisted provider token counts in a scoped, thread-safe accumulator."""
    accumulator = UsageAccumulator()
    token = _current_capture.set(accumulator)
    try:
        yield accumulator
    finally:
        _current_capture.reset(token)


@contextmanager
def usage_role(role: str) -> Iterator[None]:
    """Temporarily attribute provider requests to a fixed accounting role."""
    if role not in _ROLES:
        raise ValueError("Unsupported usage role")
    token = _current_role.set(role)
    try:
        yield
    finally:
        _current_role.reset(token)
