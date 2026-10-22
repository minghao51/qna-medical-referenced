"""File-backed chat history store with atomic writes."""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.config import CHAT_HISTORY_FILE
from src.config.settings import settings
from src.core.exceptions import AppError, StorageError

logger = logging.getLogger(__name__)

SESSION_SCHEMA_VERSION = 2


class FileChatHistoryStore:
    def __init__(
        self,
        path: Path = CHAT_HISTORY_FILE,
        *,
        ttl_seconds: int | None = None,
        max_messages_per_session: int | None = None,
    ):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._turn_lock = threading.Lock()
        self._active_turns: set[str] = set()
        self.ttl_seconds = (
            settings.api.chat_history_ttl_seconds if ttl_seconds is None else ttl_seconds
        )
        configured_max = settings.api.chat_history_max_messages_per_session
        if max_messages_per_session is None:
            self.max_messages_per_session = max(1, int(configured_max))
        else:
            self.max_messages_per_session = max(1, int(max_messages_per_session))

    @contextmanager
    def turn(self, session_id: str) -> Iterator[None]:
        """Reject overlapping operations; never hold an I/O lock across a turn."""
        with self._turn_lock:
            if session_id in self._active_turns:
                raise AppError(
                    "A request is already active for this chat session",
                    status_code=409,
                    code="chat_session_busy",
                )
            self._active_turns.add(session_id)
        try:
            yield
        finally:
            with self._turn_lock:
                self._active_turns.remove(session_id)

    def _load_history_unlocked(self) -> dict[str, dict[str, Any]]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw_history = json.load(handle)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Corrupt chat history file %s: %s — backing up and resetting", self.path, exc
            )
            self._backup_corrupt_file()
            return {}
        except FileNotFoundError:
            return {}
        except OSError as exc:
            raise StorageError("Failed to read chat history") from exc
        if not isinstance(raw_history, dict):
            return {}
        return self._normalize_history(raw_history)

    def _backup_corrupt_file(self) -> None:
        try:
            backup_path = self.path.with_suffix(f"{self.path.suffix}.corrupt.{int(time.time())}")
            shutil.copy2(self.path, backup_path)
            logger.info("Corrupt file backed up to %s", backup_path)
        except OSError:
            logger.warning("Failed to back up corrupt file %s", self.path, exc_info=True)

    def _save_history_unlocked(self, history: dict[str, dict[str, Any]]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(history, handle, indent=2)
            temp_path.replace(self.path)
        except OSError as exc:
            raise StorageError("Failed to write chat history") from exc

    def get_history(self, session_id: str) -> list[dict]:
        with self._lock:
            history = self._load_history_unlocked()
            history, changed = self._prune_expired_sessions(history)
            if changed:
                self._save_history_unlocked(history)
            session = history.get(session_id)
            if not session:
                return []
            return list(session.get("messages", []))

    def save_message(self, session_id: str, role: str, content: str) -> None:
        self._save_messages(session_id, [(role, content)])

    def save_turn(self, session_id: str, message: str, response: str) -> None:
        """Publish a complete generated pair in one replacement, never two writes."""
        if self.max_messages_per_session < 2:
            raise StorageError("Chat history capacity must allow a complete turn")
        self._save_messages(session_id, [("user", message), ("assistant", response)])

    def _save_messages(self, session_id: str, messages: list[tuple[str, str]]) -> None:
        with self._lock:
            history = self._load_history_unlocked()
            history, _ = self._prune_expired_sessions(history)
            now = int(time.time())
            session = history.setdefault(
                session_id,
                {
                    "version": SESSION_SCHEMA_VERSION,
                    "updated_at": now,
                    "messages": [],
                },
            )
            session["version"] = SESSION_SCHEMA_VERSION
            session["updated_at"] = now
            session.setdefault("messages", []).extend(
                {"role": role, "content": content, "timestamp": now * 1000}
                for role, content in messages
            )
            self._truncate_session_messages(session)
            self._save_history_unlocked(history)

    def clear_history(self, session_id: str) -> None:
        with self.turn(session_id), self._lock:
            history = self._load_history_unlocked()
            history.pop(session_id, None)
            self._save_history_unlocked(history)

    def _normalize_history(self, raw_history: dict[str, Any]) -> dict[str, dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        now = int(time.time())
        for session_id, raw_session in raw_history.items():
            session = self._normalize_session(raw_session, now)
            if session:
                normalized[session_id] = session
        return normalized

    def _normalize_session(
        self, raw_session: Any, default_updated_at: int
    ) -> dict[str, Any] | None:
        if isinstance(raw_session, list):
            messages = [message for message in raw_session if isinstance(message, dict)]
            updated_at = self._derive_updated_at(messages, default_updated_at)
            return {
                "version": SESSION_SCHEMA_VERSION,
                "updated_at": updated_at,
                "messages": messages,
            }

        if not isinstance(raw_session, dict):
            return None

        raw_messages = raw_session.get("messages", [])
        if not isinstance(raw_messages, list):
            raw_messages = []
        messages = [message for message in raw_messages if isinstance(message, dict)]
        normalized_updated_at = self._coerce_updated_at(raw_session.get("updated_at"))
        if normalized_updated_at is None:
            normalized_updated_at = self._derive_updated_at(messages, default_updated_at)
        return {
            "version": SESSION_SCHEMA_VERSION,
            "updated_at": normalized_updated_at,
            "messages": messages,
        }

    @staticmethod
    def _coerce_updated_at(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return int(value)
        return None

    def _derive_updated_at(self, messages: list[dict[str, Any]], fallback: int) -> int:
        latest = fallback
        for message in messages:
            timestamp = message.get("timestamp")
            if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
                candidate = int(timestamp / 1000) if timestamp > 10_000_000_000 else int(timestamp)
                latest = max(latest, candidate)
        return latest

    def _prune_expired_sessions(
        self,
        history: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], bool]:
        if self.ttl_seconds <= 0:
            return history, False

        now = int(time.time())
        cutoff = now - self.ttl_seconds
        pruned = {
            session_id: session
            for session_id, session in history.items()
            if int(session.get("updated_at", now)) >= cutoff
        }
        return pruned, len(pruned) != len(history)

    def _truncate_session_messages(self, session: dict[str, Any]) -> None:
        messages = session.get("messages")
        if not isinstance(messages, list):
            session["messages"] = []
            return
        if len(messages) <= self.max_messages_per_session:
            return
        session["messages"] = messages[-self.max_messages_per_session :]
