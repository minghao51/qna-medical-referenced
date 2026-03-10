"""Chat history management endpoints.

This module provides endpoints for retrieving and clearing chat session
history. History is stored in-memory and is lost on server restart.

For production use, consider implementing persistent storage (database).

Endpoints:
    - GET /history/{session_id} - Get conversation history for a session
    - DELETE /history/{session_id} - Clear conversation history for a session

Example:
    Get history:
        curl http://localhost:8001/history/user-123

    Clear history:
        curl -X DELETE http://localhost:8001/history/user-123
"""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get(
    "/history/{session_id}",
    summary="Get chat history",
    description="Retrieve all messages in the conversation history for a given session ID",
)
def get_history(session_id: str, request: Request):
    """Get conversation history for a session.

    Returns all messages (user and assistant) in chronological order
    for the specified session.

    Args:
        session_id: Unique identifier for the conversation session

    Returns:
        Dictionary containing:
            - history: List of message objects with 'role' and 'content' keys

    Example:
        GET /history/user-123

        Response:
        {
            "history": [
                {"role": "user", "content": "What is cholesterol?"},
                {"role": "assistant", "content": "Cholesterol is a..."}
            ]
        }
    """
    return {"history": request.app.state.chat_history_store.get_history(session_id)}


@router.delete(
    "/history/{session_id}",
    summary="Clear chat history",
    description="Delete all messages in the conversation history for a given session ID",
)
def clear_history(session_id: str, request: Request):
    """Clear conversation history for a session.

    Deletes all messages associated with the specified session.
    This is useful for starting a fresh conversation or for privacy.

    Args:
        session_id: Unique identifier for the conversation session

    Returns:
        Dictionary containing:
            - status: "cleared" on success

    Example:
        DELETE /history/user-123

        Response:
        {
            "status": "cleared"
        }
    """
    request.app.state.chat_history_store.clear_history(session_id)
    return {"status": "cleared"}
