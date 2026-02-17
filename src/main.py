import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.llm import get_client
from src.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestIDMiddleware
from src.rag import initialize_vector_store, retrieve_context
from src.storage import chat_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Health Screening Interpreter Chatbot",
    description="An intelligent chatbot to help understand health screening results",
    version="0.1.0"
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(APIKeyMiddleware)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = "default"
    user_context: Optional[str] = None

    @field_validator('message', mode='before')
    @classmethod
    def sanitize_message(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class ChatResponse(BaseModel):
    response: str
    sources: list[str]


llm_client = get_client()
initialize_vector_store()


@app.get("/")
def root():
    return {"message": "Health Screening Interpreter API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        session_id = request.session_id or "default"
        history = chat_store.get_history(session_id)
        
        context, sources = retrieve_context(request.message, top_k=5)
        
        history_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        full_context = f"{history_context}\n\nContext: {context}" if history_context else context

        response = llm_client.generate(
            prompt=request.message,
            context=full_context
        )

        chat_store.save_message(session_id, "user", request.message)
        chat_store.save_message(session_id, "assistant", response)

        return ChatResponse(
            response=response,
            sources=sources
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
