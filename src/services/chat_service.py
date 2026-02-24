"""Chat orchestration logic shared by API handlers."""

import time
from typing import Any, Optional

from src.pipeline import retrieve_context, retrieve_context_with_trace
from src.storage import chat_store


def _build_history_context(history: list[dict[str, str]]) -> str:
    return "\n".join(f"{msg['role']}: {msg['content']}" for msg in history)


def _compose_full_context(history_context: str, retrieved_context: str) -> str:
    if not history_context:
        return retrieved_context
    return f"{history_context}\n\nContext: {retrieved_context}"


def process_chat_message(
    *,
    llm_client: Any,
    message: str,
    session_id: Optional[str],
    include_pipeline: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
    """Run retrieval + generation, persist history, and optionally include a trace."""
    resolved_session_id = session_id or "default"
    history = chat_store.get_history(resolved_session_id)
    history_context = _build_history_context(history)

    pipeline_trace = None
    chat_start = time.time()

    if include_pipeline:
        context, sources, pipeline_trace = retrieve_context_with_trace(message, top_k=top_k)
    else:
        context, sources = retrieve_context(message, top_k=top_k)

    full_context = _compose_full_context(history_context, context)

    gen_start = time.time()
    response = llm_client.generate(prompt=message, context=full_context)
    gen_timing_ms = int((time.time() - gen_start) * 1000)

    if pipeline_trace is not None:
        pipeline_trace.generation.timing_ms = gen_timing_ms
        pipeline_trace.total_time_ms = int((time.time() - chat_start) * 1000)

    chat_store.save_message(resolved_session_id, "user", message)
    chat_store.save_message(resolved_session_id, "assistant", response)

    return {
        "response": response,
        "sources": sources,
        "pipeline": pipeline_trace,
    }

