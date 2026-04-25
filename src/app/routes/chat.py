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

import json
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response, StreamingResponse

from src.app.logging import log_event
from src.app.schemas import ChatRequest
from src.app.session import ensure_chat_session, get_chat_session_id
from src.config import settings
from src.usecases.chat import stream_chat_message

logger = logging.getLogger(__name__)

router = APIRouter()


async def chat_stream_generator(
    request: Request,
    payload: ChatRequest,
    include_pipeline: bool,
):
    sent_terminal_event = False
    try:
        session_id = (
            request.state.chat_session_id or get_chat_session_id(request) or "default"
        )
        llm_client = getattr(request.app.state, "llm_client", None)
        history_store = request.app.state.chat_history_store

        async for content, metadata in stream_chat_message(
            llm_client=llm_client,
            history_store=history_store,
            message=payload.message,
            session_id=session_id,
            include_pipeline=include_pipeline,
            top_k=5,
        ):
            if content:
                event = json.dumps({"content": content, "done": False})
                yield f"data: {event}\n\n"

            if metadata.get("done"):
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
                except Exception:
                    logger.exception("Failed to serialize SSE event")
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

    except Exception:
        logger.exception("Chat stream generator failed")
        log_event(
            logger,
            logging.ERROR,
            "chat_failed",
            request_id=getattr(request.state, "request_id", None),
            session_id=getattr(request.state, "chat_session_id", None)
            or request.cookies.get(settings.chat_session_cookie_name),
            include_pipeline=include_pipeline,
            auth_key_id=getattr(getattr(request.state, "auth", None), "key_id", None),
        )
        if not sent_terminal_event:
            error_event = json.dumps(
                {
                    "content": "",
                    "done": True,
                    "error": "An error occurred",
                    "error_code": "chat_failed",
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

    return StreamingResponse(
        chat_stream_generator(request, payload, include_pipeline),
        media_type="text/event-stream",
        headers=headers,
    )
