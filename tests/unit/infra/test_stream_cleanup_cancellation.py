"""Owned public close completion under repeated/level cancellation, not HTTP release."""

import asyncio
import threading

import anyio
import pytest

from tests.unit.infra import test_stream_contract

provider = test_stream_contract.provider


class BlockedCloseStream:
    def __init__(self, *, block_read=True, close_error=False):
        self.block_read = block_read
        self.close_error = close_error
        self.read_started = asyncio.Event()
        self.close_started = asyncio.Event()
        self.release_close = asyncio.Event()
        self.closed = asyncio.Event()
        self.close_calls = 0
        self.close_loops = []
        self.close_threads = []

    def __aiter__(self):
        return self

    async def __anext__(self):
        self.read_started.set()
        if self.block_read:
            await asyncio.Event().wait()
        raise StopAsyncIteration

    async def aclose(self):
        self.close_calls += 1
        self.close_loops.append(asyncio.get_running_loop())
        self.close_threads.append(threading.get_ident())
        self.close_started.set()
        await self.release_close.wait()
        self.closed.set()
        if self.close_error:
            raise RuntimeError("forbidden-close-detail")

    close = aclose


async def consume(client):
    return [token async for token in client.a_generate_stream("synthetic prompt")]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["read", "close"])
@pytest.mark.parametrize("close_error", [False, True])
async def test_repeated_cancellation_drains_one_owned_close_before_propagating(
    provider, stage, close_error, monkeypatch, caplog
):
    body = BlockedCloseStream(block_read=stage == "read", close_error=close_error)
    provider.create.return_value = body
    loop = asyncio.get_running_loop()
    thread = threading.get_ident()
    shields = []
    native_shield = asyncio.shield

    def shield(future):
        shields.append(future)
        return native_shield(future)

    monkeypatch.setattr(asyncio, "shield", shield)
    task = asyncio.create_task(consume(provider.client))
    try:
        if stage == "read":
            await asyncio.wait_for(body.read_started.wait(), 2)
            task.cancel()
        await asyncio.wait_for(body.close_started.wait(), 2)
        task.cancel()
        for _ in range(3):
            await asyncio.sleep(0)
        assert not task.done()
        task.cancel()
        for _ in range(3):
            await asyncio.sleep(0)
        assert not task.done()
        assert not body.closed.is_set()
        body.release_close.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert body.closed.is_set()
        assert body.close_calls == 1
        assert body.close_loops == [loop]
        assert body.close_threads == [thread]
        assert provider.create.await_count == 1
        assert 1 <= len(shields) <= 6
        assert "forbidden-close-detail" not in caplog.text
    finally:
        body.release_close.set()
        if not task.done():
            task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("close_error", [False, True])
@pytest.mark.parametrize("stage", ["read", "close"])
async def test_anyio_level_cancellation_drains_close_without_retry_or_error_masking(
    provider, close_error, stage, caplog
):
    body = BlockedCloseStream(block_read=stage == "read", close_error=close_error)
    provider.create.return_value = body
    done = asyncio.Event()
    cancelled = []

    async def run():
        try:
            await consume(provider.client)
        except asyncio.CancelledError:
            cancelled.append(True)
        finally:
            done.set()

    async with anyio.create_task_group() as group:
        group.start_soon(run)
        started = body.read_started if stage == "read" else body.close_started
        await asyncio.wait_for(started.wait(), 2)
        group.cancel_scope.cancel()
        with anyio.CancelScope(shield=True):
            try:
                await asyncio.wait_for(body.close_started.wait(), 2)
                for _ in range(3):
                    await asyncio.sleep(0)
                assert not done.is_set()
                assert not body.closed.is_set()
            finally:
                body.release_close.set()
            await asyncio.wait_for(done.wait(), 2)
    assert cancelled == [True]
    assert body.closed.is_set()
    assert body.close_calls == 1
    assert provider.create.await_count == 1
    assert "forbidden-close-detail" not in caplog.text


@pytest.mark.asyncio
async def test_public_close_cancellation_is_not_swallowed_or_retried(provider):
    class Stream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

        async def aclose(self):
            raise asyncio.CancelledError

        close = aclose

    provider.create.return_value = Stream()
    with pytest.raises(asyncio.CancelledError):
        await consume(provider.client)
    assert provider.create.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("early_close", [False, True])
async def test_native_async_generator_aclose_awaitable_is_owned(provider, early_close):
    closed = []

    async def body():
        try:
            yield provider.chunk("prefix")
        finally:
            await asyncio.sleep(0)
            closed.append(True)

    sdk_body = body()
    if provider.module.__name__.endswith("qwen_client"):

        class QwenStream:
            def __aiter__(self):
                return sdk_body

            def close(self):
                return sdk_body.aclose()

        provider.create.return_value = QwenStream()
    else:
        provider.create.return_value = sdk_body
    stream = provider.client.a_generate_stream("synthetic prompt")
    try:
        assert await anext(stream) == "prefix"
        if not early_close:
            with pytest.raises(StopAsyncIteration):
                await anext(stream)
    finally:
        await stream.aclose()
    assert closed == [True]
    assert provider.create.await_count == 1
