"""Layer-agnostic domain exceptions.

These carry HTTP-ish semantics (status codes) but depend on no web framework,
so any layer (infra, usecases, rag, ...) can raise them. The FastAPI-specific
handlers live in src/app/exceptions.py, which re-exports these for
backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AppError(Exception):
    """Base application exception with HTTP semantics."""

    message: str
    status_code: int = 500
    code: str = "application_error"
    extra: dict[str, Any] | None = None


class UpstreamServiceError(AppError):
    def __init__(self, message: str = "Upstream service failure"):
        super().__init__(message=message, status_code=502, code="upstream_service_error")


class StorageError(AppError):
    def __init__(self, message: str = "Storage operation failed"):
        super().__init__(message=message, status_code=500, code="storage_error")
