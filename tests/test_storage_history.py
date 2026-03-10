import json
from concurrent.futures import ThreadPoolExecutor

from src.infra.storage.file_chat_history_store import FileChatHistoryStore


def test_file_chat_history_store_supports_concurrent_writes(tmp_path):
    store = FileChatHistoryStore(tmp_path / "history.json")

    def write_message(index: int):
        store.save_message("session-1", "user", f"message-{index}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_message, range(25)))

    history = store.get_history("session-1")
    payload = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))

    assert len(history) == 25
    assert len(payload["session-1"]) == 25
