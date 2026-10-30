"""FastAPI application factory and configuration.

This module provides the application factory pattern for creating and
configuring the FastAPI application. It sets up middleware, routes,
lifecycle hooks, and CORS policies.

Middleware Order (Important, outermost to innermost):
    1. CORS - Handles cross-origin requests; outermost so preflight and
       auth-error responses still carry CORS headers
    2. Request Lifecycle - Gates shutdown admission
    3. RequestID - Adds unique request IDs for tracing
    4. APIKey - Validates authentication
    5. RateLimit - Enforces rate limiting per client
    6. router

Starlette wraps middleware in reverse registration order, so the middleware
added last is the outermost layer.

Example:
    Create a test application:
        from src.app.factory import create_app
        app = create_app()
        # Use app for testing...
"""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import uuid4

import anyio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from src.app.exceptions import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
)
from src.app.logging import configure_logging, log_event
from src.app.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestIDMiddleware
from src.app.routes import (
    chat_router,
    config_router,
    documents_router,
    evaluation_router,
    experiments_router,
    health_router,
    history_router,
)
from src.app.security import validate_security_configuration
from src.config import settings
from src.config.context import reset_runtime_state
from src.infra.llm import get_client
from src.infra.storage.file_chat_history_store import FileChatHistoryStore
from src.infra.telemetry import (
    ErrorCode,
    Operation,
    Route,
    Telemetry,
    telemetry_operation,
    use_telemetry,
)
from src.ingestion.indexing.factory import ChromaVectorStoreFactory
from src.rag import initialize_runtime_index_async

configure_logging(settings.app.log_level)
logger = logging.getLogger(__name__)

ExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]


async def _await_owned_task(task: asyncio.Task[Any]) -> None:
    """Drain a lifespan-owned task before propagating even repeated cancellation."""
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
            task.exception()  # Consume a failure; caller cancellation stays primary.
        raise


