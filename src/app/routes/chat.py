import logging
from typing import Union

from fastapi import APIRouter, HTTPException, Query, Request

from src.app.schemas import ChatRequest, ChatResponse
from src.rag.trace_models import ChatResponseWithPipeline
from src.usecases.chat import process_chat_message

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=Union[ChatResponse, ChatResponseWithPipeline])
def chat(
    request: Request,
    payload: ChatRequest,
    include_pipeline: bool = Query(False, description="Include pipeline trace in response"),
):
    try:
        llm_client = getattr(request.app.state, "llm_client", None)
        result = process_chat_message(
            llm_client=llm_client,
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
    except Exception as e:
        logger.error("Chat error: %s: %s", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="An error occurred processing your request")

