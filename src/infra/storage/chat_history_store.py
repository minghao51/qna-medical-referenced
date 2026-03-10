"""Compatibility wrapper for the default chat history store."""

from src.infra.storage.file_chat_history_store import FileChatHistoryStore

chat_history_store = FileChatHistoryStore()

get_history = chat_history_store.get_history
save_message = chat_history_store.save_message
clear_history = chat_history_store.clear_history

__all__ = [
    "chat_history_store",
    "get_history",
    "save_message",
    "clear_history",
    "FileChatHistoryStore",
]
