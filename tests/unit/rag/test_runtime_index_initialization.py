import asyncio
import threading
from types import SimpleNamespace

import pytest

from src.config.context import RuntimeState, get_runtime_state
from src.rag import index as rag_index
from src.rag import runtime


class _FakeVectorStore:
    def __init__(self, contents: list[str] | None = None):
        self.documents = {
            "contents": list(contents or []),
            "index_metadata": {},
        }
        self.last_indexing_stats: dict[str, int] = {}
        self.cleared = False
        self.search_calls: list[tuple[str, int, str]] = []

    def similarity_search_with_trace(self, query: str, *, top_k: int, search_mode: str):
        assert self.documents["contents"], "Retrieval must wait for index initialization"
        self.search_calls.append((query, top_k, search_mode))
        return (
            [
                {
                    "id": "synthetic-chunk",
                    "content": self.documents["contents"][0],
                    "source": "synthetic.txt",
                    "combined_score": 1.0,
                    "rank": 1,
                }
            ],
            {"timing_ms": 0, "result_count": 1, "score_weights": {}},
        )

    def clear(self) -> None:
        self.documents["contents"] = []
        self.cleared = True


class _FakeIngestionResult:
    def __init__(self):
        self.stats = {
            "attempted": 1,
            "inserted": 1,
            "skipped_duplicate_content": 0,
            "build_elapsed_ms": 5,
            "pdf_document_count": 0,
            "markdown_document_count": 1,
            "reference_document_count": 1,
            "chunk_count": 2,
            "hype_chunk_count": 0,
            "enriched_chunk_count": 0,
        }

    def to_stats(self) -> dict[str, int]:
        return dict(self.stats)


def test_initialize_vector_store_rebuilds_after_runtime_config_switch(monkeypatch):
    stores = {
        "collection_a": _FakeVectorStore(["existing"]),
        "collection_b": _FakeVectorStore([]),
    }
    active_collection = {"name": "collection_a"}
    build_calls: list[str] = []

    def fake_get_vector_store():
        return stores[active_collection["name"]]

    def fake_get_runtime_config():
        return {"collection_name": active_collection["name"]}

    def fake_run_ingestion(config):
        build_calls.append(active_collection["name"])
        stores[active_collection["name"]].documents["contents"] = ["built"]
        return _FakeIngestionResult()

    monkeypatch.setattr(rag_index, "get_vector_store", fake_get_vector_store)
    monkeypatch.setattr(rag_index, "get_vector_store_runtime_config", fake_get_runtime_config)
    monkeypatch.setattr(rag_index, "run_ingestion", fake_run_ingestion)
    monkeypatch.setattr(rag_index, "_vector_store_runtime_signature", lambda: "test-sig")
    state = get_runtime_state()
    state.reset_vector_store_state()

    first = rag_index.initialize_vector_store()
    active_collection["name"] = "collection_b"
    second = rag_index.initialize_vector_store()

    assert first["status"] == "ready"
    assert first["reused_existing_index"] is True
    assert second["status"] == "built"
    assert second["reused_existing_index"] is False
    assert build_calls == ["collection_b"]


def test_build_path_delegates_to_run_ingestion(monkeypatch):
    store = _FakeVectorStore([])
    captured: list[object] = []

    def fake_run_ingestion(config):
        captured.append(config)
        store.documents["contents"] = ["built"]
        return _FakeIngestionResult()

    monkeypatch.setattr(rag_index, "get_vector_store", lambda: store)
    monkeypatch.setattr(rag_index, "get_vector_store_runtime_config", dict)
    monkeypatch.setattr(rag_index, "run_ingestion", fake_run_ingestion)
    monkeypatch.setattr(rag_index, "_vector_store_runtime_signature", lambda: "test-sig")
    get_runtime_state().reset_vector_store_state()

    result = rag_index.initialize_vector_store(rebuild=True)

    assert store.cleared is True
    assert len(captured) == 1
    assert captured[0].force_rebuild is True
    assert result["status"] == "built"
    assert result["vector_document_count"] == 1
    assert result["indexing_stats"] == _FakeIngestionResult().to_stats()


