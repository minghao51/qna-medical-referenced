"""Rate limiting middleware using a sliding-window backend."""

from __future__ import annotations

import asyncio
import logging
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.app.logging import log_event
from src.config import RATE_LIMIT_DB, settings

from .auth import EXEMPT_PATHS

logger = logging.getLogger(__name__)

ANONYMOUS_CHAT_PATHS = {"/chat"}


@dataclass
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class RateLimitBackend:
    def check(self, key: str, limit: int, now: int | None = None) -> RateLimitDecision:
        raise NotImplementedError


@contextmanager
def get_connection():
    conn = sqlite3.connect(RATE_LIMIT_DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class SQLiteRateLimitBackend(RateLimitBackend):
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._init_db()

    def _init_db(self) -> None:
        with get_connection() as conn:
            # Migrate old table if exists (breaking change from counters to events)
            old_table_exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='rate_limit_counters'"
            ).fetchone()

            if old_table_exists:
                logger.info("Migrating rate_limit_counters to rate_limit_events schema")
                conn.execute("DROP TABLE IF EXISTS rate_limit_counters")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_limit_events (
                    key TEXT NOT NULL,
                    occurred_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rate_limit_events_key_time
                ON rate_limit_events (key, occurred_at)
                """
            )
            conn.commit()

    def _cleanup(self, conn: sqlite3.Connection, now: int) -> None:
        cutoff = now - (self.window_seconds * 2)
        conn.execute("DELETE FROM rate_limit_events WHERE occurred_at < ?", (cutoff,))

    def check(self, key: str, limit: int, now: int | None = None) -> RateLimitDecision:
        if limit <= 0:
            return RateLimitDecision(True, limit, limit, 0)
        current = now or int(time.time())
        window_start = current - self.window_seconds + 1
        with get_connection() as conn:
            self._cleanup(conn, current)
            recent_rows = conn.execute(
                """
                SELECT occurred_at
                FROM rate_limit_events
                WHERE key = ? AND occurred_at >= ?
                ORDER BY occurred_at ASC
                """,
                (key, window_start),
            ).fetchall()
            existing_count = len(recent_rows)
            if existing_count < limit:
                conn.execute(
                    "INSERT INTO rate_limit_events (key, occurred_at) VALUES (?, ?)",
                    (key, current),
                )
                count = existing_count + 1
                retry_after = 0
                allowed = True
            else:
                count = existing_count
                oldest = int(recent_rows[0]["occurred_at"]) if recent_rows else current
                retry_after = max(1, (oldest + self.window_seconds) - current)
                allowed = False
            conn.commit()

        return RateLimitDecision(
            allowed=allowed,
            limit=limit,
            remaining=max(0, limit - count) if allowed else 0,
            retry_after=retry_after,
        )


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60, backend: RateLimitBackend | None = None):
        self.requests_per_minute = requests_per_minute
        self.backend = backend or SQLiteRateLimitBackend(window_seconds=60)

    def check_rate_limit(self, key: str) -> RateLimitDecision:
        return self.backend.check(key=key, limit=self.requests_per_minute)


rate_limiter = RateLimiter(requests_per_minute=settings.api.rate_limit_per_minute)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        auth = getattr(request.state, "auth", None)
        rate_key, limit = self._build_rate_limit_key(request, auth)
        if limit <= 0:
            response = await call_next(request)
            self._attach_browser_cookie(request, response, auth)
            return response
        decision = await asyncio.to_thread(rate_limiter.backend.check, rate_key, limit)
        if not decision.allowed:
            log_event(
                logger,
                logging.WARNING,
                "rate_limit_exceeded",
                request_id=getattr(request.state, "request_id", None),
                path=request.url.path,
                rate_key=rate_key,
                retry_after=decision.retry_after,
            )
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
            )
            response.headers["Retry-After"] = str(decision.retry_after)
            response.headers["X-RateLimit-Limit"] = str(decision.limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(decision.retry_after)
            self._attach_browser_cookie(request, response, auth)
            return response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = "0"
        self._attach_browser_cookie(request, response, auth)
        return response

    def _build_rate_limit_key(self, request: Request, auth) -> tuple[str, int]:
        if auth:
            if self._is_bypass_auth(auth):
                return f"auth-bypass:{auth.key_id}", 0
            return f"auth:{auth.key_id}", rate_limiter.requests_per_minute

        client_ip = self._get_client_ip(request)
        limit = rate_limiter.requests_per_minute

        if request.url.path in ANONYMOUS_CHAT_PATHS:
            browser_id = self._get_or_create_browser_id(request)
            limit = settings.api.anonymous_chat_rate_limit_per_minute
            return f"anon-chat:{client_ip}:{browser_id}", limit

        return f"ip:{client_ip}", limit

    @staticmethod
    def _is_bypass_auth(auth) -> bool:
        if not auth:
            return False
        bypass_key_ids = {v.strip() for v in settings.api.rate_limit_bypass_key_ids.split(",") if v.strip()}
        bypass_roles = {v.strip() for v in settings.api.rate_limit_bypass_roles.split(",") if v.strip()}
        return (
            auth.key_id in bypass_key_ids
            or bool(auth.role and auth.role in bypass_roles)
        )

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        if settings.api.trust_proxy_headers:
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                first_hop = forwarded_for.split(",")[0].strip()
                if first_hop:
                    return first_hop
            real_ip = request.headers.get("X-Real-IP", "").strip()
            if real_ip:
                return real_ip

        return request.client.host if request.client else "unknown"

    @staticmethod
    def _get_or_create_browser_id(request: Request) -> str:
        cookie_name = settings.api.anonymous_browser_cookie_name
        browser_id = request.cookies.get(cookie_name)
        if browser_id:
            return browser_id

        browser_id = secrets.token_urlsafe(24)
        request.state.rate_limit_browser_id = browser_id
        return browser_id

    @staticmethod
    def _attach_browser_cookie(request: Request, response: Response, auth) -> None:
        if auth or request.url.path not in ANONYMOUS_CHAT_PATHS:
            return

        browser_id = getattr(request.state, "rate_limit_browser_id", None)
        if not browser_id:
            return

        response.set_cookie(
            key=settings.api.anonymous_browser_cookie_name,
            value=browser_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
            secure=not settings.is_development,
        )
