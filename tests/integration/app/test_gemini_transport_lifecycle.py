"""Application-owned HTTPX cleanup after real startup/body failures and cancellation."""

import asyncio

import pytest

from tests.integration.app import test_lifespan
from tests.unit.infra import test_gemini_httpx_transport

lifecycle = test_lifespan.lifecycle
native_constructor = test_gemini_httpx_transport.native_constructor


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["history", "store", "body"])
@pytest.mark.parametrize("cleanup_error", [False, True])
async def test_constructed_httpx_pool_is_closed_after_app_failure(
    lifecycle, native_constructor, failure, cleanup_error, monkeypatch, caplog
):
    from src.infra.llm.gemini_client import GeminiClient

    control = native_constructor
    original_error = RuntimeError("synthetic lifespan body failure")
    if failure != "body":
        lifecycle.failure = failure

    def build():
        client = GeminiClient()
        if cleanup_error:

            async def broken_close():
                raise RuntimeError("forbidden-sdk-cleanup-detail")

            monkeypatch.setattr(client.client.aio, "aclose", broken_close)
        return client

    monkeypatch.setattr(lifecycle.factory, "get_client", build)
    app = lifecycle.factory.create_app()
    with pytest.raises(RuntimeError) as raised:
        async with app.router.lifespan_context(app):
            assert failure == "body"
            raise original_error
    if failure == "body":
        assert raised.value is original_error
    else:
        assert str(raised.value) == f"Synthetic {failure} failure"
    assert len(control.created) == 1
    assert control.created[0].is_closed
    assert len(control.transport_closes) == 1
    assert app.state.llm_client is None
    assert app.state.chat_history_store is None
    assert app.state.vector_store is None
    assert lifecycle.state.vector_store_initialized is False
    control.aiohttp_request.assert_not_called()
    assert control.calls == []
    assert "forbidden-sdk-cleanup-detail" not in caplog.text


@pytest.mark.asyncio
async def test_constructed_httpx_pool_lives_until_normal_app_shutdown(
    lifecycle, native_constructor, monkeypatch
):
    from src.infra.llm.gemini_client import GeminiClient

    control = native_constructor
    monkeypatch.setattr(lifecycle.factory, "get_client", GeminiClient)
    app = lifecycle.factory.create_app()
    async with app.router.lifespan_context(app):
        assert len(control.created) == 1
        assert not control.created[0].is_closed
        assert control.transport_closes == []
        assert await app.state.llm_client.a_generate("synthetic prompt") == "synthetic answer"
        assert not control.created[0].is_closed
    assert control.created[0].is_closed
    assert len(control.transport_closes) == 1
    control.aiohttp_request.assert_not_called()


@pytest.mark.asyncio
async def test_app_owned_cleanup_drains_httpx_close_through_repeated_cancellation(
    lifecycle, native_constructor, monkeypatch
):
    from src.infra.llm.gemini_client import GeminiClient

    control = native_constructor
    close_started, release = asyncio.Event(), asyncio.Event()
    body_entered, finish = asyncio.Event(), asyncio.Event()

    def build():
        client = GeminiClient()
        owned = control.created[0]
        original_close = owned.aclose

        async def blocked_close():
            close_started.set()
            await release.wait()
            await original_close()

        monkeypatch.setattr(owned, "aclose", blocked_close)
        return client

    monkeypatch.setattr(lifecycle.factory, "get_client", build)
    app = lifecycle.factory.create_app()

    async def run():
        async with app.router.lifespan_context(app):
            body_entered.set()
            await finish.wait()

    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(body_entered.wait(), 2)
        finish.set()
        await asyncio.wait_for(close_started.wait(), 2)
        task.cancel()
        for _ in range(3):
            await asyncio.sleep(0)
        task.cancel()
        for _ in range(3):
            await asyncio.sleep(0)
        assert not task.done()
        assert not control.created[0].is_closed
        assert app.state.llm_client is not None
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert control.created[0].is_closed
        assert len(control.transport_closes) == 1
        assert app.state.llm_client is None
        assert app.state.chat_history_store is None
        assert app.state.vector_store is None
    finally:
        finish.set()
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)
