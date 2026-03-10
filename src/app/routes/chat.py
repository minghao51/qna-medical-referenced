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
        "message": "What is a normal cholesterol level?",
        "session_id": "user-123"
      }'
"""

import logging
from typing import Union

from fastapi import APIRouter, Query, Request

from src.app.logging import log_event
from src.app.schemas import ChatRequest, ChatResponse
from src.rag.trace_models import ChatResponseWithPipeline
from src.usecases.chat import process_chat_message

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/chat",
    response_model=Union[ChatResponse, ChatResponseWithPipeline],
    summary="Process chat message with RAG",
    description="Process a user message using retrieval-augmented generation. "
    "Retrieves relevant medical documents and generates an evidence-based response.",
)
def chat(
    request: Request,
    payload: ChatRequest,
    include_pipeline: bool = Query(
        False,
        description="Include detailed pipeline trace with timing information for debugging",
    ),
):
    """Process a chat message using RAG (Retrieval-Augmented Generation).

    This endpoint:
    1. Retrieves the user's session history (if session_id provided)
    2. Searches the vector database for relevant medical documents
    3. Generates a response using Qwen LLM with retrieved context
    4. Saves the conversation to history
    5. Returns the response with source citations

    Args:
        request: FastAPI request object (used to access app.state.llm_client)
        payload: Chat request containing message and optional session_id
        include_pipeline: If True, returns detailed pipeline trace with:
            - Retrieval timing and document counts
            - Generation timing
            - Individual pipeline step details

    Returns:
        ChatResponse: Standard response with:
            - response: Generated answer text
            - sources: List of retrieved document sources

        ChatResponseWithPipeline (if include_pipeline=True): Extended response with:
            - response: Generated answer text
            - sources: List of retrieved document sources
            - pipeline: Detailed trace with timing metrics

    Raises:
        HTTPException(500): If an error occurs during processing

    Example:
        Standard request:
            POST /chat
            {
                "message": "What is a normal cholesterol level?",
                "session_id": "user-123"
            }

        Response:
            {
                "response": "According to medical guidelines...",
                "sources": [
                    {
                        "source": "healthhub.sg",
                        "title": "Cholesterol Screening",
                        "url": "https://www.healthhub.sg/..."
                    }
                ]
            }

        With pipeline trace:
            POST /chat?include_pipeline=true
            {
                "message": "What is diabetes?",
                "session_id": "user-123"
            }

        Response:
            {
                "response": "Diabetes is a chronic condition...",
                "sources": [...],
                "pipeline": {
                    "retrieval": {
                        "timing_ms": 150,
                        "num_candidates": 5
                    },
                    "generation": {
                        "timing_ms": 1200
                    },
                    "total_time_ms": 1350
                }
            }
    """
    try:
        llm_client = getattr(request.app.state, "llm_client", None)
        history_store = request.app.state.chat_history_store
        result = process_chat_message(
            llm_client=llm_client,
            history_store=history_store,
            message=payload.message,
            session_id=payload.session_id,
            include_pipeline=include_pipeline,
            top_k=5,
        )

        if include_pipeline:
            return ChatResponseWithPipeline(
                response=result["response"],
                sources=result["sources"],
                pipeline=result["pipeline"],
            )

        return ChatResponse(response=result["response"], sources=result["sources"])
    except Exception:
        log_event(
            logger,
            logging.ERROR,
            "chat_failed",
            request_id=getattr(request.state, "request_id", None),
            session_id=payload.session_id,
            include_pipeline=include_pipeline,
            auth_key_id=getattr(getattr(request.state, "auth", None), "key_id", None),
        )
        raise
