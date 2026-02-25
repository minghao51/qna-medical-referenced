"""Formatting helpers for retrieved context and sources."""


def format_source_name(result: dict) -> str:
    page = result.get("page")
    page_info = f" page {page}" if page else ""
    return f"{result['source']}{page_info}"


def build_context_and_sources(results: list[dict]) -> tuple[str, list[str]]:
    context_parts: list[str] = []
    sources: list[str] = []

    for result in results:
        source_name = format_source_name(result)
        sources.append(source_name)
        context_parts.append(f"[Source: {source_name}]\n{result['content']}")

    return "\n\n".join(context_parts), sources

