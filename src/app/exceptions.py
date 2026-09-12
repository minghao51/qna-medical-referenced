"""Application-level domain exceptions and FastAPI handlers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

# Layer-agnostic domain exceptions live in src/core/exceptions.py;
# alias re-exports keep them importable from here for existing importers.
from src.core.exceptions import AppError as AppError
from src.core.exceptions import StorageError as StorageError
from src.core.exceptions import UpstreamServiceError as UpstreamServiceError

# Layer-agnostic domain exceptions live in src/core/exceptions.py;


class InvalidInputError(AppError):
    def __init__(self, message: str, *, extra: dict[str, Any] | None = None):
        super().__init__(message=message, status_code=400, code="invalid_input", extra=extra)


class ArtifactNotFoundError(AppError):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=404, code="artifact_not_found")


def _error_payload(
    *,
    request: Request,
    message: str,
    code: str,
    status_code: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "detail": message,
        "error": {
            "code": code,
            "status_code": status_code,
            "request_id": getattr(request.state, "request_id", None),
        },
    }
    if extra:
        payload["error"]["extra"] = extra
    return payload


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    response = JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            request=request,
            message=exc.message,
            code=exc.code,
            status_code=exc.status_code,
            extra=exc.extra,
        ),
    )
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    response = JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            request=request,
            message=detail,
            code="http_error",
            status_code=exc.status_code,
        ),
    )
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    response = JSONResponse(
        status_code=500,
        content=_error_payload(
            request=request,
            message="Internal server error",
            code="internal_server_error",
            status_code=500,
        ),
    )
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response
