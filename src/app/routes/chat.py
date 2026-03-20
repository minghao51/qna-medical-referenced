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
from fastapi.responses import StreamingResponse

from src.app.logging import log_event
from src.app.schemas import ChatRequest
from src.app.session import get_chat_session_id
from src.config import settings
from src.usecases.chat import stream_chat_message

logger = logging.getLogger(__name__)

router = APIRouter()


async def chat_stream_generator(
    request: Request,
    payload: ChatRequest,
    include_pipeline: bool,
):
    try:
        session_id = get_chat_session_id(request) or "default"
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
                event = json.dumps(
                    {
                        "content": "",
                        "done": True,
                        "sources": metadata.get("sources", []),
                        "pipeline": metadata.get("pipeline"),
                        "error": metadata.get("error"),
                    }
                )
                yield f"data: {event}\n\n"

    except Exception:
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
        error_event = json.dumps({"content": "", "done": True, "error": "An error occurred"})
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
    return StreamingResponse(
        chat_stream_generator(request, payload, include_pipeline),
        media_type="text/event-stream",
    )
