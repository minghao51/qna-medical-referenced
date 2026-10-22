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
    Process a chat message (dependencies constructed at the caller's edge —
    the app composition root, a CLI entrypoint, or a test):
        from src.usecases.chat import process_chat_message

        result = process_chat_message(
            llm_client=client,
            history_store=history_store,
            message="What is a normal CBC count?",
            session_id="user-123",
            include_pipeline=True
        )
        print(result["response"])
"""

import asyncio
import logging
import re
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing
from typing import Any

import anyio

from src.config import settings
from src.core.exceptions import UpstreamServiceError
from src.infra.llm.conversation_context import conversation_scope
from src.infra.storage.interfaces import ChatHistoryStore
from src.infra.telemetry import (
    ErrorCode,
    Operation,
    Stage,
    start_telemetry_operation,
    telemetry_operation,
)
from src.rag import (
    get_runtime_retrieval_config,
    retrieve_context,
    retrieve_context_with_trace,
    retrieve_context_with_trace_async,
)

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = settings.api.max_message_length
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9\-]+$")


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
    session_id: str | None,
    include_pipeline: bool = False,
    top_k: int | None = None,
) -> dict[str, Any]:
    """Run retrieval + generation, persist history, and optionally include a trace.

    This is the main chat processing function that orchestrates the entire
    RAG pipeline. It retrieves relevant context, generates a response, and
    tracks timing information for monitoring and debugging.

    Args:
        llm_client: LLM client instance (QwenClient or compatible) — required;
            callers construct it at their edge (the app composition root,
            CLI entrypoints, or tests)
        message: User's question or message
        session_id: Session identifier for history persistence.
                   If None, uses "default" session
        include_pipeline: If True, includes detailed pipeline trace with timing
        top_k: Explicit document limit, or None to inherit the effective runtime limit

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
    if resolved_session_id != "default" and not _SESSION_ID_RE.match(resolved_session_id):
        raise ValueError(f"Invalid session_id format: {resolved_session_id!r}")
    if not message or len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"message must be 1-{MAX_MESSAGE_LENGTH} characters")
    if top_k is None:
        top_k = int(get_runtime_retrieval_config()["top_k"])
    with history_store.turn(resolved_session_id):
        history = history_store.get_history(resolved_session_id)
        history_context = _build_history_context(history)

        pipeline_trace = None
        chat_start = time.time()

        with telemetry_operation(Operation.RETRIEVAL) as retrieval_span:
            if include_pipeline:
                context, sources, pipeline_trace = retrieve_context_with_trace(
                    message, top_k=top_k, allow_build=False
                )
            else:
                context, sources = retrieve_context(message, top_k=top_k, allow_build=False)
            retrieval_span.set_result_count(len(sources))

        full_context = _compose_full_context(history_context, context)

        gen_start = time.time()
        try:
            with conversation_scope(resolved_session_id):
                with telemetry_operation(
                    Operation.GENERATION,
                    stage=Stage.GENERATION,
                    model=getattr(llm_client, "model", None),
                ):
                    response = llm_client.generate(prompt=message, context=full_context)
        except Exception as exc:
            logger.error("Chat generation failed")
            raise UpstreamServiceError("An error occurred processing your request") from exc
        gen_timing_ms = int((time.time() - gen_start) * 1000)

        if pipeline_trace is not None:
            model = getattr(llm_client, "model", None)
            if isinstance(model, str):
                pipeline_trace.generation.model = model
            pipeline_trace.generation.timing_ms = gen_timing_ms
            pipeline_trace.total_time_ms = int((time.time() - chat_start) * 1000)

        history_store.save_turn(resolved_session_id, message, response)

        return {
            "response": response,
            "sources": sources,
            "pipeline": pipeline_trace,
        }


async def _run_owned_worker(function: Callable[..., Any], *args: Any) -> Any:
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # An admitted worker cannot be revoked; keep the session until it settles.
        with anyio.CancelScope(shield=True):
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
        if not task.cancelled():
            try:
                task.result()
            except Exception:
                logger.error("Chat worker failed during cancellation")
        raise


async def _save_turn_async(
    history_store: ChatHistoryStore, session_id: str, message: str, response: str
) -> None:
    # Cancellation observed here admits no persistence job.
    await asyncio.sleep(0)
    await _run_owned_worker(history_store.save_turn, session_id, message, response)


