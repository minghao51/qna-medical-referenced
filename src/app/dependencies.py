"""FastAPI dependency accessors for app.state-managed dependencies.

The composition root is the application lifespan in ``src.app.factory``:
it constructs the LLM client, chat history store, and vector store and
stashes them on ``app.state``. Routes receive them through these
accessors (usable directly or via ``fastapi.Depends``) instead of
reaching for module-level ``get_*()`` singletons (roadmap P3.1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from fastapi import Request

if TYPE_CHECKING:
    from src.infra.llm.interfaces import LLMClient
    from src.infra.storage.interfaces import ChatHistoryStore
    from src.rag.protocols import VectorStoreProtocol


def _require(state: object, attr: str) -> Any:
    value = getattr(state, attr, None)
    if value is None:
        raise RuntimeError(
            f"{attr} not initialized — the application lifespan "
            "(composition root in src.app.factory) did not run or did not "
            "construct this dependency"
        )
    return value


def get_llm_client(request: Request) -> LLMClient:
    """Return the LLM client constructed by the application lifespan."""
    return cast("LLMClient", _require(request.app.state, "llm_client"))


def get_chat_history_store(request: Request) -> ChatHistoryStore:
    """Return the chat history store constructed by the application lifespan."""
    return cast("ChatHistoryStore", _require(request.app.state, "chat_history_store"))


def get_vector_store(request: Request) -> VectorStoreProtocol:
    """Return the vector store constructed by the application lifespan."""
    return cast("VectorStoreProtocol", _require(request.app.state, "vector_store"))
