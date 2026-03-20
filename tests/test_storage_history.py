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
    assert payload["session-1"]["version"] == 2
    assert len(payload["session-1"]["messages"]) == 25


def test_file_chat_history_store_prunes_expired_sessions(tmp_path, monkeypatch):
    current_time = 1_700_000_000
    monkeypatch.setattr(
        "src.infra.storage.file_chat_history_store.time.time",
        lambda: current_time,
    )
    store = FileChatHistoryStore(tmp_path / "history.json", ttl_seconds=60)
    store.save_message("fresh-session", "user", "hello")

    stale_payload = {
        "stale-session": {
            "version": 2,
            "updated_at": current_time - 61,
            "messages": [
                {"role": "user", "content": "expired", "timestamp": (current_time - 61) * 1000}
            ],
        },
        "fresh-session": json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))[
            "fresh-session"
        ],
    }
    (tmp_path / "history.json").write_text(json.dumps(stale_payload), encoding="utf-8")

    history = store.get_history("fresh-session")
    payload = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))

    assert history == payload["fresh-session"]["messages"]
    assert "stale-session" not in payload


def test_file_chat_history_store_migrates_legacy_format(tmp_path, monkeypatch):
    current_time = 1_700_000_000
    monkeypatch.setattr(
        "src.infra.storage.file_chat_history_store.time.time",
        lambda: current_time,
    )
    legacy_payload = {
        "legacy-session": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
    }
    path = tmp_path / "history.json"
    path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    store = FileChatHistoryStore(path, ttl_seconds=3600)
    history = store.get_history("legacy-session")
    store.save_message("legacy-session", "user", "follow-up")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert history == legacy_payload["legacy-session"]
    assert payload["legacy-session"]["version"] == 2
    assert len(payload["legacy-session"]["messages"]) == 3
