"""Enrichment workers inherit safe usage capture and drain on cancellation."""

import asyncio
import json
import threading

import pytest

from src.infra.usage import capture_usage, usage_call
from src.ingestion.steps.enrich_chunks import _enrich_chunk_batch, enrich_chunks


class _ReportingClient:
    def generate(self, prompt: str, context: str) -> str:
        with usage_call(provider="openai") as call:
            assert call is not None
            call.record_response(
                {
                    "usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 2,
                        "total_tokens": 7,
                    }
                }
            )
        return json.dumps({"keywords": ["synthetic-term"], "summary": "Synthetic summary."})


@pytest.mark.asyncio
async def test_worker_inherits_capture_and_uses_enrichment_role():
    with capture_usage() as accumulator:
        results = await enrich_chunks(
            [{"id": "chunk-1", "content": "synthetic medical text"}],
            _ReportingClient(),
            sample_rate=1.0,
            max_chunks=1,
        )

    assert results == {"chunk-1": {"keywords": ["synthetic-term"], "summary": "Synthetic summary."}}
    snapshot = accumulator.snapshot()
    assert snapshot["usage_by_role"] == {
        "enrichment": {
            "input_tokens": 5,
            "output_tokens": 2,
            "total_tokens": 7,
            "status": "reported",
            "source": "provider_sdk",
        }
    }
    assert snapshot["unknowns"] == []


@pytest.mark.asyncio
async def test_cancelled_enrichment_holds_semaphore_until_worker_settles():
    started = threading.Event()
    release = threading.Event()
    settled = threading.Event()

    class _BlockingClient:
        def generate(self, prompt: str, context: str) -> str:
            started.set()
            try:
                release.wait()
                return "{}"
            finally:
                settled.set()

    semaphore = asyncio.Semaphore(1)
    task = asyncio.create_task(
        _enrich_chunk_batch(
            [{"id": "chunk-1", "content": "synthetic medical text"}],
            _BlockingClient(),
            True,
            True,
            semaphore,
        )
    )
    assert await asyncio.to_thread(started.wait, 2)

    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    assert semaphore.locked()
    assert not settled.is_set()

    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert settled.is_set()
    assert not semaphore.locked()
