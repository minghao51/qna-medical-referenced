"""Chat orchestration logic for RAG-based conversations.

This module contains the core chat processing logic that coordinates retrieval,
generation, and history persistence. It serves as the use case layer that
orchestrates the RAG pipeline and LLM client to produce chat responses.

Flow:
    1. Retrieve conversation history for the session
    2. Perform RAG retrieval (with or without pipeline trace)
    3. Combine history context and retrieved context
    4. Generate response using LLM
    5. Save user message and assistant response to history
    6. Return response with sources and optional pipeline trace

Example:
    Process a chat message:
        from src.usecases.chat import process_chat_message
        from src.infra.llm import get_client

        result = process_chat_message(
            llm_client=get_client(),
            message="What is a normal CBC count?",
            session_id="user-123",
            include_pipeline=True
        )
        print(result["response"])
"""

import logging
import time
from typing import Any, AsyncGenerator, Optional

from src.app.exceptions import UpstreamServiceError
from src.infra.llm import get_client
from src.infra.storage.interfaces import ChatHistoryStore
from src.rag import retrieve_context, retrieve_context_with_trace, retrieve_context_with_trace_async

logger = logging.getLogger(__name__)


def _build_history_context(history: list[dict[str, str]]) -> str:
    """Convert conversation history to a context string.

    Args:
        history: List of message dictionaries with 'role' and 'content' keys

    Returns:
        Formatted string with role-labeled messages joined by newlines

    Example:
        Input: [{"role": "user", "content": "Hello"}]
        Output: "user: Hello"
    """
    return "\n".join(f"{msg['role']}: {msg['content']}" for msg in history)


def _compose_full_context(history_context: str, retrieved_context: str) -> str:
    """Combine history and retrieved contexts into a single context string.

    Args:
        history_context: Conversation history formatted as a string
        retrieved_context: RAG-retrieved reference information

    Returns:
        Combined context string. If history is empty, returns only retrieved context.
    """
    if not history_context:
        return retrieved_context
    return f"{history_context}\n\nContext: {retrieved_context}"


def process_chat_message(
    *,
    llm_client: Any,
    history_store: ChatHistoryStore,
    message: str,
    session_id: Optional[str],
    include_pipeline: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
    """Run retrieval + generation, persist history, and optionally include a trace.

    This is the main chat processing function that orchestrates the entire
    RAG pipeline. It retrieves relevant context, generates a response, and
    tracks timing information for monitoring and debugging.

    Args:
        llm_client: LLM client instance (QwenClient or compatible)
        message: User's question or message
        session_id: Session identifier for history persistence.
                   If None, uses "default" session
        include_pipeline: If True, includes detailed pipeline trace with timing
        top_k: Number of documents to retrieve from vector store (default: 5)

    Returns:
        Dictionary containing:
            - "response": Generated assistant response text
            - "sources": List of retrieved document sources
            - "pipeline": PipelineTrace object if include_pipeline=True, else None

    Pipeline trace includes:
        - Retrieval timing and document counts
        - Generation timing
        - Total request processing time
        - Individual pipeline step details

    Side effects:
        - Saves user message and assistant response to chat history store
        - Updates pipeline trace with timing information if tracing enabled
    """
    resolved_session_id = session_id or "default"
    history = history_store.get_history(resolved_session_id)
    history_context = _build_history_context(history)

    pipeline_trace = None
    chat_start = time.time()

    if include_pipeline:
        context, sources, pipeline_trace = retrieve_context_with_trace(message, top_k=top_k)
    else:
        context, sources = retrieve_context(message, top_k=top_k)

    full_context = _compose_full_context(history_context, context)

    gen_start = time.time()
    client = llm_client or get_client()
    try:
        response = client.generate(prompt=message, context=full_context)
    except Exception as exc:
        logger.exception("Chat generation failed for session %s", resolved_session_id)
        raise UpstreamServiceError("An error occurred processing your request") from exc
    gen_timing_ms = int((time.time() - gen_start) * 1000)

    if pipeline_trace is not None:
        pipeline_trace.generation.timing_ms = gen_timing_ms
        pipeline_trace.total_time_ms = int((time.time() - chat_start) * 1000)

    history_store.save_message(resolved_session_id, "user", message)
    history_store.save_message(resolved_session_id, "assistant", response)

    return {
        "response": response,
        "sources": sources,
        "pipeline": pipeline_trace,
    }


async def stream_chat_message(
    *,
    llm_client: Any,
    history_store: ChatHistoryStore,
    message: str,
    session_id: Optional[str],
    include_pipeline: bool = False,
    top_k: int = 5,
) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
    """Stream response tokens while performing RAG.

    Runs RAG synchronously (needed before generation), then streams tokens
    from the LLM. Saves messages to history when stream completes.

    Args:
        llm_client: LLM client instance (QwenClient or compatible)
        message: User's question
        session_id: Session identifier for history persistence
        include_pipeline: If True, includes pipeline trace in final metadata
        top_k: Number of documents to retrieve (default: 5)

    Yields:
        Tuple of (content, metadata) where:
        - content: Token string (may be empty for metadata-only events)
        - metadata: Dict with keys: done (bool), sources (list), pipeline (dict), error (str)

    On completion, yields final metadata with done=True and sources.
    On error after partial output, yields with error key set.
    """
    resolved_session_id = session_id or "default"
    history = history_store.get_history(resolved_session_id)
    history_context = _build_history_context(history)

    pipeline_trace = None
    chat_start = time.time()
    client = llm_client or get_client()

    context, sources, pipeline_trace = await retrieve_context_with_trace_async(
        message,
        top_k=top_k,
        hyde_client=client,
    )
    if not include_pipeline:
        pipeline_trace = None

    full_context = _compose_full_context(history_context, context)

    gen_start = time.time()
    accumulated_response = ""

    try:
        async for token in client.a_generate_stream(prompt=message, context=full_context):
            accumulated_response += token
            yield (token, {"done": False})

        gen_timing_ms = int((time.time() - gen_start) * 1000)
        if pipeline_trace is not None:
            pipeline_trace.generation.timing_ms = gen_timing_ms
            pipeline_trace.total_time_ms = int((time.time() - chat_start) * 1000)

        history_store.save_message(resolved_session_id, "user", message)
        history_store.save_message(resolved_session_id, "assistant", accumulated_response)

        yield (
            "",
            {
                "done": True,
                "sources": sources,
                "pipeline": pipeline_trace,
            },
        )

    except Exception as exc:
        logger.exception("Error during stream for session %s", resolved_session_id)
        try:
            history_store.save_message(resolved_session_id, "user", message)
            if accumulated_response:
                history_store.save_message(resolved_session_id, "assistant", accumulated_response)
        except Exception:
            logger.warning("Failed to save partial error message to history for session %s", resolved_session_id)

        try:
            yield (
                "",
                {
                    "done": True,
                    "sources": sources,
                    "pipeline": pipeline_trace,
                    "error": "An error occurred processing your request",
                    "error_code": "chat_stream_failed",
                },
            )
        except Exception:
            logger.exception("Failed to yield error event for session %s", resolved_session_id)
        raise UpstreamServiceError("An error occurred processing your request") from exc
