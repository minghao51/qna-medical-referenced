import os

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

API_KEYS: set[str] = set()


def load_api_keys():
    global API_KEYS
    keys_str = os.getenv("API_KEYS", "")
    if keys_str:
        API_KEYS = set(keys_str.split(","))


load_api_keys()


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")

        if not api_key:
            raise HTTPException(status_code=401, detail="Missing X-API-Key header")

        if api_key not in API_KEYS:
            raise HTTPException(status_code=403, detail="Invalid API key")

        return await call_next(request)
