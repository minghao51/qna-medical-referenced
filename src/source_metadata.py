"""Shared source metadata helpers for ingestion, retrieval, and presentation."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def sanitize_external_url(url: str | None) -> str | None:
    """Return a normalized external URL when it is safe to expose."""
    if not url:
        return None
    candidate = str(url).strip()
    if not candidate:
        return None
    try:
        parsed = urlparse(candidate)
    except Exception as e:
        logger.debug("Failed to parse URL %r: %s", candidate, e)
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return parsed.geturl()


def infer_domain(url: str | None) -> str | None:
    """Extract the hostname from a safe external URL."""
    safe_url = sanitize_external_url(url)
    if not safe_url:
        return None
    try:
        return urlparse(safe_url).netloc.lower() or None
    except Exception as e:
        logger.debug("Failed to infer domain from %r: %s", safe_url, e)
        return None


def infer_domain_type(domain_or_url: str | None) -> str:
    """Classify a domain using the same coarse buckets used in the UI."""
    if not domain_or_url:
        return "unknown"
    candidate = str(domain_or_url).strip().lower()
    if not candidate:
        return "unknown"
    if "://" in candidate:
        candidate = infer_domain(candidate) or candidate
    if candidate.startswith("www."):
        candidate = candidate[4:]
    if candidate.endswith(".gov") or ".gov." in candidate:
        return "government"
    if candidate.endswith(".edu") or ".edu." in candidate:
        return "education"
    if candidate.endswith(".org"):
        return "organization"
    if candidate.endswith(".com"):
        return "commercial"
    return "unknown"


def normalize_source_type(source: str | None, explicit_type: str | None = None) -> str:
    """Normalize source types into chat-friendly buckets."""
    if explicit_type:
        normalized = str(explicit_type).strip().lower()
        if normalized in {"pdf", "html", "reference_csv", "csv", "other"}:
            return "reference_csv" if normalized == "csv" else normalized
    lowered = str(source or "").strip().lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".csv"):
        return "reference_csv"
    if lowered.endswith((".md", ".html")):
        return "html"
    return "other"


_INTERNATIONAL_DOMAINS = {
    "nice.org.uk",
    "cdc.gov",
    "who.int",
    "nih.gov",
    "mayoclinic.org",
    "webmd.com",
}


def normalize_source_class(
    source: str | None,
    *,
    source_type: str | None = None,
    explicit_class: str | None = None,
    page_type: str | None = None,
    logical_name: str | None = None,
    domain: str | None = None,
) -> str:
    """Normalize retrieval/source class labels."""
    if explicit_class:
        normalized = str(explicit_class).strip().lower()
        if normalized:
            return normalized
    normalized_type = normalize_source_type(source, source_type)
    if normalized_type == "pdf":
        return "guideline_pdf"
    if normalized_type == "reference_csv":
        return "reference_csv"
    if (page_type or "").strip().lower() in {"index/listing", "navigation-heavy"}:
        return "index_page"
    if normalized_type == "html":
        logical_lower = str(logical_name or "").lower()
        domain_lower = str(domain or "").lower()
        if "drug_guidance" in logical_lower or "drug-guidance" in logical_lower:
            return "ace_drug_guidance"
        if "guideline" in logical_lower or domain_lower == "hpp.moh.gov.sg":
            return "hpp_guideline"
        if domain_lower == "www.healthhub.sg" or "healthhub" in domain_lower:
            return "healthhub_html"
        if any(international in domain_lower for international in _INTERNATIONAL_DOMAINS):
            return "international_html"
        return "guideline_html"
    return "unknown"


def fallback_source_label(source: str | None) -> str:
    """Build a readable label from a raw source identifier."""
    text = str(source or "").strip()
    if not text or text.lower() == "unknown":
        return "Unknown source"
    stem = Path(text).stem or Path(text).name or text
    cleaned = re.sub(r"[_\-]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "Unknown source"


def canonical_source_label(source: str | None, logical_name: str | None = None) -> str:
    """Return the preferred stable human-readable label for a source."""
    logical = str(logical_name or "").strip()
    if logical:
        return logical
    return fallback_source_label(source)


def build_document_source_metadata(
    base_metadata: dict[str, Any] | None,
    *,
    source: str,
    source_type: str,
    manifest_record: dict[str, Any] | None = None,
    explicit_class: str | None = None,
    page_type: str | None = None,
) -> dict[str, Any]:
    """Build the standard document-level source metadata shared by the loaders.

    Applies manifest overrides (``logical_name`` / ``source_url``) on top of
    ``base_metadata``, then derives ``source_type``, ``domain``,
    ``source_class``, ``canonical_label`` and ``domain_type`` the same way for
    every ingestion source (PDF, converted HTML, ...).
    """
    metadata = dict(base_metadata or {})
    if manifest_record:
        metadata["logical_name"] = manifest_record.get("logical_name")
        metadata["source_url"] = manifest_record.get("url")
    metadata["source_type"] = source_type
    metadata["domain"] = infer_domain(metadata.get("source_url"))
    metadata["source_class"] = normalize_source_class(
        source,
        source_type=source_type,
        explicit_class=explicit_class
        if explicit_class is not None
        else metadata.get("source_class"),
        page_type=page_type if page_type is not None else metadata.get("page_type"),
        logical_name=metadata.get("logical_name"),
        domain=metadata.get("domain"),
    )
    metadata["canonical_label"] = canonical_source_label(source, metadata.get("logical_name"))
    metadata["domain_type"] = infer_domain_type(metadata.get("domain"))
    return metadata


def display_source_label(
    source: str | None,
    *,
    logical_name: str | None = None,
    canonical_label: str | None = None,
    page: int | None = None,
) -> str:
    """Return the display label, optionally appending page details."""
    base = str(canonical_label or "").strip() or canonical_source_label(source, logical_name)
    return f"{base} page {page}" if page else base
