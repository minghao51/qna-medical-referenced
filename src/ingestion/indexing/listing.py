"""API-shaped document listing (pagination + by-id lookup).

Mixin for ChromaVectorStore: serves the /documents routes.
"""

from __future__ import annotations

import logging
from typing import Any, cast

logger = logging.getLogger(__name__)


class DocumentListingMixin:
    """Paginated document listing and single-document lookup."""

    @staticmethod
    def _build_source_type_filter(source_type: str | None) -> dict[str, Any] | None:
        normalized = str(source_type or "").strip()
        if not normalized:
            return None
        return {"source_type": normalized}

    def list_documents_paginated(
        self,
        *,
        limit: int,
        offset: int,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        where_filter = self._build_source_type_filter(source_type)
        page_result = cast(
            dict[str, Any],
            self._collection.get(
                where=where_filter,
                limit=limit,
                offset=offset,
                include=["documents", "metadatas"],
            ),
        )

        ids = list(page_result.get("ids") or [])
        contents = list(page_result.get("documents") or [])
        metadatas = list(page_result.get("metadatas") or [])

        items: list[dict[str, Any]] = []
        for index, doc_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) else {}
            content = contents[index] if index < len(contents) else ""
            items.append(
                {
                    "id": doc_id,
                    "source": metadata.get("source", ""),
                    "page": metadata.get("page"),
                    "source_type": metadata.get("source_type", ""),
                    "source_class": metadata.get("source_class", ""),
                    "content_type": metadata.get("content_type", ""),
                    "content_preview": content[:200] if content else "",
                    "content_length": len(content),
                }
            )

        # Totals and per-type counts come from the in-memory mirrors instead
        # of a second full-collection fetch. _build_source_type_filter only
        # produces equality filters, so mirror matching is equivalent.
        self._rebuild_index_if_needed()
        if where_filter is not None:
            matching_metadatas = [
                meta
                for meta in self._doc_metadatas
                if meta.get("source_type") == where_filter["source_type"]
            ]
        else:
            matching_metadatas = list(self._doc_metadatas)

        source_type_counts: dict[str, int] = {}
        for metadata in matching_metadatas:
            key = str((metadata or {}).get("source_type") or "unknown")
            source_type_counts[key] = source_type_counts.get(key, 0) + 1

        total = len(matching_metadatas)
        return {
            "total": total,
            "items": items,
            "source_type_counts": source_type_counts,
            "index_metadata": self._index_metadata,
        }

    def get_document_by_id(self, doc_id: str) -> dict[str, Any] | None:
        result = cast(
            dict[str, Any],
            self._collection.get(ids=[doc_id], include=["documents", "metadatas"]),
        )
        ids = list(result.get("ids") or [])
        if not ids:
            return None

        content = (result.get("documents") or [""])[0]
        metadata = (result.get("metadatas") or [{}])[0]
        return {
            "id": ids[0],
            "content": content,
            "metadata": metadata,
            "content_length": len(content),
        }
