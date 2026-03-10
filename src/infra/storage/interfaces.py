"""Storage abstractions for chat history persistence."""

from __future__ import annotations

from typing import Protocol


class ChatHistoryStore(Protocol):
    def get_history(self, session_id: str) -> list[dict]: ...

    def save_message(self, session_id: str, role: str, content: str) -> None: ...

    def clear_history(self, session_id: str) -> None: ...