async def stream_chat_message(
    *,
    llm_client: Any,
    history_store: ChatHistoryStore,
    message: str,
    session_id: str | None,
    include_pipeline: bool = False,
    top_k: int | None = None,
) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
    """Stream response tokens while performing RAG.

    Awaits async RAG retrieval before generation, then streams tokens
    from the LLM. Saves messages to history when stream completes.

    Args:
        llm_client: LLM client instance (QwenClient or compatible)
        message: User's question
        session_id: Session identifier for history persistence
        include_pipeline: If True, includes pipeline trace in final metadata
        top_k: Explicit document limit, or None to inherit the effective runtime limit

    Yields:
        Tuple of (content, metadata) where:
        - content: Token string (may be empty for metadata-only events)
        - metadata: Dict with keys: done (bool), sources (list), pipeline (dict), error (str)

    On completion, yields final metadata with done=True and sources.
    On error after partial output, yields with error key set.
    """
    resolved_session_id = session_id or "default"
    if top_k is None:
        top_k = int(get_runtime_retrieval_config()["top_k"])
    failure: Exception | None = None
    with history_store.turn(resolved_session_id):
        history = await _run_owned_worker(history_store.get_history, resolved_session_id)
        history_context = _build_history_context(history)

        chat_start = time.time()
        with telemetry_operation(Operation.RETRIEVAL) as retrieval_span:
            context, sources, pipeline_trace = await retrieve_context_with_trace_async(
                message,
                top_k=top_k,
                hyde_client=llm_client,
                allow_build=False,
            )
            retrieval_span.set_result_count(len(sources))
        if not include_pipeline:
            pipeline_trace = None
        full_context = _compose_full_context(history_context, context)
        gen_start = time.time()
        accumulated_response = ""
        model = getattr(llm_client, "model", None)
        generation_span = start_telemetry_operation(
            Operation.GENERATION,
            stage=Stage.GENERATION,
            model=model if isinstance(model, str) else None,
        )

        try:
            # Scope the conversation id around each upstream token pull only,
            # never across the yields below: while a generator is suspended at a
            # yield, its consuming task (and any child task it spawns) would
            # otherwise inherit the contextvar and could attach this
            # conversation's session header to unrelated requests.
            async with aclosing(
                llm_client.a_generate_stream(prompt=message, context=full_context)
            ) as stream:
                while True:
                    with conversation_scope(resolved_session_id):
                        try:
                            token = await anext(stream)
                        except StopAsyncIteration:
                            break
                    accumulated_response += token
                    yield (token, {"done": False})
        except asyncio.CancelledError:
            generation_span.finish(outcome="cancelled", error_code=ErrorCode.CANCELLED)
            cancellation_span = start_telemetry_operation(
                Operation.CANCELLATION,
                stage=Stage.GENERATION,
                error_code=ErrorCode.CANCELLED,
            )
            cancellation_span.finish(outcome="cancelled", error_code=ErrorCode.CANCELLED)
            raise
        except GeneratorExit:
            generation_span.finish(outcome="cancelled", error_code=ErrorCode.CANCELLED)
            cancellation_span = start_telemetry_operation(
                Operation.CANCELLATION,
                stage=Stage.GENERATION,
                error_code=ErrorCode.CANCELLED,
            )
            cancellation_span.finish(outcome="cancelled", error_code=ErrorCode.CANCELLED)
            raise
        except Exception as exc:
            generation_span.finish(outcome="error", error_code=ErrorCode.UPSTREAM)
            error_span = start_telemetry_operation(
                Operation.ERROR,
                stage=Stage.GENERATION,
                error_code=ErrorCode.UPSTREAM,
            )
            error_span.finish(outcome="error", error_code=ErrorCode.UPSTREAM)
            logger.error("Chat stream generation failed")
            failure = exc
        else:
            generation_span.finish()

        if failure is None:
            try:
                gen_timing_ms = int((time.time() - gen_start) * 1000)
                if pipeline_trace is not None:
                    if isinstance(model, str):
                        pipeline_trace.generation.model = model
                    pipeline_trace.generation.timing_ms = gen_timing_ms
                    pipeline_trace.total_time_ms = int((time.time() - chat_start) * 1000)

                await _save_turn_async(
                    history_store, resolved_session_id, message, accumulated_response
                )
            except asyncio.CancelledError:
                cancellation_span = start_telemetry_operation(
                    Operation.CANCELLATION,
                    stage=Stage.PERSISTENCE,
                    error_code=ErrorCode.CANCELLED,
                )
                cancellation_span.finish(outcome="cancelled", error_code=ErrorCode.CANCELLED)
                raise
            except GeneratorExit:
                raise
            except Exception as exc:
                error_span = start_telemetry_operation(
                    Operation.ERROR,
                    stage=Stage.PERSISTENCE,
                    error_code=ErrorCode.INTERNAL,
                )
                error_span.finish(outcome="error", error_code=ErrorCode.INTERNAL)
                logger.error("Chat stream persistence failed")
                failure = exc

    # A terminal consumer must not retain admission after work/cleanup has ended.
    if failure is None:
        yield (
            "",
            {"done": True, "sources": sources, "pipeline": pipeline_trace},
        )
    else:
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
        except asyncio.CancelledError:
            raise
        except GeneratorExit:
            raise
        except Exception:
            logger.error("Failed to yield chat stream error event")
        raise UpstreamServiceError("An error occurred processing your request") from failure
