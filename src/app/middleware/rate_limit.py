"""Rate limiting middleware using sliding window algorithm.

This module provides rate limiting based on client IP address or API key.
Uses SQLite for persistence and a sliding window algorithm to track
request timestamps within the last minute.

Rate limiting algorithm:
    - Sliding window with 1-minute window size
    - Tracks timestamps of all requests in the window
    - Allows up to N requests per minute (configurable)
    - Returns HTTP 429 when limit exceeded

Storage:
    - SQLite database at path specified by RATE_LIMIT_DB
    - Table: rate_limits (key, requests)
    - Requests stored as comma-separated ISO timestamps

Exempt paths:
    - / - Root path
    - /health - Health check endpoint
    - /docs - API documentation (Swagger UI)
    - /openapi.json - OpenAPI schema

Example:
    Configure rate limit in .env:
        RATE_LIMIT_PER_MINUTE=60

    Client request exceeding limit:
        HTTP/1.1 429 Too Many Requests
        {"detail": "Rate limit exceeded. Please try again later."}
"""

import asyncio
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.app.middleware.auth import get_api_keys
from src.config import RATE_LIMIT_DB, settings


def _init_db():
    """Initialize the rate limiting SQLite database.

    Creates the rate_limits table if it doesn't exist.
    Called once on module import.
    """
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                key TEXT PRIMARY KEY,
                requests TEXT NOT NULL
            )
        """)
        conn.commit()


@contextmanager
def get_connection():
    """Get a SQLite database connection.

    Yields a connection with row_factory set to sqlite3.Row for
    dictionary-like access to rows.

    Yields:
        sqlite3.Connection: Database connection

    Example:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM rate_limits").fetchone()
    """
    conn = sqlite3.connect(RATE_LIMIT_DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class RateLimiter:
    """Rate limiter using sliding window algorithm.

    Tracks request timestamps per client (IP or API key) and enforces
    a maximum number of requests per minute.

    Attributes:
        requests_per_minute: Maximum allowed requests in 1-minute window
        lock: Async lock for thread-safe database operations

    Example:
        Check if request is allowed:
            limiter = RateLimiter(requests_per_minute=60)
            allowed = await limiter.check_rate_limit("client_ip")
            if not allowed:
                return "Rate limit exceeded"
    """

    def __init__(self, requests_per_minute: int = 60):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
        """
        self.requests_per_minute = requests_per_minute
        self.lock = asyncio.Lock()
        _init_db()

    async def check_rate_limit(self, key: str) -> bool:
        """Check if request is within rate limit.

        Retrieves previous request timestamps for the key, removes
        timestamps older than 1 minute, and checks if the count is
        within the allowed limit. Adds current timestamp if allowed.

        Args:
            key: Unique identifier (client IP or API key)

        Returns:
            True if request is allowed, False if limit exceeded
        """
        if self.requests_per_minute <= 0:
            return True

        async with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=1)

            with get_connection() as conn:
                row = conn.execute(
                    "SELECT requests FROM rate_limits WHERE key = ?", (key,)
                ).fetchone()

                request_times = []
                if row:
                    try:
                        timestamps = row["requests"].split(",")
                        request_times = [datetime.fromisoformat(ts) for ts in timestamps if ts]
                    except (ValueError, AttributeError):
                        request_times = []

                # Filter to only requests within the last minute
                request_times = [t for t in request_times if t > cutoff]

                # Check if limit exceeded
                if len(request_times) >= self.requests_per_minute:
                    return False

                # Add current request timestamp
                request_times.append(now)

                # Save updated timestamps
                timestamps_str = ",".join(t.isoformat() for t in request_times)
                conn.execute(
                    "INSERT OR REPLACE INTO rate_limits (key, requests) VALUES (?, ?)",
                    (key, timestamps_str),
                )
                conn.commit()

                return True


# Global rate limiter instance configured from settings
rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_per_minute)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting.

    Applies rate limiting to all requests except exempt paths.
    Tracks requests by client IP, or by API key if authentication
    is enabled. Returns HTTP 429 when limit exceeded.

    Exempt paths:
        - / - Root
        - /health - Health check
        - /docs - Swagger UI documentation
        - /openapi.json - OpenAPI schema

    Example:
        Add to FastAPI app:
            from src.app.middleware.rate_limit import RateLimitMiddleware
            app.add_middleware(RateLimitMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce rate limit.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler in chain

        Returns:
            Response from next handler, or 429 error if rate limited
        """
        if rate_limiter.requests_per_minute <= 0:
            return await call_next(request)

        # Skip rate limiting for public endpoints
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Determine rate limit key (API key if auth enabled, otherwise IP)
        client_ip = request.client.host if request.client else "unknown"

        api_keys = get_api_keys()
        if api_keys:
            api_key = request.headers.get("X-API-Key")
            rate_key = api_key if api_key else client_ip
        else:
            rate_key = client_ip

        # Check rate limit
        if not await rate_limiter.check_rate_limit(rate_key):
            return JSONResponse(
                status_code=429, content={"detail": "Rate limit exceeded. Please try again later."}
            )

        return await call_next(request)
