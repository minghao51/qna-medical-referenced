"""Request ownership remains held until admitted synchronous workers settle."""

import asyncio
import threading

import anyio
import pytest

from src.core.exceptions import AppError
from src.infra.storage.file_chat_history_store import FileChatHistoryStore
from src.usecases import chat


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellation", ["asyncio", "anyio"])
async def test_cancelled_history_read_keeps_session_until_worker_finishes(
    monkeypatch, tmp_path, cancellation
):
    store = FileChatHistoryStore(tmp_path / "history.json")
    entered, release = threading.Event(), threading.Event()
    retrieved = []
    original_get_history = store.get_history

    def blocked_history(session_id):
        entered.set()
        if not release.wait(timeout=5):
            raise TimeoutError("Test did not release history read")
        return original_get_history(session_id)

    async def unexpected_retrieval(*args, **kwargs):
        retrieved.append(True)
        raise AssertionError("Cancellation must stop downstream retrieval")

    class Client:
        async def a_generate_stream(self, **kwargs):
            pytest.fail("Cancellation must stop downstream generation")
            yield "unreachable"

    monkeypatch.setattr(store, "get_history", blocked_history)
    monkeypatch.setattr(chat, "retrieve_context_with_trace_async", unexpected_retrieval)
    generator = chat.stream_chat_message(
        llm_client=Client(),
        history_store=store,
        message="synthetic question",
        session_id="synthetic-session",
    )

    def assert_session_busy():
        with pytest.raises(AppError) as busy:
            with store.turn("synthetic-session"):
                pytest.fail("Session admission released before history worker settled")
        assert busy.value.code == "chat_session_busy"

    try:
        if cancellation == "asyncio":
            task = asyncio.create_task(anext(generator))
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            assert not task.done()
            assert_session_busy()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            cancelled = asyncio.Event()

            async def consume():
                try:
                    await anext(generator)
                except asyncio.CancelledError:
                    cancelled.set()
                    raise

            async with anyio.create_task_group() as group:
                group.start_soon(consume)
                assert await asyncio.to_thread(entered.wait, 2)
                group.cancel_scope.cancel()
                with anyio.CancelScope(shield=True):
                    await asyncio.sleep(0)
                    assert not cancelled.is_set()
                    assert_session_busy()
                    release.set()
            assert cancelled.is_set()
        assert retrieved == []
        assert store.get_history("synthetic-session") == []
    finally:
        release.set()
        await generator.aclose()
    with store.turn("synthetic-session"):
        pass
