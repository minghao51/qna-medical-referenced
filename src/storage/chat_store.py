import json
import os
from pathlib import Path
from typing import Optional

CHAT_HISTORY_FILE = Path("data/chat_history.json")


def _load_history() -> dict:
    if not CHAT_HISTORY_FILE.exists():
        return {}
    try:
        with open(CHAT_HISTORY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_history(history: dict) -> None:
    CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHAT_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def get_history(session_id: str) -> list[dict]:
    history = _load_history()
    return history.get(session_id, [])


def save_message(session_id: str, role: str, content: str) -> None:
    history = _load_history()
    if session_id not in history:
        history[session_id] = []
    history[session_id].append({
        "role": role,
        "content": content
    })
    _save_history(history)


def clear_history(session_id: str) -> None:
    history = _load_history()
    if session_id in history:
        del history[session_id]
        _save_history(history)
