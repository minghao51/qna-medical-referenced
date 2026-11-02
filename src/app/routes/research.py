"""Authenticated, read-only research catalog endpoints.

These handlers are deliberately separate from browser `/research/...` routes and
never accept a filesystem path. Every read is a bounded projection of a fixed,
allowlisted source.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from src.app.schemas.research import (
    CatalogCasesResponse,
    CatalogEntry,
    CatalogListResponse,
)
from src.evals.research_catalog import (
    CatalogCasesUnavailableError,
    CatalogNotFoundError,
    CatalogRevisionChangedError,
    CatalogUnavailableError,
    get_catalog_cases,
    get_catalog_entry,
    list_catalog,
)

router = APIRouter()


def _require_authenticated_request(request: Request) -> None:
    if getattr(request.state, "auth", None) is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")


@router.get(
    "/research-data/datasets",
    response_model=CatalogListResponse,
    summary="List research dataset catalog entries",
    description="Bounded summaries of the fixed catalog allowlist and exact current-file overlap.",
)
def list_research_datasets(request: Request) -> CatalogListResponse:
    _require_authenticated_request(request)
    return CatalogListResponse.model_validate(list_catalog())


@router.get(
    "/research-data/datasets/{dataset_id}",
    response_model=CatalogEntry,
    summary="Get one research dataset catalog entry",
    description="Current metadata for one allowlisted logical catalog ID; never a filesystem path.",
)
def get_research_dataset(dataset_id: str, request: Request) -> CatalogEntry:
    _require_authenticated_request(request)
    try:
        return CatalogEntry.model_validate(get_catalog_entry(dataset_id))
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail="catalog_not_found") from exc


@router.get(
    "/research-data/datasets/{dataset_id}/cases",
    response_model=CatalogCasesResponse,
    summary="Get revision-bound case projections",
    description="Bounded fixture case rows; the revision must match the current source bytes.",
)
def get_research_dataset_cases(
    dataset_id: str,
    request: Request,
    revision: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> CatalogCasesResponse:
    _require_authenticated_request(request)
    try:
        return CatalogCasesResponse.model_validate(
            get_catalog_cases(dataset_id, revision=revision, limit=limit, offset=offset)
        )
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail="catalog_not_found") from exc
    except CatalogUnavailableError as exc:
        raise HTTPException(status_code=404, detail="catalog_unavailable") from exc
    except CatalogCasesUnavailableError as exc:
        raise HTTPException(status_code=409, detail="catalog_cases_unavailable") from exc
    except CatalogRevisionChangedError as exc:
        raise HTTPException(status_code=409, detail="catalog_revision_changed") from exc