@pytest.fixture
def retrieval_store(monkeypatch):
    """Keep real initialization/retrieval, replacing only storage and ingestion."""
    store = _FakeVectorStore(["synthetic evidence"])
    state = RuntimeState()
    build_calls: list[object] = []

    def fake_run_ingestion(config):
        build_calls.append(config)
        store.documents["contents"] = ["synthetic evidence"]
        return _FakeIngestionResult()

    monkeypatch.setattr(rag_index, "get_runtime_state", lambda: state)
    monkeypatch.setattr(rag_index, "get_vector_store", lambda: store)
    monkeypatch.setattr(runtime, "get_vector_store", lambda: store)
    monkeypatch.setattr(
        rag_index,
        "get_vector_store_runtime_config",
        lambda: {"collection_name": "synthetic-runtime"},
    )
    monkeypatch.setattr(rag_index, "run_ingestion", fake_run_ingestion)
    monkeypatch.setattr(runtime.settings.hype, "enabled", False)
    monkeypatch.setattr(runtime.settings.retrieval, "enable_reranking", False)
    monkeypatch.setattr(runtime.settings.retrieval, "medical_expansion_enabled", False)
    return store, state, build_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("initialized", [False, True])
@pytest.mark.parametrize("query", ["synthetic query", "x" * 4001], ids=["short", "truncated"])
async def test_async_retrieval_reuses_existing_index(retrieval_store, initialized, query):
    store, state, build_calls = retrieval_store
    if initialized:
        state.set_vector_store_initialized(rag_index._vector_store_runtime_signature())

    context, sources, trace = await runtime.retrieve_context_with_trace_async(
        query, top_k=1, retrieval_options={"search_mode": "semantic_only"}
    )

    assert "synthetic evidence" in context
    assert len(sources) == 1
    assert sources[0].source == "synthetic.txt"
    assert trace.retrieval.query == query[:4000]
    assert trace.retrieval.query_original_length == len(query)
    assert trace.retrieval.query_truncated is (len(query) > 4000)
    assert trace.retrieval.documents[0].id == "synthetic-chunk"
    assert store.search_calls == [
        (expanded_query, 4, "semantic_only")
        for expanded_query in trace.retrieval.score_weights["expanded_queries"]
    ]
    assert state.get_vector_store_status() == {
        "initialized": True,
        "signature": rag_index._vector_store_runtime_signature(),
    }
    assert build_calls == []
    assert store.cleared is False


@pytest.mark.asyncio
async def test_async_retrieval_waits_for_initial_index_build(retrieval_store):
    store, state, build_calls = retrieval_store
    store.documents["contents"] = []

    context, sources, trace = await runtime.retrieve_context_with_trace_async(
        "synthetic query", top_k=1, retrieval_options={"search_mode": "semantic_only"}
    )

    assert "synthetic evidence" in context
    assert len(sources) == 1
    assert trace.context.total_chunks == 1
    assert state.vector_store_initialized is True
    assert len(build_calls) == 1
    assert build_calls[0].force_rebuild is False
    assert store.search_calls == [
        (expanded_query, 4, "semantic_only")
        for expanded_query in trace.retrieval.score_weights["expanded_queries"]
    ]
    assert store.cleared is False


@pytest.mark.parametrize("has_contents", [False, True], ids=["empty-index", "existing-index"])
def test_sync_retrieval_initializes_index(retrieval_store, has_contents):
    store, state, build_calls = retrieval_store
    if not has_contents:
        store.documents["contents"] = []

    context, sources, trace = runtime.retrieve_context_with_trace(
        "synthetic query", top_k=1, retrieval_options={"search_mode": "semantic_only"}
    )

    assert "synthetic evidence" in context
    assert len(sources) == 1
    assert trace.retrieval.documents[0].id == "synthetic-chunk"
    assert store.search_calls == [
        (expanded_query, 4, "semantic_only")
        for expanded_query in trace.retrieval.score_weights["expanded_queries"]
    ]
    assert state.vector_store_initialized is True
    assert len(build_calls) == (0 if has_contents else 1)
    assert store.cleared is False


