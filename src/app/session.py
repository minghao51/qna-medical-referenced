"""Helpers for server-issued anonymous chat sessions."""

from __future__ import annotations

import secrets

from fastapi import Request, Response

from src.config import settings


def get_chat_session_id(request: Request) -> str | None:
    session_id = request.cookies.get(settings.api.chat_session_cookie_name)
    if not session_id:
        return None
    return session_id.strip() or None


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
    response.set_cookie(
        key=settings.api.chat_session_cookie_name,
        value=session_id,
        max_age=settings.api.chat_session_cookie_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=not settings.is_development,
    )
