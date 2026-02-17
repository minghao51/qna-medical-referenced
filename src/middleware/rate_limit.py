import asyncio
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.middleware.auth import API_KEYS


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[datetime]] = defaultdict(list)
        self.lock = asyncio.Lock()

    async def check_rate_limit(self, key: str) -> bool:
        async with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=1)

            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if req_time > cutoff
            ]

            if len(self.requests[key]) >= self.requests_per_minute:
                return False

            self.requests[key].append(now)
            return True


rate_limiter = RateLimiter(requests_per_minute=60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        if API_KEYS:
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
