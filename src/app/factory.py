"""FastAPI application factory and configuration.

This module provides the application factory pattern for creating and
configuring the FastAPI application. It sets up middleware, routes,
lifecycle hooks, and CORS policies.

Middleware Order (Important):
    1. CORS - Handles cross-origin requests (must be first)
    2. RequestID - Adds unique request IDs for tracing
    3. RateLimit - Enforces rate limiting per IP
    4. APIKey - Validates authentication (must be last for security)

Example:
    Create a test application:
        from src.app.factory import create_app
        app = create_app()
        # Use app for testing...
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestIDMiddleware
from src.app.routes import chat_router, evaluation_router, health_router, history_router
from src.infra.llm import get_client
from src.rag import initialize_runtime_index

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Initializes application state on startup and performs cleanup on shutdown.
    This is the ideal place to initialize expensive resources like database
    connections and LLM clients.

    Args:
        app: The FastAPI application instance

    Yields:
        None: Control is transferred to the application during its lifetime

    Startup tasks:
        - Initialize LLM client and store in app.state.llm_client
        - Load vector index into memory for fast retrieval

    Shutdown tasks:
        - Currently none (FastAPI handles cleanup automatically)
    """
    app.state.llm_client = get_client()
    initialize_runtime_index()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Sets up the complete application with all routes, middleware, and
    lifecycle hooks. This factory pattern enables easy testing and
    multiple application instances if needed.

    Returns:
        FastAPI: Configured application instance ready to run

    Middleware configuration:
        - CORS: Allows requests from frontend dev servers
        - RequestID: Adds X-Request-ID header for tracing
        - RateLimit: Limits requests to 60/minute per IP
        - APIKey: Validates X-API-Key header if configured

    Routes:
        - /health: Health check endpoint
        - /chat: Main chat endpoint with RAG
        - /history: Chat history management
        - /evaluation: Evaluation and metrics endpoints
    """
    app = FastAPI(
        title="Health Screening Interpreter Chatbot",
        description="An intelligent chatbot to help understand health screening results",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS must be first middleware
    # Allows frontend to communicate with backend during development
    # For production, update allow_origins with actual frontend domain
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Request tracking middleware
    app.add_middleware(RequestIDMiddleware)
    # Rate limiting (prevents abuse)
    app.add_middleware(RateLimitMiddleware)
    # Authentication (must be last for security)
    app.add_middleware(APIKeyMiddleware)

    # Register route modules
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(history_router)
    app.include_router(evaluation_router)
    return app


app = create_app()

