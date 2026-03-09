"""Formatting helpers for retrieved context and sources."""


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


def build_context_and_sources(results: list[dict]) -> tuple[str, list[str]]:
    context_parts: list[str] = []
    sources: list[str] = []

    for result in results:
        source_name = format_source_name(result)
        sources.append(source_name)
        context_parts.append(f"[Source: {source_name}]\n{result['content']}")

    return "\n\n".join(context_parts), sources
