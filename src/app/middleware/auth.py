"""API key authentication middleware."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.app.security import AuthContext, load_api_key_records

logger = logging.getLogger(__name__)

EXEMPT_PATHS = {"/", "/health", "/docs", "/openapi.json"}


class APIKeyConfig:
    """Validated API key configuration cached in memory."""

    _records: list = []
    _record_map: dict[str, object] = {}
    _loaded = False

    @classmethod
    def get_records(cls) -> list:
        if not cls._loaded:
            cls.reload()
        return list(cls._records)

    @classmethod
    def get_record_map(cls) -> dict[str, object]:
        if not cls._loaded:
            cls.reload()
        return dict(cls._record_map)

    @classmethod
    def reload(cls) -> None:
        cls._records = load_api_key_records()
        cls._record_map = {record.key_id: record for record in cls._records}
        cls._loaded = True


def get_api_key_records() -> list:
    return APIKeyConfig.get_records()


def get_api_keys() -> set[str]:
    return {record.key_id for record in APIKeyConfig.get_records()}


def authenticate_api_key(api_key: str | None) -> AuthContext | None:
    if not api_key:
        return None
    for record in APIKeyConfig.get_records():
        if record.matches(api_key):
            return AuthContext(key_id=record.key_id, owner=record.owner, role=record.role)
    return None


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.auth = None

        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        records = APIKeyConfig.get_records()
        if not records:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return self._error_response(request, 401, "Missing X-API-Key header")

        auth_context = authenticate_api_key(api_key.strip())
        if auth_context is None:
            logger.warning("Invalid API key attempt from %s", request.client.host if request.client else "unknown")
            return self._error_response(request, 403, "Invalid API key")

        request.state.auth = auth_context
        return await call_next(request)

    @staticmethod
    def _error_response(request: Request, status_code: int, detail: str) -> JSONResponse:
        payload = {
            "detail": detail,
            "error": {
                "code": "http_error",
                "status_code": status_code,
                "request_id": getattr(request.state, "request_id", None),
            },
        }
        response = JSONResponse(status_code=status_code, content=payload)
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response
