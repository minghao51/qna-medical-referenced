"""File-backed chat history store with atomic writes."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from src.app.exceptions import StorageError
from src.config import CHAT_HISTORY_FILE


class FileChatHistoryStore:
    def __init__(self, path: Path = CHAT_HISTORY_FILE):
        self.path = Path(path)
        self._lock = threading.RLock()

    def _load_history_unlocked(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_history_unlocked(self, history: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(history, handle, indent=2)
            temp_path.replace(self.path)
        except OSError as exc:
            raise StorageError(f"Failed to write chat history: {exc}") from exc

    def get_history(self, session_id: str) -> list[dict]:
        with self._lock:
            history = self._load_history_unlocked()
            return list(history.get(session_id, []))

    def save_message(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            history = self._load_history_unlocked()
            history.setdefault(session_id, []).append({"role": role, "content": content})
            self._save_history_unlocked(history)

    def clear_history(self, session_id: str) -> None:
        with self._lock:
            history = self._load_history_unlocked()
            history.pop(session_id, None)
            self._save_history_unlocked(history)
