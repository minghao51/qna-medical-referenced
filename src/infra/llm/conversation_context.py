"""Request-scoped conversation identity for provider identity headers.

The chat use cases set the resolved conversation id around the generation call
region; the provider adapters read it to derive per-conversation identity
headers (e.g. OpenCode Go's stable ``x-opencode-session``). Only the opaque
hash derived by :func:`opaque_session_id` may appear on the wire; the raw
conversation id never leaves the process through this module.
"""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_conversation_id: ContextVar[str | None] = ContextVar("qna_conversation_id", default=None)


@contextmanager
def conversation_scope(conversation_id: str | None) -> Iterator[None]:
    """Bind the current conversation id for the wrapped region."""
    token = _conversation_id.set(conversation_id)
    try:
        yield
    finally:
        _conversation_id.reset(token)


def get_conversation_id() -> str | None:
    """Return the conversation id bound by :func:`conversation_scope`, if any."""
    return _conversation_id.get()


def opaque_session_id(conversation_id: str) -> str:
    """Return a stable, opaque per-conversation session id for provider headers."""
    return "qna-" + hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()[:16]
