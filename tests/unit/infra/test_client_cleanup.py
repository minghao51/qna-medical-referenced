"""SDK transport cleanup without constructing SDK clients or using the network."""

import threading
from types import SimpleNamespace

import pytest

from src.infra.llm.gemini_client import GeminiClient
from src.infra.llm.qwen_client import QwenClient


@pytest.mark.asyncio
@pytest.mark.parametrize("client_class", [QwenClient, GeminiClient])
@pytest.mark.parametrize("failure", [None, "async", "sync"])
async def test_client_cleanup_closes_both_transports_on_correct_threads(client_class, failure):
    calls = []
    loop_thread = threading.get_ident()

    async def close_async():
        calls.append(("async", threading.get_ident()))
        if failure == "async":
            raise RuntimeError("Synthetic async close failure")

    def close_sync():
        calls.append(("sync", threading.get_ident()))
        if failure == "sync":
            raise RuntimeError("Synthetic sync close failure")

    client = client_class.__new__(client_class)
    if client_class is QwenClient:
        client.client = SimpleNamespace(close=close_sync)
        client.async_client = SimpleNamespace(close=close_async)
    else:
        client.client = SimpleNamespace(close=close_sync, aio=SimpleNamespace(aclose=close_async))
    if failure:
        with pytest.raises(RuntimeError, match=f"Synthetic {failure} close failure"):
            await client.aclose()
    else:
        await client.aclose()
    assert [name for name, _ in calls] == ["async", "sync"]
    assert calls[0][1] == loop_thread
    assert calls[1][1] != loop_thread
