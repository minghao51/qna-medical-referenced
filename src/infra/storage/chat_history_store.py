"""Chat history storage using file-based persistence.

This module provides simple file-based storage for chat conversation history.
Each session's messages are stored in a JSON file with structure:
    {
        "session_id": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }

Storage format:
    - File: JSON file at path specified by CHAT_HISTORY_FILE
    - Structure: Dictionary mapping session_id to list of messages
    - Persistence: Immediate write on every save_message call
    - Concurrency: No locking - not suitable for multi-process deployments

Limitations:
    - No transaction support
    - No concurrent write handling
    - Performance degrades with many messages
    - Entire file read/written on each operation

For production use, consider replacing with:
    - SQLite database for better performance and ACID guarantees
    - Redis for distributed systems
    - PostgreSQL for multi-instance deployments

Example:
    Save and retrieve messages:
        from src.infra.storage import chat_history_store

        chat_history_store.save_message("user-123", "user", "Hello")
        chat_history_store.save_message("user-123", "assistant", "Hi there!")
        history = chat_history_store.get_history("user-123")
"""

import json

from src.config import CHAT_HISTORY_FILE


def _load_history() -> dict:
    """Load chat history from disk.

    Reads the JSON file containing all chat histories. Returns empty
    dict if file doesn't exist or is corrupted.

    Returns:
        Dictionary mapping session_id to list of message dicts

    Note:
        This function is called on every read/write operation. For
        better performance with high traffic, consider caching.
    """
    if not CHAT_HISTORY_FILE.exists():
        return {}
    try:
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_history(history: dict) -> None:
    """Save chat history to disk.

    Writes the entire history dictionary to JSON file. Creates parent
    directories if they don't exist.

    Args:
        history: Dictionary mapping session_id to list of message dicts

    Note:
        This is a synchronous write operation. For high-traffic scenarios,
        consider async writes or batching updates.
    """
    CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def get_history(session_id: str) -> list[dict]:
    """Get conversation history for a session.

    Retrieves all messages for the specified session in chronological order.

    Args:
        session_id: Unique identifier for the conversation session

    Returns:
        List of message dictionaries with 'role' and 'content' keys.
        Returns empty list if session doesn't exist.

    Example:
        >>> get_history("user-123")
        [
            {"role": "user", "content": "What is cholesterol?"},
            {"role": "assistant", "content": "Cholesterol is a..."}
        ]
    """
    history = _load_history()
    return history.get(session_id, [])


def save_message(session_id: str, role: str, content: str) -> None:
    """Save a message to the conversation history.

    Appends a new message to the specified session's history.
    Creates the session if it doesn't exist. Writes to disk immediately.

    Args:
        session_id: Unique identifier for the conversation session
        role: Message role, typically "user" or "assistant"
        content: Message text content

    Example:
        >>> save_message("user-123", "user", "Hello!")
        >>> save_message("user-123", "assistant", "Hi there!")
    """
    history = _load_history()
    if session_id not in history:
        history[session_id] = []
    history[session_id].append({
        "role": role,
        "content": content
    })
    _save_history(history)


def clear_history(session_id: str) -> None:
    """Clear all messages for a session.

    Deletes the entire conversation history for the specified session.
    This is useful for starting fresh conversations or for privacy.

    Args:
        session_id: Unique identifier for the conversation session

    Note:
        If session doesn't exist, this is a no-op (no error raised).

    Example:
        >>> clear_history("user-123")
        # All messages for user-123 are now deleted
    """
    history = _load_history()
    if session_id in history:
        del history[session_id]
    _save_history(history)
