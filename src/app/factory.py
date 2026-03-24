"""FastAPI application factory and configuration.

This module provides the application factory pattern for creating and
configuring the FastAPI application. It sets up middleware, routes,
lifecycle hooks, and CORS policies.

Middleware Order (Important):
    1. CORS - Handles cross-origin requests (must be first)
    2. RateLimit - Enforces rate limiting per client
    3. APIKey - Validates authentication
    4. RequestID - Adds unique request IDs for tracing and must run outermost

Example:
    Create a test application:
        from src.app.factory import create_app
        app = create_app()
        # Use app for testing...
"""

import logging
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.app.exceptions import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
)
from src.app.logging import configure_logging
from src.app.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestIDMiddleware
from src.app.routes import chat_router, evaluation_router, health_router, history_router
from src.app.security import validate_security_configuration
from src.config import settings
from src.infra.di import get_container, reset_container
from src.infra.storage import FileChatHistoryStore
from src.rag import initialize_runtime_index

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

ExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]


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
        - Initialize dependency injection container
        - Initialize LLM client
        - Load vector index into memory for fast retrieval

    Shutdown tasks:
        - Reset container for clean shutdown
    """
    # Startup
    container = get_container()
    app.state.container = container

    # Initialize LLM client
    app.state.llm_client = container.get_llm_client()

    # Initialize chat history store
    app.state.chat_history_store = FileChatHistoryStore()

    # Initialize vector store
    initialize_runtime_index()
    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutting down")
    reset_container()


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
        - RateLimit: Limits requests to 60/minute per client
        - APIKey: Validates X-API-Key header if configured

    Routes:
        - /health: Health check endpoint
        - /chat: Main chat endpoint with RAG
        - /history: Chat history management
        - /evaluation: Evaluation and metrics endpoints
    """
    validate_security_configuration()

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
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Rate limiting (prevents abuse)
    app.add_middleware(RateLimitMiddleware)
    # Authentication before rate-limit key selection
    app.add_middleware(APIKeyMiddleware)
    # Request tracking outermost so errors also carry request ids
    app.add_middleware(RequestIDMiddleware)

    # Register route modules
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(history_router)
    app.include_router(evaluation_router)
    request_exception_handler = cast(ExceptionHandler, app_error_handler)
    http_request_exception_handler = cast(ExceptionHandler, http_exception_handler)
    app.add_exception_handler(AppError, request_exception_handler)
    app.add_exception_handler(HTTPException, http_request_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    return app


app = create_app()
