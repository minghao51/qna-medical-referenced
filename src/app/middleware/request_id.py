import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.app.logging import log_event
from src.infra.telemetry import current_telemetry

logger = logging.getLogger(__name__)
_STANDARD_HTTP_METHODS = frozenset(
    {"CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"}
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        telemetry = current_telemetry()
        if telemetry is None:
            response = await call_next(request)
        else:
            with telemetry.request_id_context(request_id):
                response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        log_event(
            logger,
            logging.INFO,
            "request_completed",
            request_id=request_id,
            method=request.method if request.method in _STANDARD_HTTP_METHODS else "OTHER",
            path=getattr(request.scope.get("route"), "path", "/unmatched"),
            status_code=response.status_code,
            latency_ms=elapsed_ms,
            auth_key_id=getattr(getattr(request.state, "auth", None), "key_id", None),
        )

        return response
