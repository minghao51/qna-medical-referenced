import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.middleware.auth import get_api_keys

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
RATE_LIMIT_DB = DATA_DIR / "rate_limits.db"


def _init_db():
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
    conn = sqlite3.connect(RATE_LIMIT_DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.lock = asyncio.Lock()
        _init_db()

    async def check_rate_limit(self, key: str) -> bool:
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
                        request_times = [
                            datetime.fromisoformat(ts) for ts in timestamps if ts
                        ]
                    except (ValueError, AttributeError):
                        request_times = []

                request_times = [t for t in request_times if t > cutoff]

                if len(request_times) >= self.requests_per_minute:
                    return False

                request_times.append(now)

                timestamps_str = ",".join(t.isoformat() for t in request_times)
                conn.execute(
                    "INSERT OR REPLACE INTO rate_limits (key, requests) VALUES (?, ?)",
                    (key, timestamps_str)
                )
                conn.commit()

                return True


rate_limiter = RateLimiter(requests_per_minute=60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        api_keys = get_api_keys()
        if api_keys:
            api_key = request.headers.get("X-API-Key")
            rate_key = api_key if api_key else client_ip
        else:
            rate_key = client_ip

        if not await rate_limiter.check_rate_limit(rate_key):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )

        return await call_next(request)
