"""Formatting helpers for retrieved context and sources."""

from src.rag.trace_models import ChatSource
from src.source_metadata import (
    canonical_source_label,
    display_source_label,
    infer_domain,
    infer_domain_type,
    normalize_source_class,
    normalize_source_type,
    sanitize_external_url,
)


def build_source_payload(result: dict) -> dict:
    """Build normalized source metadata from a retrieved result."""
    metadata = result.get("metadata", {})
    source = result.get("source", "unknown")
    page = result.get("page")
    logical_name = metadata.get("logical_name")
    canonical_label = (metadata.get("canonical_label") or "").strip() or canonical_source_label(
        source, logical_name
    )
    display_label = (metadata.get("display_label") or "").strip() or display_source_label(
        source,
        logical_name=logical_name,
        canonical_label=canonical_label,
        page=page,
    )
    source_url = sanitize_external_url(
        metadata.get("source_url") or result.get("source_url") or result.get("url")
    )
    domain = metadata.get("domain") or infer_domain(source_url)
    domain_type = metadata.get("domain_type") or infer_domain_type(domain)
    source_type = normalize_source_type(source, metadata.get("source_type"))
    source_class = normalize_source_class(
        source,
        source_type=source_type,
        explicit_class=metadata.get("source_class"),
        page_type=metadata.get("page_type"),
        logical_name=logical_name,
        domain=domain,
    )
    return {
        "canonical_label": canonical_label,
        "display_label": display_label,
        "source_url": source_url,
        "source_type": source_type,
        "source_class": source_class,
        "domain": domain,
        "domain_type": domain_type,
        "label": display_label,
        "source": source,
        "url": source_url,
        "page": page,
        "content_type": result.get("content_type") or metadata.get("content_type"),
    }


def format_source_name(result: dict) -> str:
    """Format the human-readable source name for context assembly."""
    return str(build_source_payload(result)["display_label"])


def format_source_with_url(result: dict) -> str:
    """Format source name with clickable URL if available."""
    payload = build_source_payload(result)
    if payload["source_url"]:
        return f"{payload['display_label']} ({payload['source_url']})"
    return str(payload["display_label"])


def build_chat_sources(results: list[dict]) -> list[ChatSource]:
    """Build structured source citations for API responses."""
    return [ChatSource(**build_source_payload(result)) for result in results]


def build_context_and_sources(results: list[dict]) -> tuple[str, list[str], list[ChatSource]]:
    context_parts: list[str] = []
    source_labels: list[str] = []
    chat_sources = build_chat_sources(results)

    for result, chat_source in zip(results, chat_sources):
        source_name = chat_source.display_label
        source_labels.append(source_name)
        context_parts.append(f"[Source: {source_name}]\n{result['content']}")

    return "\n\n".join(context_parts), source_labels, chat_sources