class _RequestLifecycle:
    """Track requests owned by one app instance and gate shutdown admission."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._active = 0
        self._closing = False

    async def acquire(self) -> bool:
        async with self._condition:
            if self._closing:
                return False
            self._active += 1
            return True

    async def release(self) -> None:
        async with self._condition:
            self._active -= 1
            if self._active == 0:
                self._condition.notify_all()

    async def stop_and_drain(self) -> None:
        async with self._condition:
            self._closing = True
            await self._condition.wait_for(lambda: self._active == 0)


class _RequestLifecycleMiddleware:
    """Hold app request ownership until the ASGI response has fully settled."""

    def __init__(self, app: ASGIApp, tracker: _RequestLifecycle) -> None:
        self.app = app
        self.tracker = tracker

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if not await self.tracker.acquire():
            request_id = str(uuid4())
            app_instance = scope.get("app")
            telemetry = getattr(getattr(app_instance, "state", None), "telemetry", None)
            if not isinstance(telemetry, Telemetry):
                telemetry = None
            log_event(
                logger, logging.WARNING, "request_rejected", request_id=request_id, status_code=503
            )
            with use_telemetry(telemetry):
                with telemetry_operation(Operation.REQUEST, request_id=request_id) as span:
                    await Response(
                        "Application is shutting down",
                        status_code=503,
                        headers={"X-Request-ID": request_id},
                    )(scope, receive, send)
                    span.finish(outcome="error", error_code=ErrorCode.SHUTDOWN)
            return
        app_instance = scope.get("app")
        telemetry = getattr(getattr(app_instance, "state", None), "telemetry", None)
        if not isinstance(telemetry, Telemetry):
            telemetry = None
        path = scope.get("path", "")
        route = None
        if path in {"/chat", "/chat/"}:
            route = Route.CHAT
        elif path == "/evaluation" or path.startswith("/evaluation/"):
            route = Route.EVALUATION
        try:
            with use_telemetry(telemetry):
                if telemetry is None:
                    await self.app(scope, receive, send)
                else:
                    with telemetry.span(Operation.REQUEST, route=route):
                        await self.app(scope, receive, send)
        finally:
            await _await_owned_task(asyncio.create_task(self.tracker.release()))


async def _shutdown_lifespan(app: FastAPI, llm_client: Any, telemetry: Telemetry | None) -> None:
    await app.state.request_lifecycle.stop_and_drain()
    await _cleanup_lifespan(app, llm_client, telemetry)


async def _cleanup_lifespan(app: FastAPI, llm_client: Any, telemetry: Telemetry | None) -> None:
    try:
        close = getattr(llm_client, "aclose", None)
        if close is not None:
            await close()
    except Exception:
        # Do not mask startup failures or export SDK exception/credential details.
        logger.warning("LLM client cleanup failed")
    finally:
        try:
            if telemetry is not None:
                if await telemetry.aclose() is False:
                    logger.warning("Telemetry cleanup incomplete")
        except BaseException:
            # Telemetry shutdown is best-effort and must not mask application cleanup.
            pass
        finally:
            app.state.telemetry = None
            app.state.llm_client = None
            app.state.chat_history_store = None
            app.state.vector_store = None
            try:
                ChromaVectorStoreFactory.reset()
            finally:
                reset_runtime_state()


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
        - Construct dependencies (LLM client, chat history store, vector store)
          and stash them on app.state — this lifespan is the composition root
        - Load vector index into memory for fast retrieval

    Shutdown tasks:
        - Drain owned startup/cleanup tasks before resetting shared state
        - Close the client constructed here, not an injected app.state replacement
        - Reset logical vector-store/runtime state and clear dependency references
    """
    # Startup — composition root (roadmap P3.1): the only server-side place
    # that constructs concrete dependencies. Routes read them through the
    # accessors in src.app.dependencies.
    _wandb_key = settings.wandb.wandb_api_key.get_secret_value()
    if _wandb_key:
        os.environ["WANDB_API_KEY"] = _wandb_key

    llm_client = None
    owned_telemetry = None
    try:
        owned_telemetry = Telemetry(settings.telemetry)
        app.state.telemetry = owned_telemetry
        llm_client = get_client()
        app.state.llm_client = llm_client
        app.state.chat_history_store = FileChatHistoryStore()

        from src.rag.production_profile import apply_production_profile

        profile_name = settings.production.production_profile
        if profile_name:
            if apply_production_profile(profile_name):
                logger.info(f"Production profile applied: {profile_name}")

        chroma_host = settings.storage.chroma_server_host.strip()
        index_location = (
            f"{chroma_host}:{settings.storage.chroma_server_port}"
            if chroma_host
            else str(settings.storage.chroma_persist_directory)
        )
        logger.info(
            "Serving index: location=%s collection_name=%s production_profile=%s",
            index_location,
            settings.storage.collection_name,
            profile_name or "none",
        )

        # The worker warms the singleton off-loop. Shield/drain it on cancellation
        # so it cannot publish readiness after cleanup has reset the factory/state.
        initialization = asyncio.create_task(initialize_runtime_index_async(allow_build=False))
        await _await_owned_task(initialization)
        app.state.vector_store = ChromaVectorStoreFactory.get_vector_store()
        logger.info("Application startup complete")
        yield
    finally:
        logger.info("Application shutting down")
        cleanup = asyncio.create_task(_shutdown_lifespan(app, llm_client, owned_telemetry))
        await _await_owned_task(cleanup)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Sets up the complete application with all routes, middleware, and
    lifecycle hooks. This factory pattern enables easy testing and
    multiple application instances if needed.

    Returns:
        FastAPI: Configured application instance ready to run

    Middleware configuration (outermost to innermost):
        - CORS: Allows requests from frontend dev servers
        - Lifecycle: Rejects requests once shutdown has started
        - RequestID: Adds X-Request-ID header for tracing
        - APIKey: Validates X-API-Key header if configured
        - RateLimit: Limits requests to 60/minute per client

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

    request_lifecycle = _RequestLifecycle()
    app.state.request_lifecycle = request_lifecycle
    app.state.telemetry = None

    # Registration order below is innermost-first: Starlette reverses it, so the
    # last add_middleware call becomes the outermost layer.
    # Rate limiting (prevents abuse)
    app.add_middleware(RateLimitMiddleware)
    # Authentication before rate-limit key selection
    app.add_middleware(APIKeyMiddleware)
    # Request tracking outside auth so errors also carry request ids
    app.add_middleware(RequestIDMiddleware)
    # Shutdown gate must reject requests before they reach app work.
    app.add_middleware(_RequestLifecycleMiddleware, tracker=request_lifecycle)
    # CORS registered last so it is outermost: preflight (which the API-key
    # middleware would answer with 401) and auth-error responses carry the
    # Access-Control-Allow-* headers the browser needs.
    # Allows frontend to communicate with backend during development
    # For production, update allow_origins with actual frontend domain
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            o.strip() for o in settings.api.cors_allowed_origins.split(",") if o.strip()
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-API-Key"],
    )

    # Register route modules
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(history_router)
    app.include_router(evaluation_router)
    app.include_router(config_router)
    app.include_router(experiments_router)
    app.include_router(documents_router)
    request_exception_handler = cast(ExceptionHandler, app_error_handler)
    http_request_exception_handler = cast(ExceptionHandler, http_exception_handler)
    app.add_exception_handler(AppError, request_exception_handler)
    app.add_exception_handler(HTTPException, http_request_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    return app


app = create_app()