@pytest.mark.asyncio
async def test_sync_retrieval_still_rejects_running_event_loop(retrieval_store):
    store, state, build_calls = retrieval_store

    with pytest.raises(RuntimeError, match="Use initialize_vector_store_async in async context"):
        runtime.retrieve_context_with_trace("synthetic query")

    assert store.search_calls == []
    assert state.vector_store_initialized is False
    assert build_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", " \t\n"], ids=["empty", "whitespace"])
async def test_empty_retrieval_does_not_initialize_index(retrieval_store, query):
    store, state, build_calls = retrieval_store

    sync_result = runtime.retrieve_context_with_trace(query)
    async_result = await runtime.retrieve_context_with_trace_async(query)

    for context, sources, trace in (sync_result, async_result):
        assert context == ""
        assert sources == []
        assert trace.context.total_chunks == 0
        assert trace.retrieval.documents == []
    assert store.search_calls == []
    assert state.vector_store_initialized is False
    assert build_calls == []


class _BoundedInitializationLock:
    """Real thread lock with a test-only timeout so regressions cannot hang pytest."""

    def __init__(self):
        self._lock = threading.Lock()
        self.attempted = threading.Event()
        self.exited = threading.Semaphore(0)

    def __enter__(self):
        self.attempted.set()
        if not self._lock.acquire(timeout=5):
            raise TimeoutError("Initialization lock blocked the event loop or worker")
        return self

    def __exit__(self, *args):
        self._lock.release()
        self.exited.release()


@pytest.fixture
def blocked_initialization(monkeypatch, retrieval_store):
    store, state, build_calls = retrieval_store
    store.documents["contents"] = []
    control = SimpleNamespace(
        store=store,
        state=state,
        calls=build_calls,
        started=threading.Event(),
        release=threading.Event(),
        finished=threading.Event(),
        lock=_BoundedInitializationLock(),
        failure=None,
        store_accesses=0,
    )

    def fake_get_vector_store():
        control.store_accesses += 1
        return store

    def fake_run_ingestion(config):
        build_calls.append(config)
        control.started.set()
        try:
            if not control.release.wait(timeout=10):
                raise TimeoutError("Test did not release synthetic ingestion")
            if control.failure is not None:
                raise control.failure
            store.documents["contents"] = ["synthetic evidence"]
            return _FakeIngestionResult()
        finally:
            control.finished.set()

    monkeypatch.setattr(rag_index, "_INITIALIZATION_LOCK", control.lock)
    monkeypatch.setattr(rag_index, "get_vector_store", fake_get_vector_store)
    monkeypatch.setattr(rag_index, "run_ingestion", fake_run_ingestion)
    try:
        yield control
    finally:
        control.release.set()


@pytest.mark.asyncio
@pytest.mark.parametrize("sync_waiter", [False, True], ids=["async-waiter", "sync-waiter"])
async def test_concurrent_initialization_builds_once_without_blocking_loop(
    blocked_initialization, sync_waiter
):
    control = blocked_initialization
    first = asyncio.create_task(rag_index.initialize_runtime_index_async())
    tasks = [first]
    try:
        assert await asyncio.to_thread(control.started.wait, 5)
        control.lock.attempted.clear()
        waiter = asyncio.create_task(
            asyncio.to_thread(rag_index.initialize_runtime_index)
            if sync_waiter
            else rag_index.initialize_runtime_index_async()
        )
        tasks.append(waiter)
        assert await asyncio.to_thread(control.lock.attempted.wait, 5)
        # The loop reached this point while the first build still holds the lock.
        assert not waiter.done()
        assert len(control.calls) == 1
        assert control.state.vector_store_initialized is False
        control.release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
        assert [result["status"] for result in results] == ["built", "ready"]
        assert len(control.calls) == 1
        assert control.state.vector_store_initialized is True
    finally:
        control.release.set()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancelled_active_initialization_keeps_worker_serialized(blocked_initialization):
    control = blocked_initialization
    first = asyncio.create_task(rag_index.initialize_runtime_index_async())
    tasks = [first]
    try:
        assert await asyncio.to_thread(control.started.wait, 5)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not control.finished.is_set()
        assert control.state.vector_store_initialized is False

        control.lock.attempted.clear()
        waiter = asyncio.create_task(rag_index.initialize_runtime_index_async())
        tasks.append(waiter)
        assert await asyncio.to_thread(control.lock.attempted.wait, 5)
        assert not waiter.done()
        assert len(control.calls) == 1
        control.release.set()
        result = await asyncio.wait_for(waiter, timeout=5)
        assert result["status"] == "ready"
        assert control.finished.is_set()
        assert len(control.calls) == 1
        assert control.state.vector_store_initialized is True
        assert control.store.cleared is False
    finally:
        control.release.set()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("rebuild", [False, True], ids=["load", "forced-rebuild"])
