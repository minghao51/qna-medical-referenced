"""Runtime configuration API endpoints.

Exposes current runtime configuration for the frontend to display,
including retrieval strategy, feature toggles, chunking settings,
and LLM parameters. Read-only — no mutation from the UI.

The view itself is assembled by the usecase facade
``src.usecases.runtime_config`` (roadmap P3.3); this route only handles
HTTP concerns.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from src.usecases.runtime_config import get_runtime_config_view

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_authenticated_request(request: Request) -> None:
    if getattr(request.state, "auth", None) is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")


@router.get(
    "/config",
    summary="Get current runtime configuration",
    description="Read-only snapshot of the active runtime configuration",
)
def get_config(request: Request) -> dict:
    _require_authenticated_request(request)
    return get_runtime_config_view()
