"""Real async orchestration with bounded, synthetic blocking dependencies."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from types import SimpleNamespace

import anyio
import pytest

from src.config import context as runtime_context
from src.config.context import RuntimeState
from src.rag import index as rag_index
from src.rag import query_expansion, reranker, retrieval, runtime
from src.rag.medical_expansion import MedicalExpansion

_RUN_CONTEXT = ContextVar("synthetic_retrieval_run", default="missing")
_BLOCKING_STAGES = ["store", "medical", "hype", "search", "rerank"]


@pytest.fixture
def synthetic_retrieval(monkeypatch):
    state = RuntimeState()
    control = SimpleNamespace(
        blocked=None,
        failure=None,
        started=threading.Event(),
        release=threading.Event(),
        hyde_started=asyncio.Event(),
        hyde_release=asyncio.Event(),
        calls=[],
    )

    def visit(stage, detail=None):
        control.calls.append((stage, detail, threading.get_ident(), _RUN_CONTEXT.get()))
        if control.blocked == stage and stage != "hyde":
            control.started.set()
            if not control.release.wait(timeout=5):
                raise TimeoutError(f"Test did not release synthetic {stage}")
        if control.failure == stage:
            raise RuntimeError(f"Synthetic {stage} failure")

    class Store:
        documents = {"contents": ["synthetic evidence"], "index_metadata": {}}
        last_indexing_stats = {}

        def search_hypothetical_questions(self, query, *, limit):
            visit("hype", query)
            assert limit == 5
            return ["synthetic indexed question"]

        def similarity_search_with_trace(self, query, *, top_k, search_mode):
            visit("search", query)
            assert top_k >= 2
            return (
                [
                    {
                        "id": name,
                        "content": f"synthetic evidence {name}",
                        "source": f"synthetic-{name}.txt",
                        "page": 1,
                        "combined_score": score,
                        "rank": rank,
                        "metadata": {"source_type": "synthetic"},
                    }
                    for rank, (name, score) in enumerate(
                        [("a", 0.9), ("b", 0.8), ("c", 0.7)], start=1
                    )
                ],
                {"timing_ms": 0, "score_weights": {}, "search_mode": search_mode},
            )

    class MedicalProvider:
        def expand(self, query, *, base_queries):
            visit("medical", query)
            assert query in base_queries
            return [MedicalExpansion("synthetic related term", "synthetic", "synonym")]

    class Model:
        def predict(self, pairs):
            visit("rerank")
            scores = {"a": 0.7, "b": 0.9, "c": 0.2}
            return [scores[content[-1]] for _, content in pairs]

    class Client:
        def generate(self, **kwargs):
            visit("sync_hyde")
            raise AssertionError("HyDE must not use synchronous generation")

        async def a_generate(self, *, prompt, context):
            visit("hyde", prompt)
            assert context == ""
            control.hyde_started.set()
            if control.blocked == "hyde":
                await control.hyde_release.wait()
            await asyncio.sleep(0)
            return "synthetic hypothetical guidance"

    store = Store()
    model = Model()
    ranker = reranker.CrossEncoderReranker(model_name="synthetic-reranker")
    ranker._model = model

    def get_store():
        visit("store")
        return store

    original_lexical = query_expansion.expand_lexical_queries

    def lexical(query):
        visit("lexical", query)
        return original_lexical(query)

    original_trace = runtime._build_pipeline_trace

    def build_trace(**kwargs):
        visit("trace")
        return original_trace(**kwargs)

    def unexpected_ingestion(*args, **kwargs):
        raise AssertionError("Synthetic populated index must not invoke ingestion")

    monkeypatch.setattr(rag_index, "run_ingestion", unexpected_ingestion)
    monkeypatch.setattr(runtime_context, "get_runtime_state", lambda: state)
    monkeypatch.setattr(rag_index, "get_runtime_state", lambda: state)
    monkeypatch.setattr(rag_index, "get_vector_store", lambda: store)
    monkeypatch.setattr(
        rag_index, "get_vector_store_runtime_config", lambda: {"collection_name": "synthetic"}
    )
    monkeypatch.setattr(runtime, "get_vector_store", get_store)
    monkeypatch.setattr(runtime, "_build_pipeline_trace", build_trace)
    monkeypatch.setattr(query_expansion, "expand_lexical_queries", lexical)
    monkeypatch.setattr(
        query_expansion, "get_medical_expansion_provider", lambda name: MedicalProvider()
    )
    control.original_get_reranker = reranker.get_reranker
    monkeypatch.setattr(reranker, "get_reranker", lambda: ranker)
    control.options = {
        "search_mode": "rrf_hybrid",
        "enable_query_understanding": False,
        "enable_medical_expansion": True,
        "medical_expansion_provider": "synthetic",
        "enable_hype": True,
        "enable_hyde": False,
        "enable_reranking": True,
        "reranking_mode": "both",
        "enable_diversification": True,
        "overfetch_multiplier": 2,
        "rerank_score_threshold": 0.5,
    }
    control.store = store
    control.client = Client()
    control.model = model
    control.ranker = ranker
    control.visit = visit
    token = _RUN_CONTEXT.set("synthetic-run")
    try:
        yield control
    finally:
        control.release.set()
        control.hyde_release.set()
        _RUN_CONTEXT.reset(token)


def _retrieve(control, **options):
    return runtime.retrieve_context_with_trace_async(
        "synthetic query",
        top_k=2,
        retrieval_options={**control.options, **options},
        hyde_client=control.client,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", _BLOCKING_STAGES)
async def test_async_runtime_keeps_loop_responsive(synthetic_retrieval, stage):
    control = synthetic_retrieval
    control.blocked = stage
    loop_thread = threading.get_ident()
    task = asyncio.create_task(_retrieve(control))
    try:
        assert await asyncio.to_thread(control.started.wait, 5)
        # A synchronous call on this loop would have timed out before we got here.
        assert not task.done()
        control.release.set()
        context, sources, trace = await asyncio.wait_for(task, timeout=5)
    finally:
        control.release.set()
        await asyncio.gather(task, return_exceptions=True)

    assert context
    assert len(sources) == 2
    # Preserve existing MMR behavior, which uses combined rather than rerank scores.
    assert [doc.id for doc in trace.retrieval.documents] == ["a", "b"]
    for name, _, thread_id, context_value in control.calls:
        if name in {*_BLOCKING_STAGES, "lexical"}:
            assert thread_id != loop_thread
            assert context_value == "synthetic-run"
    queries = trace.retrieval.score_weights["expanded_queries"]
    assert [detail for name, detail, *_ in control.calls if name == "search"] == queries
    assert [name for name, *_ in control.calls] == [
        "store",
        "lexical",
        "medical",
        "hype",
        *["search"] * len(queries),
        "rerank",
        "trace",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["expansion", "candidates"])
async def test_direct_async_entry_offloads_fallback_expansion(synthetic_retrieval, entry):
    control = synthetic_retrieval
    control.blocked = "lexical"
    if entry == "expansion":
        operation = query_expansion.expand_queries_async("synthetic query")
    else:
        operation = retrieval.retrieve_candidates_with_trace_async(
            control.store, "synthetic query", 2, "semantic_only"
        )
    task = asyncio.create_task(operation)
    try:
        assert await asyncio.to_thread(control.started.wait, 5)
        assert not task.done()
        control.release.set()
        result = await asyncio.wait_for(task, timeout=5)
    finally:
        control.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert result
    assert all(thread_id != threading.get_ident() for _, _, thread_id, _ in control.calls)
    assert all(value == "synthetic-run" for *_, value in control.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("queries", [None, ["variant alpha", "variant beta"]])
async def test_direct_async_candidates_offload_search(synthetic_retrieval, queries):
    control = synthetic_retrieval
    control.blocked = "search"
    task = asyncio.create_task(
        retrieval.retrieve_candidates_with_trace_async(
            control.store, "synthetic query", 2, "semantic_only", pre_expanded_queries=queries
        )
    )
    try:
        assert await asyncio.to_thread(control.started.wait, 5)
        assert not task.done()
        assert [name for name, *_ in control.calls].count("search") == 1
        control.release.set()
        results, trace = await asyncio.wait_for(task, timeout=5)
    finally:
        control.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert len(results) == 2
    searched = [detail for name, detail, *_ in control.calls if name == "search"]
    assert searched == trace["expanded_queries"]
    if queries is not None:
        assert searched == queries
    assert all(thread_id != threading.get_ident() for _, _, thread_id, _ in control.calls)


@pytest.mark.asyncio
async def test_empty_preexpanded_queries_skip_generation_and_search(synthetic_retrieval):
    control = synthetic_retrieval
    results, trace = await retrieval.retrieve_candidates_with_trace_async(
        control.store,
        "synthetic query",
        2,
        "semantic_only",
        pre_expanded_queries=[],
        enable_hyde=True,
        hyde_client=control.client,
    )
    assert results == []
    assert trace["expanded_queries"] == []
    assert trace["hyde_enabled"] is True
    assert control.calls == []


@pytest.mark.asyncio
async def test_async_runtime_matches_sync_results_and_trace(synthetic_retrieval):
    control = synthetic_retrieval
    sync_context, sync_sources, sync_trace = await asyncio.to_thread(
        runtime.retrieve_context_with_trace,
        "synthetic query",
        top_k=2,
        retrieval_options=control.options,
    )
    context, sources, trace = await _retrieve(control)
    assert context == sync_context
    assert sources == sync_sources
    assert trace.context == sync_trace.context
    payloads = []
    for item in (sync_trace, trace):
        payload = item.retrieval.model_dump(exclude={"timing_ms", "steps"})
        payload["score_weights"].pop("rerank_timing_ms")
        payloads.append(payload)
    assert payloads[0] == payloads[1]
    assert [step.name for step in trace.retrieval.steps] == [
        "query_expansion",
        "semantic_search",
        "keyword_search",
        "score_fusion",
        "reranking",
    ]
    assert trace.retrieval.score_weights["medical_expansion_term_count"] == 1
    assert trace.retrieval.score_weights["rerank_filtered_out"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", _BLOCKING_STAGES)
async def test_worker_failure_stops_downstream_stages(synthetic_retrieval, stage):
    control = synthetic_retrieval
    control.failure = stage
    with pytest.raises(RuntimeError, match=f"Synthetic {stage} failure"):
        await _retrieve(control)
    assert control.calls[-1][0] == stage
    assert "trace" not in [name for name, *_ in control.calls]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", _BLOCKING_STAGES)
@pytest.mark.parametrize("cancellation", ["asyncio", "anyio"])
async def test_cancelled_worker_stage_does_not_continue_orchestration(
    synthetic_retrieval, stage, cancellation
):
    control = synthetic_retrieval
    control.blocked = stage
    # The caller remains owned until the synchronous stage has actually settled.
    with ThreadPoolExecutor(max_workers=4) as pool:
        asyncio.get_running_loop().set_default_executor(pool)
        if cancellation == "asyncio":
            task = asyncio.create_task(_retrieve(control))
            try:
                assert await asyncio.to_thread(control.started.wait, 5)
                assert not task.done()
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
                assert not task.done()
                control.release.set()
                with pytest.raises(asyncio.CancelledError):
                    await task
            finally:
                control.release.set()
                await asyncio.gather(task, return_exceptions=True)
        else:
            cancelled = asyncio.Event()

            async def retrieve_and_record_cancel():
                try:
                    await _retrieve(control)
                except asyncio.CancelledError:
                    cancelled.set()
                    raise

            try:
                async with anyio.create_task_group() as group:
                    group.start_soon(retrieve_and_record_cancel)
                    assert await asyncio.to_thread(control.started.wait, 5)
                    group.cancel_scope.cancel()
                    with anyio.CancelScope(shield=True):
                        await asyncio.sleep(0)
                        assert not cancelled.is_set()
                        control.release.set()
                assert cancelled.is_set()
            finally:
                control.release.set()
    stages = [name for name, *_ in control.calls]
    assert "trace" not in stages
    assert stages[-1] == stage


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
async def test_hyde_uses_native_async_client_on_owning_loop(synthetic_retrieval, fails):
    control = synthetic_retrieval
    if fails:
        control.failure = "hyde"
    _, _, trace = await _retrieve(control, enable_hyde=True)
    calls = [call for call in control.calls if call[0] == "hyde"]
    assert len(calls) == 1
    assert calls[0][2:] == (threading.get_ident(), "synthetic-run")
    stages = [name for name, *_ in control.calls]
    assert "sync_hyde" not in stages
    assert stages.index("medical") < stages.index("hyde") < stages.index("hype")
    assert (
        "synthetic hypothetical guidance" in trace.retrieval.score_weights["expanded_queries"]
    ) is not fails
    assert trace.retrieval.steps[0].details["hyde_enabled"] is True


@pytest.mark.asyncio
async def test_hyde_cancellation_propagates_without_search(synthetic_retrieval):
    control = synthetic_retrieval
    control.blocked = "hyde"
    task = asyncio.create_task(_retrieve(control, enable_hyde=True))
    try:
        await asyncio.wait_for(control.hyde_started.wait(), timeout=5)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        control.hyde_release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert control.calls[-1][0] == "hyde"


@pytest.mark.asyncio
async def test_shared_reranker_serializes_cold_load_and_prediction(
    monkeypatch, synthetic_retrieval
):
    control = synthetic_retrieval
    control.blocked = "construct"
    original_init = reranker.CrossEncoderReranker.__init__
    attempted = threading.Event()
    lock = threading.Lock()
    counter_lock = threading.Lock()
    attempts = 0

    class BoundedLock:
        def __enter__(self):
            nonlocal attempts
            with counter_lock:
                attempts += 1
                if attempts == 2:
                    attempted.set()
            if not lock.acquire(timeout=5):
                raise TimeoutError("Reranker lock did not release")

        def __exit__(self, *args):
            lock.release()

    def construct(instance, *args, **kwargs):
        control.visit("construct")
        original_init(instance, *args, **kwargs)

    def load_model(instance):
        if instance._model is None:
            control.visit("load")
            instance._model = control.model

    monkeypatch.setattr(reranker, "get_reranker", control.original_get_reranker)
    monkeypatch.setattr(reranker.CrossEncoderReranker, "__init__", construct)
    monkeypatch.setattr(reranker.CrossEncoderReranker, "_load_model", load_model)
    monkeypatch.setattr(runtime, "_RERANKING_LOCK", BoundedLock())
    first = asyncio.create_task(_retrieve(control))
    second = None
    try:
        assert await asyncio.to_thread(control.started.wait, 5)
        second = asyncio.create_task(_retrieve(control))
        assert await asyncio.to_thread(attempted.wait, 5)
        assert not first.done()
        assert not second.done()
        assert [name for name, *_ in control.calls].count("construct") == 1
        assert "load" not in [name for name, *_ in control.calls]
        control.release.set()
        results = await asyncio.wait_for(asyncio.gather(first, second), timeout=5)
    finally:
        control.release.set()
        await asyncio.gather(*[task for task in (first, second) if task], return_exceptions=True)
    assert results[0][:2] == results[1][:2]
    stages = [name for name, *_ in control.calls]
    assert stages.count("construct") == 1
    assert stages.count("load") == 1
    assert stages.count("rerank") == 2
