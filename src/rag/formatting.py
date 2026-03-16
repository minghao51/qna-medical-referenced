"""Formatting helpers for retrieved context and sources."""

from src.rag.trace_models import ChatSource


def format_source_name(result: dict) -> str:
    """Format source name, preferring logical_name if available."""
    metadata = result.get("metadata", {})
    logical_name = metadata.get("logical_name")
    display_name = logical_name if logical_name else result.get("source", "unknown")
    page = result.get("page")
    page_info = f" page {page}" if page else ""
    return f"{display_name}{page_info}"


def format_source_with_url(result: dict) -> str:
    """Format source name with clickable URL if available."""
    metadata = result.get("metadata", {})
    url = metadata.get("source_url")
    source_name = format_source_name(result)
    if url:
        return f"{source_name} ({url})"
    return source_name


def build_chat_sources(results: list[dict]) -> list[ChatSource]:
    """Build structured source citations for API responses."""
    sources: list[ChatSource] = []

    for result in results:
        metadata = result.get("metadata", {})
        sources.append(
            ChatSource(
                label=format_source_name(result),
                source=result.get("source", "unknown"),
                url=metadata.get("source_url"),
                page=result.get("page"),
            )
        )

    return sources


def build_context_and_sources(results: list[dict]) -> tuple[str, list[str], list[ChatSource]]:
    context_parts: list[str] = []
    source_labels: list[str] = []
    chat_sources = build_chat_sources(results)

    for result, chat_source in zip(results, chat_sources):
        source_name = chat_source.label
        source_labels.append(source_name)
        context_parts.append(f"[Source: {source_name}]\n{result['content']}")

    return "\n\n".join(context_parts), source_labels, chat_sources
