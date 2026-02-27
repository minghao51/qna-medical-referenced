import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestIDMiddleware
from src.app.routes import chat_router, health_router, history_router, evaluation_router
from src.infra.llm import get_client
from src.rag import initialize_runtime_index

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm_client = get_client()
    initialize_runtime_index()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Health Screening Interpreter Chatbot",
        description="An intelligent chatbot to help understand health screening results",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(APIKeyMiddleware)

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(history_router)
    app.include_router(evaluation_router)
    return app


app = create_app()

