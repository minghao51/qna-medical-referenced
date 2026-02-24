import os

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


class APIKeyConfig:
    _keys: set[str] | None = None

    @classmethod
    def get_keys(cls) -> set[str]:
        if cls._keys is None:
            keys_str = os.getenv("API_KEYS", "")
            cls._keys = set(keys_str.split(",")) if keys_str else set()
        return cls._keys

    @classmethod
    def reload(cls):
        cls._keys = None


def get_api_keys() -> set[str]:
    return APIKeyConfig.get_keys()


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        api_keys = get_api_keys()
        if not api_keys:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")

        if not api_key:
            raise HTTPException(status_code=401, detail="Missing X-API-Key header")

        if api_key not in api_keys:
            raise HTTPException(status_code=403, detail="Invalid API key")

        return await call_next(request)
