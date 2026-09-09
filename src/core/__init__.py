"""Shared kernel — cross-cutting primitives used by multiple layers.

Depends on nothing outside the standard library (and optionally `config/`).
Anything imported by two or more top-level packages belongs here.

See docs/plans/20260910-structural-refactor-roadmap.md §3.2.
"""

from src.core.source_metadata import (
    build_document_source_metadata,
    canonical_source_label,
)

__all__ = [
    "build_document_source_metadata",
    "canonical_source_label",
]