async def test_observed_cancellation_before_worker_admission_skips_store(
    blocked_initialization, rebuild
):
    control = blocked_initialization
    first = asyncio.create_task(rag_index.initialize_runtime_index_async())
    tasks = [first]
    try:
        assert await asyncio.to_thread(control.started.wait, 5)
        control.lock.attempted.clear()
        waiter = asyncio.create_task(rag_index.initialize_runtime_index_async(rebuild=rebuild))
        tasks.append(waiter)
        # Ensure cancellation happens after the second worker starts waiting.
        assert await asyncio.to_thread(control.lock.attempted.wait, 5)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert control.store.cleared is False
        control.release.set()
        assert (await asyncio.wait_for(first, timeout=5))["status"] == "built"
        # Both lock scopes must exit, including the cancelled worker's scope.
        for _ in range(2):
            assert await asyncio.to_thread(control.lock.exited.acquire, timeout=5)
        assert control.store_accesses == 1
        assert len(control.calls) == 1
        assert control.store.cleared is False
        assert control.state.vector_store_initialized is True
    finally:
        control.release.set()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancellation_after_worker_admission_allows_build_to_finish(
    monkeypatch, blocked_initialization
):
    control = blocked_initialization
    admitted = threading.Event()
    continue_worker = threading.Event()
    original_signature = rag_index._vector_store_runtime_signature

    def paused_signature():
        # Called after the worker's cancellation checkpoint, before store access.
        admitted.set()
        if not continue_worker.wait(timeout=5):
            raise TimeoutError("Test did not release admitted initializer")
        return original_signature()

    monkeypatch.setattr(rag_index, "_vector_store_runtime_signature", paused_signature)
    task = asyncio.create_task(rag_index.initialize_runtime_index_async(rebuild=True))
    try:
        assert await asyncio.to_thread(admitted.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert control.store_accesses == 0
        assert control.store.cleared is False
    finally:
        continue_worker.set()
        control.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(control.lock.exited.acquire, timeout=5)

    # Cancellation cannot revoke work already admitted at the checkpoint.
    assert control.store_accesses == 1
    assert control.store.cleared is True
    assert len(control.calls) == 1
    assert control.state.vector_store_initialized is True


@pytest.mark.asyncio
async def test_initialization_failure_releases_lock_for_retry(blocked_initialization):
    control = blocked_initialization
    control.failure = RuntimeError("synthetic ingestion failed")
    control.release.set()

    with pytest.raises(RuntimeError, match="synthetic ingestion failed"):
        await asyncio.wait_for(rag_index.initialize_runtime_index_async(), timeout=5)
    assert control.state.vector_store_initialized is False
    assert control.store.documents["contents"] == []

    control.failure = None
    result = await asyncio.wait_for(rag_index.initialize_runtime_index_async(), timeout=5)
    assert result["status"] == "built"
    assert len(control.calls) == 2
    assert control.state.vector_store_initialized is True
