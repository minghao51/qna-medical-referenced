"""Chat API endpoints for RAG-based question answering.

This module provides the main chat endpoint that processes user questions
using Retrieval-Augmented Generation (RAG). It coordinates document retrieval,
LLM generation, and response formatting.

Endpoints:
    - POST /chat - Process a chat message with RAG

Example request:
    curl -X POST http://localhost:8000/chat \\
      -H "Content-Type: application/json" \\
      -d '{
        "message": "What is a normal cholesterol level?"
      }'
"""

import asyncio
import json
import logging
from contextlib import aclosing
from typing import Any

import anyio
from fastapi import APIRouter, Query, Request
from fastapi.responses import Response, StreamingResponse
from starlette.types import Receive, Scope, Send

from src.app.dependencies import get_chat_history_store, get_llm_client
from src.app.logging import log_event
from src.app.schemas import ChatRequest
from src.app.session import ensure_chat_session, get_chat_session_id
from src.core.exceptions import AppError
from src.usecases.chat import stream_chat_message

logger = logging.getLogger(__name__)

router = APIRouter()


async def _close_stream_iterator(iterator: Any) -> None:
    close = getattr(iterator, "aclose", None)
    if close is None:
        return
    task = asyncio.ensure_future(close())
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
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
                logger.error("Chat response iterator cleanup failed")
        raise
    except Exception:
        logger.error("Chat response iterator cleanup failed")


class _ChatStreamingResponse(StreamingResponse):
    """Close the route iterator even when ASGI sending or disconnect handling fails."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await _close_stream_iterator(self.body_iterator)


async def chat_stream_generator(
    request: Request,
    payload: ChatRequest,
    include_pipeline: bool,
):
    sent_terminal_event = False
    try:
        session_id = request.state.chat_session_id or get_chat_session_id(request) or "default"
        llm_client = get_llm_client(request)
        history_store = get_chat_history_store(request)

        async with aclosing(
            stream_chat_message(
                llm_client=llm_client,
                history_store=history_store,
                message=payload.message,
                session_id=session_id,
                include_pipeline=include_pipeline,
            )
        ) as stream:
            async for content, metadata in stream:
                if content and not sent_terminal_event:
                    event = json.dumps({"content": content, "done": False})
                    yield f"data: {event}\n\n"

                if metadata.get("done") and not sent_terminal_event:
                    sources_data = metadata.get("sources", [])
                    if sources_data and hasattr(sources_data[0], "model_dump"):
                        sources_data = [
                            s.model_dump() if hasattr(s, "model_dump") else s for s in sources_data
                        ]
                    pipeline_data = metadata.get("pipeline")
                    if pipeline_data is not None and hasattr(pipeline_data, "model_dump"):
                        pipeline_data = pipeline_data.model_dump()
                    try:
                        event = json.dumps(
                            {
                                "content": "",
                                "done": True,
                                "sources": sources_data,
                                "pipeline": pipeline_data,
                                "error": metadata.get("error"),
                                "error_code": metadata.get("error_code"),
                                "request_id": getattr(request.state, "request_id", None),
                            }
                        )
                        sent_terminal_event = True
                        yield f"data: {event}\n\n"
                    except GeneratorExit:
                        raise
                    except Exception:
                        logger.error("Failed to serialize SSE event")
                        error_event = json.dumps(
                            {
                                "content": "",
                                "done": True,
                                "error": "Serialization error",
                                "error_code": "sse_serialization_failed",
                                "request_id": getattr(request.state, "request_id", None),
                            }
                        )
                        sent_terminal_event = True
                        yield f"data: {error_event}\n\n"

    except GeneratorExit:
        raise
    except Exception as exc:
        busy = isinstance(exc, AppError) and exc.code == "chat_session_busy"
        logger.error("Chat stream generator failed")
        log_event(
            logger,
            logging.ERROR,
            "chat_failed",
            request_id=getattr(request.state, "request_id", None),
            include_pipeline=include_pipeline,
            auth_key_id=getattr(getattr(request.state, "auth", None), "key_id", None),
        )
        if not sent_terminal_event:
            error_event = json.dumps(
                {
                    "content": "",
                    "done": True,
                    "error": (
                        "A request is already active for this chat session"
                        if busy
                        else "An error occurred"
                    ),
                    "error_code": "chat_session_busy" if busy else "chat_failed",
                    "request_id": getattr(request.state, "request_id", None),
                }
            )
            yield f"data: {error_event}\n\n"


@router.post(
    "/chat",
    summary="Process chat message with RAG (streaming)",
    description="Process a user message using retrieval-augmented generation with streaming response.",
)
async def chat(
    request: Request,
    payload: ChatRequest,
    include_pipeline: bool = Query(
        False,
        description="Include detailed pipeline trace with timing information for debugging",
    ),
):
    response = Response()
    ensure_chat_session(request, response)
    headers = {k: v for k, v in dict(response.headers).items() if k.lower() != "content-length"}
    headers["Cache-Control"] = "no-cache"
    headers["X-Accel-Buffering"] = "no"

    return _ChatStreamingResponse(
        chat_stream_generator(request, payload, include_pipeline),
        media_type="text/event-stream",
        headers=headers,
    )
