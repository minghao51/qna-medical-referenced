"""Rate limiting middleware using a fixed-window backend."""

from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.app.logging import log_event
from src.config import RATE_LIMIT_DB, settings

from .auth import EXEMPT_PATHS

logger = logging.getLogger(__name__)


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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_limit_counters (
                    key TEXT PRIMARY KEY,
                    window_start INTEGER NOT NULL,
                    count INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def _cleanup(self, conn: sqlite3.Connection, now: int) -> None:
        cutoff = now - (self.window_seconds * 2)
        conn.execute("DELETE FROM rate_limit_counters WHERE updated_at < ?", (cutoff,))

    def check(self, key: str, limit: int, now: int | None = None) -> RateLimitDecision:
        if limit <= 0:
            return RateLimitDecision(True, limit, limit, 0)
        current = now or int(time.time())
        window_start = current - (current % self.window_seconds)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT window_start, count FROM rate_limit_counters WHERE key = ?",
                (key,),
            ).fetchone()
            if not row or int(row["window_start"]) != window_start:
                count = 1
                conn.execute(
                    """
                    INSERT OR REPLACE INTO rate_limit_counters (key, window_start, count, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, window_start, count, current),
                )
            else:
                count = int(row["count"]) + 1
                conn.execute(
                    """
                    UPDATE rate_limit_counters
                    SET count = ?, updated_at = ?
                    WHERE key = ? AND window_start = ?
                    """,
                    (count, current, key, window_start),
                )
            self._cleanup(conn, current)
            conn.commit()

        allowed = count <= limit
        remaining = max(0, limit - count)
        retry_after = max(0, (window_start + self.window_seconds) - current)
        return RateLimitDecision(
            allowed=allowed,
            limit=limit,
            remaining=remaining if allowed else 0,
            retry_after=retry_after if not allowed else 0,
        )


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60, backend: RateLimitBackend | None = None):
        self.requests_per_minute = requests_per_minute
        self.backend = backend or SQLiteRateLimitBackend(window_seconds=60)

    def check_rate_limit(self, key: str) -> RateLimitDecision:
        return self.backend.check(key=key, limit=self.requests_per_minute)


rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_per_minute)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if rate_limiter.requests_per_minute <= 0 or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        auth = getattr(request.state, "auth", None)
        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"auth:{auth.key_id}" if auth else f"ip:{client_ip}"
        decision = rate_limiter.check_rate_limit(rate_key)
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
            return response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = "0"
        return response
