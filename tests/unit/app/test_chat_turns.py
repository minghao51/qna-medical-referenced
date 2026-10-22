"""Usecase admission and owned atomic-commit worker contracts, offline only."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import anyio
import pytest

from src.core.exceptions import AppError, UpstreamServiceError
from src.infra.storage.file_chat_history_store import FileChatHistoryStore
from src.usecases import chat


@pytest.fixture
def leaves(monkeypatch, tmp_path):
    calls = []

    def retrieve(query, **kwargs):
        calls.append(query)
        return "synthetic evidence", []

    async def retrieve_async(query, **kwargs):
        context, sources = retrieve(query, **kwargs)
        return context, sources, None

    monkeypatch.setattr(chat, "retrieve_context", retrieve)
    monkeypatch.setattr(chat, "retrieve_context_with_trace_async", retrieve_async)
    store = FileChatHistoryStore(tmp_path / "history.json")

    class Client:
        model = "synthetic-model"

        def generate(self, *, prompt, context):
            return "answer"

        async def a_generate_stream(self, *, prompt, context):
            yield "answer"

    return SimpleNamespace(store=store, client=Client(), calls=calls)


def _kwargs(leaves, session="synthetic"):
    return {
        "llm_client": leaves.client,
        "history_store": leaves.store,
        "message": "question",
        "session_id": session,
        "top_k": 2,
    }


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.asyncio
async def test_usecases_commit_only_through_atomic_turn_method(leaves, monkeypatch, streaming):
    def no_message_writes(*args):
        pytest.fail("Usecase attempted individual message persistence")

    monkeypatch.setattr(leaves.store, "save_message", no_message_writes)
    if streaming:
        events = [event async for event in chat.stream_chat_message(**_kwargs(leaves))]
        assert events[-1][1]["done"]
    else:
        assert chat.process_chat_message(**_kwargs(leaves))["response"] == "answer"
    assert [m["role"] for m in leaves.store.get_history("synthetic")] == ["user", "assistant"]
    with leaves.store.turn("synthetic"):
        pass


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.asyncio
async def test_busy_usecase_skips_history_retrieval_and_generation(leaves, monkeypatch, streaming):
    def no_history(*args):
        pytest.fail("Busy turn read history")

    monkeypatch.setattr(leaves.store, "get_history", no_history)
    with leaves.store.turn("synthetic"):
        with pytest.raises(AppError) as busy:
            if streaming:
                await anext(chat.stream_chat_message(**_kwargs(leaves)))
            else:
                chat.process_chat_message(**_kwargs(leaves))
        assert busy.value.code == "chat_session_busy"
    assert leaves.calls == []


@pytest.mark.asyncio
async def test_active_stream_rejects_sync_same_session_but_allows_other_session(leaves):
    generator = chat.stream_chat_message(**_kwargs(leaves))
    try:
        assert (await anext(generator))[0] == "answer"
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(AppError):
                pool.submit(chat.process_chat_message, **_kwargs(leaves)).result(timeout=2)
            result = pool.submit(chat.process_chat_message, **_kwargs(leaves, "other")).result(
                timeout=2
            )
            assert result["response"] == "answer"
        assert leaves.calls == ["question", "question"]
    finally:
        await generator.aclose()
    assert leaves.store.get_history("synthetic") == []
    assert len(leaves.store.get_history("other")) == 2
    with leaves.store.turn("synthetic"):
        pass


@pytest.mark.asyncio
async def test_active_sync_turn_rejects_stream_same_session(leaves, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def generation(**kwargs):
        entered.set()
        if not release.wait(3):
            raise TimeoutError("test failed to release generation")
        return "answer"

    monkeypatch.setattr(leaves.client, "generate", generation)
    task = asyncio.create_task(asyncio.to_thread(chat.process_chat_message, **_kwargs(leaves)))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        with pytest.raises(AppError):
            await anext(chat.stream_chat_message(**_kwargs(leaves)))
    finally:
        release.set()
        await task
    assert len(leaves.store.get_history("synthetic")) == 2


@pytest.mark.parametrize("failure", ["generation", "persistence"])
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.asyncio
async def test_failures_release_guard_and_do_not_publish_partial_turn(
    leaves, monkeypatch, failure, streaming
):
    leaves.store.save_message("synthetic", "user", "older")
    before = leaves.store.path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("forbidden-failure-detail")

    async def failing_stream(**kwargs):
        yield "partial"
        fail()

    terminal = None
    with monkeypatch.context() as patch:
        if failure == "generation":
            patch.setattr(leaves.client, "generate", fail)
            patch.setattr(leaves.client, "a_generate_stream", failing_stream)
        else:
            patch.setattr(leaves.store, "_save_history_unlocked", fail)
        with pytest.raises((UpstreamServiceError, OSError)):
            if streaming:
                generator = chat.stream_chat_message(**_kwargs(leaves))
                try:
                    async for _, metadata in generator:
                        if metadata["done"]:
                            terminal = metadata
                            # Ownership must already be released before a terminal.
                            with leaves.store.turn("synthetic"):
                                pass
                finally:
                    await generator.aclose()
            else:
                chat.process_chat_message(**_kwargs(leaves))
    if streaming:
        assert terminal is not None
    assert leaves.store.path.read_bytes() == before
    with leaves.store.turn("synthetic"):
        pass


@pytest.mark.parametrize("fail_commit", [False, True])
@pytest.mark.parametrize("cancellation", ["asyncio", "anyio"])
@pytest.mark.asyncio
async def test_cancelled_commit_drains_before_releasing_session(
    leaves, monkeypatch, fail_commit, cancellation
):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = leaves.store._save_history_unlocked
    store_thread = []

    def blocked_save(history):
        store_thread.append(threading.get_ident())
        entered.set()
        try:
            if not release.wait(3):
                raise TimeoutError("test failed to release write")
            if fail_commit:
                raise OSError("forbidden-persistence-detail")
            original(history)
        finally:
            finished.set()

    monkeypatch.setattr(leaves.store, "_save_history_unlocked", blocked_save)
    events = []
    shield_calls = []
    native_shield = asyncio.shield

    def tracked_shield(task):
        if isinstance(task, asyncio.Task) and task.get_coro().__qualname__ == "to_thread":
            shield_calls.append(task)
        return native_shield(task)

    monkeypatch.setattr(asyncio, "shield", tracked_shield)

    async def consume():
        async for event in chat.stream_chat_message(**_kwargs(leaves)):
            events.append(event)

    async def assert_busy():
        assert not finished.is_set()
        with pytest.raises(AppError):
            with leaves.store.turn("synthetic"):
                pytest.fail("Session released while commit worker still running")
        with pytest.raises(AppError):
            leaves.store.clear_history("synthetic")

    if cancellation == "asyncio":
        task = asyncio.create_task(consume())
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            await assert_busy()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
    else:
        cancelled = asyncio.Event()

        async def cancelled_consumer():
            try:
                await consume()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        try:
            async with anyio.create_task_group() as group:
                group.start_soon(cancelled_consumer)
                assert await asyncio.to_thread(entered.wait, 2)
                group.cancel_scope.cancel()
                with anyio.CancelScope(shield=True):
                    await asyncio.sleep(0.01)
                    assert not cancelled.is_set()
                    await assert_busy()
                    release.set()
        finally:
            release.set()
        assert cancelled.is_set()
    assert finished.is_set()
    # Persistent AnyIO cancellation must not repeatedly poll a blocked commit.
    assert 1 <= len(shield_calls) <= 4
    assert len(store_thread) == 1
    assert store_thread[0] != threading.get_ident()
    assert events == [("answer", {"done": False})]
    assert len(leaves.store.get_history("synthetic")) == (0 if fail_commit else 2)
    with leaves.store.turn("synthetic"):
        pass


@pytest.mark.asyncio
async def test_cancellation_before_commit_checkpoint_discards_turn(leaves, monkeypatch):
    async def cancelled_generation(**kwargs):
        yield "answer"
        asyncio.current_task().cancel()

    monkeypatch.setattr(leaves.client, "a_generate_stream", cancelled_generation)

    async def consume():
        return [event async for event in chat.stream_chat_message(**_kwargs(leaves))]

    task = asyncio.create_task(consume())
    with pytest.raises(asyncio.CancelledError):
        await task
    assert leaves.store.get_history("synthetic") == []
    with leaves.store.turn("synthetic"):
        pass


@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.asyncio
async def test_guard_is_released_while_terminal_is_suspended(leaves, monkeypatch, failure):
    if failure:

        async def generation(**kwargs):
            yield "prefix"
            raise RuntimeError("synthetic generation failure")

        monkeypatch.setattr(leaves.client, "a_generate_stream", generation)
    generator = chat.stream_chat_message(**_kwargs(leaves))
    try:
        assert (await anext(generator))[1] == {"done": False}
        terminal = (await anext(generator))[1]
        assert terminal["done"]
        assert bool(terminal.get("error")) is failure
        with leaves.store.turn("synthetic"):
            pass
        if failure:
            with pytest.raises(UpstreamServiceError):
                await anext(generator)
        else:
            with pytest.raises(StopAsyncIteration):
                await anext(generator)
    finally:
        await generator.aclose()


@pytest.mark.parametrize("phase", ["history", "retrieval"])
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.asyncio
async def test_pre_generation_failure_releases_admission(leaves, monkeypatch, phase, streaming):
    def fail(*args, **kwargs):
        raise OSError("synthetic pre-generation failure")

    async def fail_async(*args, **kwargs):
        fail()

    if phase == "history":
        monkeypatch.setattr(leaves.store, "get_history", fail)
    else:
        monkeypatch.setattr(chat, "retrieve_context", fail)
        monkeypatch.setattr(chat, "retrieve_context_with_trace_async", fail_async)
    with pytest.raises(OSError):
        if streaming:
            await anext(chat.stream_chat_message(**_kwargs(leaves)))
        else:
            chat.process_chat_message(**_kwargs(leaves))
    with leaves.store.turn("synthetic"):
        pass
