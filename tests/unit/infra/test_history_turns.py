"""Atomic completed turns and same-instance, process-local admission."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path

import pytest

from src.core.exceptions import AppError, StorageError
from src.infra.storage.file_chat_history_store import FileChatHistoryStore


@pytest.mark.parametrize("outcome", ["success", "error"])
def test_turn_rejects_same_session_and_clear_but_not_other_sessions(tmp_path, outcome):
    store = FileChatHistoryStore(tmp_path / "history.json")
    with pytest.raises(RuntimeError) if outcome == "error" else nullcontext():
        with store.turn("synthetic-one"):
            with pytest.raises(AppError) as busy:
                with store.turn("synthetic-one"):
                    pytest.fail("Overlapping turn admitted")
            assert busy.value.code == "chat_session_busy"
            assert busy.value.status_code == 409
            with pytest.raises(AppError):
                store.clear_history("synthetic-one")
            with store.turn("synthetic-two"):
                store.save_turn("synthetic-two", "question", "answer")
            assert store.get_history("synthetic-one") == []
            if outcome == "error":
                raise RuntimeError("synthetic failure")
    with store.turn("synthetic-one"):
        pass
    store.clear_history("synthetic-two")
    assert store.get_history("synthetic-two") == []


def test_turn_admission_is_shared_across_threads(tmp_path):
    store = FileChatHistoryStore(tmp_path / "history.json")
    with store.turn("synthetic"):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(store.clear_history, "synthetic")
            with pytest.raises(AppError):
                future.result(timeout=2)


@pytest.mark.parametrize("limit", [2, 3, 40])
def test_save_turn_publishes_once_and_retains_complete_new_pair(tmp_path, monkeypatch, limit):
    store = FileChatHistoryStore(tmp_path / "history.json", max_messages_per_session=limit)
    store.save_message("synthetic", "user", "older")
    publications = []
    original = store._save_history_unlocked

    def publish(history):
        publications.append(json.loads(json.dumps(history)))
        original(history)

    monkeypatch.setattr(store, "_save_history_unlocked", publish)
    with store.turn("synthetic"):
        store.save_turn("synthetic", "question", "answer")
    assert len(publications) == 1
    history = store.get_history("synthetic")
    assert len(history) <= limit
    assert [(m["role"], m["content"]) for m in history[-2:]] == [
        ("user", "question"),
        ("assistant", "answer"),
    ]
    assert history[-1]["timestamp"] == history[-2]["timestamp"]
    assert publications[0]["synthetic"]["version"] == 2


def test_save_turn_rejects_one_message_capacity_without_modifying_file(tmp_path):
    store = FileChatHistoryStore(tmp_path / "history.json", max_messages_per_session=1)
    store.save_message("synthetic", "user", "older")
    before = store.path.read_bytes()
    with pytest.raises(StorageError):
        store.save_turn("synthetic", "question", "answer")
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("failure", ["read", "serialize", "replace"])
def test_failed_atomic_turn_preserves_existing_file(tmp_path, monkeypatch, failure):
    store = FileChatHistoryStore(tmp_path / "history.json")
    store.save_message("synthetic", "user", "older")
    before = store.path.read_bytes()
    with monkeypatch.context() as patch:
        if failure == "read":
            original = Path.open

            def fail_read(path, *args, **kwargs):
                if path == store.path:
                    raise OSError("forbidden-storage-detail")
                return original(path, *args, **kwargs)

            patch.setattr(Path, "open", fail_read)
        elif failure == "serialize":

            def fail_dump(*args, **kwargs):
                raise OSError("forbidden-storage-detail")

            patch.setattr(json, "dump", fail_dump)
        else:

            def fail_replace(*args, **kwargs):
                raise OSError("forbidden-storage-detail")

            patch.setattr(Path, "replace", fail_replace)
        with pytest.raises(StorageError) as error:
            with store.turn("synthetic"):
                store.save_turn("synthetic", "question", "answer")
        assert "forbidden-storage-detail" not in error.value.message
    assert store.path.read_bytes() == before
    with store.turn("synthetic"):
        store.save_turn("synthetic", "retry", "complete")
    assert len(store.get_history("synthetic")) == 3


def test_atomic_turn_preserves_legacy_loading_and_ttl(tmp_path, monkeypatch):
    monkeypatch.setattr("src.infra.storage.file_chat_history_store.time.time", lambda: 1000)
    path = tmp_path / "history.json"
    path.write_text(
        json.dumps(
            {
                "legacy": [{"role": "user", "content": "older"}],
                "expired": {"version": 2, "updated_at": 900, "messages": []},
            }
        )
    )
    store = FileChatHistoryStore(path, ttl_seconds=60)
    store.save_turn("legacy", "question", "answer")
    payload = json.loads(path.read_text())
    assert set(payload) == {"legacy"}
    assert payload["legacy"]["version"] == 2
    assert len(payload["legacy"]["messages"]) == 3


def test_atomic_turns_from_distinct_sessions_preserve_all_pairs(tmp_path):
    store = FileChatHistoryStore(tmp_path / "history.json")
    barrier = threading.Barrier(4)

    def save(index):
        session = f"synthetic-{index}"
        with store.turn(session):
            barrier.wait(timeout=2)
            store.save_turn(session, "question", "answer")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(save, range(4)))
    assert all(len(store.get_history(f"synthetic-{i}")) == 2 for i in range(4))


@pytest.mark.parametrize("fail_clear", [False, True])
def test_clear_owns_session_until_its_write_settles(tmp_path, monkeypatch, fail_clear):
    store = FileChatHistoryStore(tmp_path / "history.json")
    store.save_turn("synthetic", "question", "answer")
    entered, release = threading.Event(), threading.Event()
    original = store._save_history_unlocked

    def blocked_save(history):
        entered.set()
        if not release.wait(3):
            raise TimeoutError("test failed to release clear")
        if fail_clear:
            raise StorageError("synthetic clear failure")
        original(history)

    monkeypatch.setattr(store, "_save_history_unlocked", blocked_save)
    with ThreadPoolExecutor(max_workers=1) as pool:
        clear = pool.submit(store.clear_history, "synthetic")
        try:
            assert entered.wait(2)
            with pytest.raises(AppError):
                with store.turn("synthetic"):
                    pytest.fail("Turn overlapped clear")
            with store.turn("other"):
                pass
        finally:
            release.set()
            if fail_clear:
                with pytest.raises(StorageError):
                    clear.result(timeout=2)
            else:
                clear.result(timeout=2)
    assert len(store.get_history("synthetic")) == (2 if fail_clear else 0)
    with store.turn("synthetic"):
        pass


def test_readers_see_old_file_until_entire_turn_is_published(tmp_path, monkeypatch):
    store = FileChatHistoryStore(tmp_path / "history.json")
    store.save_turn("synthetic", "older question", "older answer")
    before = store.path.read_bytes()
    entered, release = threading.Event(), threading.Event()
    original = json.dump

    def blocked_dump(history, handle, **kwargs):
        handle.write('{"incomplete":')
        handle.flush()
        entered.set()
        if not release.wait(3):
            raise TimeoutError("test failed to release serialization")
        handle.seek(0)
        handle.truncate()
        return original(history, handle, **kwargs)

    monkeypatch.setattr(json, "dump", blocked_dump)
    with ThreadPoolExecutor(max_workers=1) as pool:
        write = pool.submit(store.save_turn, "synthetic", "question", "answer")
        try:
            assert entered.wait(2)
            # A direct external reader is not protected by the instance lock.
            assert store.path.read_bytes() == before
        finally:
            release.set()
            write.result(timeout=2)
    payload = json.loads(store.path.read_text())
    assert len(payload["synthetic"]["messages"]) == 4
