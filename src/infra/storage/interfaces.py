"""Storage abstractions for chat history persistence."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol


class ChatHistoryStore(Protocol):
    def turn(self, session_id: str) -> AbstractContextManager[None]: ...

    def save_turn(self, session_id: str, message: str, response: str) -> None: ...

    def get_history(self, session_id: str) -> list[dict]: ...

    def save_message(self, session_id: str, role: str, content: str) -> None: ...

    def clear_history(self, session_id: str) -> None: ...
