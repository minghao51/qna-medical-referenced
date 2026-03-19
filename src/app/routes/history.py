"""Chat history management endpoints bound to a server-issued session cookie."""

from fastapi import APIRouter, Request, Response

from src.app.session import ensure_chat_session, get_chat_session_id, rotate_chat_session

router = APIRouter()


@router.get(
    "/history",
    summary="Get chat history",
    description="Retrieve all messages in the conversation history for the current chat session",
)
def get_history(request: Request, response: Response):
    session_id = ensure_chat_session(request, response)
    return {"history": request.app.state.chat_history_store.get_history(session_id)}


@router.delete(
    "/history",
    summary="Clear chat history",
    description="Delete all messages in the conversation history for the current chat session",
)
def clear_history(request: Request, response: Response):
    session_id = get_chat_session_id(request)
    if session_id:
        request.app.state.chat_history_store.clear_history(session_id)
    next_session_id = rotate_chat_session(response)
    request.state.chat_session_id = next_session_id
    return {"status": "cleared"}


@router.get(
    "/history/{session_id}",
    summary="Get chat history (legacy)",
    description="Deprecated. Returns history for the current cookie-bound chat session.",
    deprecated=True,
)
def get_history_legacy(session_id: str, request: Request, response: Response):
    del session_id
    return get_history(request, response)


@router.delete(
    "/history/{session_id}",
    summary="Clear chat history (legacy)",
    description="Deprecated. Clears history for the current cookie-bound chat session.",
    deprecated=True,
)
def clear_history_legacy(session_id: str, request: Request, response: Response):
    del session_id
    return clear_history(request, response)
