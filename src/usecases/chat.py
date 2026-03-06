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

import time
from typing import Any, Optional

from src.infra.llm import get_client
from src.infra.storage import chat_history_store
from src.rag import retrieve_context, retrieve_context_with_trace


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
        llm_client: LLM client instance (GeminiClient or compatible)
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
    history = chat_history_store.get_history(resolved_session_id)
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
    response = client.generate(prompt=message, context=full_context)
    gen_timing_ms = int((time.time() - gen_start) * 1000)

    if pipeline_trace is not None:
        pipeline_trace.generation.timing_ms = gen_timing_ms
        pipeline_trace.total_time_ms = int((time.time() - chat_start) * 1000)

    chat_history_store.save_message(resolved_session_id, "user", message)
    chat_history_store.save_message(resolved_session_id, "assistant", response)

    return {
        "response": response,
        "sources": sources,
        "pipeline": pipeline_trace,
    }
