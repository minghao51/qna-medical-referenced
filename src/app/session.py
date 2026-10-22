"""Helpers for server-issued anonymous chat sessions."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets

from fastapi import Request, Response
from pydantic import SecretStr

from src.config import settings

logger = logging.getLogger(__name__)

_SIGNING_SEPARATOR = "."
_MIN_SIGNING_KEY_BYTES = 32
_DEVELOPMENT_SIGNING_KEY = secrets.token_bytes(_MIN_SIGNING_KEY_BYTES)


def _get_signing_key() -> bytes:
    configured_secret = getattr(settings.api, "session_signing_secret", None)
    if configured_secret is None:
        if settings.is_development:
            return _DEVELOPMENT_SIGNING_KEY
        raise RuntimeError("Session signing secret must be configured outside development mode")

    if isinstance(configured_secret, SecretStr):
        secret = configured_secret.get_secret_value().strip()
    elif isinstance(configured_secret, str):
        secret = configured_secret.strip()
    else:
        raise RuntimeError("Configured session signing secret is invalid")

    key = secret.encode("utf-8")
    if len(key) < _MIN_SIGNING_KEY_BYTES:
        raise RuntimeError(
            "Configured session signing secret must contain at least 32 bytes after trimming whitespace"
        )
    return key


def _sign_session_id(session_id: str) -> str:
    key = _get_signing_key()
    sig = hmac.new(key, session_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{session_id}{_SIGNING_SEPARATOR}{sig}"


def _verify_signed_session_id(signed_value: str) -> str | None:
    parts = signed_value.rsplit(_SIGNING_SEPARATOR, 1)
    if len(parts) != 2:
        return None
    session_id, provided_sig = parts
    if len(provided_sig) != 64 or any(ch not in "0123456789abcdef" for ch in provided_sig):
        return None
    expected_sig = hmac.new(
        _get_signing_key(), session_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if hmac.compare_digest(expected_sig, provided_sig):
        return session_id
    logger.warning("Session cookie signature verification failed")
    return None


def get_chat_session_id(request: Request) -> str | None:
    raw = request.cookies.get(settings.api.chat_session_cookie_name)
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    verified = _verify_signed_session_id(raw)
    return verified


def ensure_chat_session(request: Request, response: Response) -> str:
    session_id = get_chat_session_id(request)
    if session_id:
        request.state.chat_session_id = session_id
        return session_id

    session_id = _generate_session_id()
    _set_chat_session_cookie(response, session_id)
    request.state.chat_session_id = session_id
    return session_id


def rotate_chat_session(response: Response) -> str:
    session_id = _generate_session_id()
    _set_chat_session_cookie(response, session_id)
    return session_id


def _generate_session_id() -> str:
    return f"chat_{secrets.token_urlsafe(24)}"


def _set_chat_session_cookie(response: Response, session_id: str) -> None:
    signed = _sign_session_id(session_id)
    response.set_cookie(
        key=settings.api.chat_session_cookie_name,
        value=signed,
        max_age=settings.api.chat_session_cookie_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=not settings.is_development,
    )
