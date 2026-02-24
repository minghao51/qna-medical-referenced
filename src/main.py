import logging
from contextlib import asynccontextmanager
from typing import Union

from fastapi import FastAPI, HTTPException, Query

from src.api.schemas import ChatRequest, ChatResponse
from src.llm import get_client
from src.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestIDMiddleware
from src.models import ChatResponseWithPipeline
from src.pipeline import initialize_vector_store
from src.services.chat_service import process_chat_message
from src.storage import chat_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm_client = get_client()
    initialize_vector_store()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Health Screening Interpreter Chatbot",
        description="An intelligent chatbot to help understand health screening results",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(APIKeyMiddleware)
    return app


app = create_app()


@app.get("/")
def root():
    return {"message": "Health Screening Interpreter API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/chat", response_model=Union[ChatResponse, ChatResponseWithPipeline])
def chat(
    request: ChatRequest,
    include_pipeline: bool = Query(False, description="Include pipeline trace in response")
):
    try:
        llm_client = getattr(app.state, "llm_client", None) or get_client()
        result = process_chat_message(
            llm_client=llm_client,
            message=request.message,
            session_id=request.session_id,
            include_pipeline=include_pipeline,
            top_k=5,
        )

        if include_pipeline:
            return ChatResponseWithPipeline(
                response=result["response"],
                sources=result["sources"],
                pipeline=result["pipeline"],
            )

        return ChatResponse(
            response=result["response"],
            sources=result["sources"]
        )
    except Exception as e:
        logger.error(f"Chat error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred processing your request")


@app.get("/history/{session_id}")
def get_history(session_id: str):
    return {"history": chat_store.get_history(session_id)}


@app.delete("/history/{session_id}")
def clear_history(session_id: str):
    chat_store.clear_history(session_id)
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
