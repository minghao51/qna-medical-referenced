"""Real lifespan/HTTP/SSE orchestration with synthetic leaves and temporary files."""

import asyncio
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr


def _expected_index_metadata() -> dict:
    """Build metadata the no-build readiness gate expects for a frozen index.

    Reuses the production helper so the synthetic store cannot drift from the
    gate it is validated by.
    """
    from src.rag.index import _expected_index_metadata as expected

    return expected()


@pytest.fixture
def lifecycle(monkeypatch, tmp_path):
    import src.config as config
    from src.config import context, settings

    # Protect import-time SQLite construction even when this file runs alone.
    monkeypatch.setattr(config, "RATE_LIMIT_DB", tmp_path / "rate_limits.db")
    monkeypatch.setattr(config, "CHAT_HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(settings.app, "environment", "development")
    monkeypatch.setattr(settings.api, "api_keys", "")
    monkeypatch.setattr(settings.api, "api_keys_json", None)
    monkeypatch.setattr(settings.wandb, "wandb_api_key", SecretStr(""))
    monkeypatch.setattr(settings.production, "production_profile", None)
    monkeypatch.setattr(settings.hype, "enabled", False)
    monkeypatch.setattr(settings.retrieval, "enable_reranking", False)
    monkeypatch.setattr(settings.retrieval, "medical_expansion_enabled", False)

    from src.app import factory
    from src.app.middleware import rate_limit
    from src.app.middleware.auth import APIKeyConfig
    from src.infra.storage.file_chat_history_store import FileChatHistoryStore
    from src.ingestion.indexing import factory as store_factory
    from src.rag import index, production_profile

    monkeypatch.setattr(rate_limit, "RATE_LIMIT_DB", tmp_path / "rate_limits.db")
    monkeypatch.setattr(rate_limit, "rate_limiter", rate_limit.RateLimiter())
    monkeypatch.setattr(APIKeyConfig, "_records", [])
    monkeypatch.setattr(APIKeyConfig, "_record_map", {})
    monkeypatch.setattr(APIKeyConfig, "_loaded", True)
    monkeypatch.setattr(context, "_state", context.RuntimeState())
    cache = store_factory.ChromaVectorStoreFactory
    monkeypatch.setattr(cache, "_instance", None)
    monkeypatch.setattr(cache, "_runtime_config", {})
    monkeypatch.setattr(cache, "_runtime_signature_value", None)
    control = SimpleNamespace(
        cold=False,
        failure=None,
        close_failure=False,
        block_build=False,
        block_close=False,
        build_started=threading.Event(),
        release_build=threading.Event(),
        build_finished=threading.Event(),
        close_started=asyncio.Event(),
        release_close=asyncio.Event(),
        closed=0,
        constructed=0,
        builds=0,
        searches=[],
        fetch_ks=[],
        real_apply_profile=production_profile.apply_production_profile,
        generations=[],
        stream_closed=0,
        constructor_threads=[],
        close_threads=[],
        body_entered=False,
    )

    class Store:
        def __init__(self, **kwargs):
            if control.failure == "store":
                raise RuntimeError("Synthetic store failure")
            control.constructed += 1
            control.constructor_threads.append(threading.get_ident())
            if control.block_build:  # Block existing-index loading, not web ingestion.
                control.build_started.set()
                try:
                    if not control.release_build.wait(timeout=5):
                        raise TimeoutError("Test did not release synthetic index load")
                    if control.failure == "loading":
                        raise RuntimeError("Synthetic loading failure")
                finally:
                    control.build_finished.set()
            self.documents = {
                "contents": [] if control.cold else ["synthetic evidence"],
                "index_metadata": _expected_index_metadata(),
            }
            self.last_indexing_stats = {}

        def similarity_search_with_trace(self, query, *, top_k, search_mode):
            assert self.documents["contents"]
            control.searches.append((query, threading.get_ident()))
            control.fetch_ks.append(top_k)
            return (
                [
                    {
                        "id": "synthetic-chunk",
                        "content": "synthetic evidence",
                        "source": "synthetic.txt",
                        "page": 1,
                        "combined_score": 1.0,
                        "rank": 1,
                        "metadata": {"logical_name": "Synthetic reference"},
                    }
                ],
                {"timing_ms": 0, "result_count": 1, "score_weights": {}},
            )

    class Client:
        model = "synthetic-model"

        async def a_generate_stream(self, *, prompt, context):
            control.generations.append((prompt, context, threading.get_ident()))
            try:
                yield "synthetic "
                await asyncio.sleep(0)
                yield "answer"
            finally:
                control.stream_closed += 1

        async def aclose(self):
            control.closed += 1
            control.close_threads.append(threading.get_ident())
            control.close_started.set()
            if control.block_close:
                await control.release_close.wait()
            if control.close_failure:
                raise RuntimeError("forbidden-cleanup-detail")

    client = Client()

    def build_client():
        if control.failure == "client":
            raise RuntimeError("Synthetic client failure")
        return client

    def build_history():
        if control.failure == "history":
            raise RuntimeError("Synthetic history failure")
        return FileChatHistoryStore(tmp_path / "history.json")

    def apply_profile(name):
        if control.failure == "profile":
            raise RuntimeError("Synthetic profile failure")
        return True

    def ingest(config):
        control.builds += 1
        control.build_started.set()
        try:
            if control.block_build and not control.release_build.wait(timeout=5):
                raise TimeoutError("Test did not release synthetic build")
            if control.failure == "ingestion":
                raise RuntimeError("Synthetic ingestion failure")
            cache._instance.documents["contents"] = ["synthetic evidence"]
            return SimpleNamespace(
                to_stats=lambda: {
                    "attempted": 1,
                    "inserted": 1,
                    "skipped_duplicate_content": 0,
                }
            )
        finally:
            control.build_finished.set()

    monkeypatch.setattr(store_factory, "ChromaVectorStore", Store)
    monkeypatch.setattr(factory, "get_client", build_client)
    monkeypatch.setattr(factory, "FileChatHistoryStore", build_history)
    monkeypatch.setattr(production_profile, "apply_production_profile", apply_profile)
    monkeypatch.setattr(index, "run_ingestion", ingest)
    control.factory = factory
    control.cache = cache
    control.state = context.get_runtime_state()
    control.settings = settings
    control.tmp_path = tmp_path
    try:
        yield control
    finally:
        control.release_build.set()
        control.release_close.set()


def _assert_cleared(control, app):
    assert control.cache._instance is None
    assert control.state.vector_store_initialized is False
    for name in ("llm_client", "chat_history_store", "vector_store"):
        assert getattr(app.state, name, None) is None


@pytest.mark.parametrize("cold", [False, True], ids=["existing-index", "offline-built-index"])
@pytest.mark.parametrize("include_pipeline", [False, True])
def test_real_lifespan_serves_nonempty_sse_and_persists_history(lifecycle, cold, include_pipeline):
    from src.app.session import _verify_signed_session_id

    control = lifecycle
    control.cold = cold
    if cold:
        # Explicit ingestion is an operator/CLI operation, never a web startup side effect.
        from src.rag.index import initialize_runtime_index_async

        asyncio.run(initialize_runtime_index_async())
    app = control.factory.create_app()
    with TestClient(app) as http:
        assert app.state.vector_store is control.cache._instance
        assert control.state.vector_store_initialized is True
        history_store = app.state.chat_history_store
        response = http.post(
            "/chat",
            params={"include_pipeline": include_pipeline},
            json={"message": "synthetic question"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        assert [item["content"] for item in events if not item["done"]] == ["synthetic ", "answer"]
        terminal = [item for item in events if item["done"]]
        assert len(terminal) == 1
        assert terminal[0]["error"] is None
        assert terminal[0]["request_id"] == response.headers["x-request-id"]
        assert terminal[0]["sources"][0]["source"] == "synthetic.txt"
        if include_pipeline:
            assert terminal[0]["pipeline"]["retrieval"]["documents"][0]["id"] == "synthetic-chunk"
        else:
            assert terminal[0]["pipeline"] is None
        session = _verify_signed_session_id(
            http.cookies.get(control.settings.api.chat_session_cookie_name)
        )
        assert session
        history = history_store.get_history(session)
        assert [item["role"] for item in history] == ["user", "assistant"]
        assert [item["content"] for item in history] == ["synthetic question", "synthetic answer"]
        assert history_store.path == control.tmp_path / "history.json"
        assert history_store.path.exists()
        with sqlite3.connect(control.tmp_path / "rate_limits.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM rate_limit_events").fetchone()[0] == 1
        assert control.closed == 0
        assert control.constructed == 1
        assert control.builds == int(cold)
        assert control.stream_closed == 1
        loop_thread = control.generations[0][2]
        assert "synthetic evidence" in control.generations[0][1]
        assert control.constructor_threads[0] != loop_thread
        assert all(thread != loop_thread for _, thread in control.searches)
    assert control.closed == 1
    assert control.close_threads == [loop_thread]
    _assert_cleared(control, app)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage", ["client", "history", "profile", "store", "empty_index", "publish"]
)
async def test_startup_failure_cleans_acquired_resources(monkeypatch, lifecycle, stage):
    control = lifecycle
    control.failure = stage
    control.cold = stage == "empty_index"
    if stage == "profile":
        monkeypatch.setattr(control.settings.production, "production_profile", "synthetic")
    if stage == "publish":
        original_get = control.cache.get_vector_store.__func__
        calls = 0

        def get_store(cls, config=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("Synthetic publish failure")
            return original_get(cls, config)

        monkeypatch.setattr(control.cache, "get_vector_store", classmethod(get_store))
    app = control.factory.create_app()
    message = (
        "allow_build=False prevents ingestion"
        if stage == "empty_index"
        else f"Synthetic {stage} failure"
    )
    with pytest.raises(RuntimeError, match=message):
        async with app.router.lifespan_context(app):
            pytest.fail("Failed startup must never yield")
    assert control.closed == (0 if stage == "client" else 1)
    _assert_cleared(control, app)


@pytest.mark.asyncio
async def test_lifespan_body_exception_still_cleans_resources(lifecycle):
    control = lifecycle
    app = control.factory.create_app()
    with pytest.raises(ValueError, match="Synthetic body failure"):
        async with app.router.lifespan_context(app):
            raise ValueError("Synthetic body failure")
    assert control.closed == 1
    _assert_cleared(control, app)


@pytest.mark.asyncio
async def test_shutdown_does_not_close_replacement_client(lifecycle):
    control = lifecycle
    replacement_closed = []

    async def close_replacement():
        replacement_closed.append(True)

    app = control.factory.create_app()
    async with app.router.lifespan_context(app):
        app.state.llm_client = SimpleNamespace(aclose=close_replacement)
    assert control.closed == 1
    assert replacement_closed == []
    _assert_cleared(control, app)


@pytest.mark.asyncio
@pytest.mark.parametrize("startup_failure", [False, True])
async def test_cleanup_failure_is_logged_without_masking_startup_error(
    lifecycle, caplog, startup_failure
):
    control = lifecycle
    control.close_failure = True
    app = control.factory.create_app()
    if startup_failure:
        control.cold = True
        with pytest.raises(RuntimeError, match="allow_build=False prevents ingestion"):
            async with app.router.lifespan_context(app):
                pytest.fail("Failed startup must never yield")
    else:
        async with app.router.lifespan_context(app):
            pass
    assert control.closed == 1
    assert "LLM client cleanup failed" in caplog.text
    assert "forbidden-cleanup-detail" not in caplog.text
    _assert_cleared(control, app)


@pytest.mark.asyncio
@pytest.mark.parametrize("build_failure", [False, True])
async def test_cancelled_startup_drains_load_before_reset(lifecycle, build_failure):
    control = lifecycle
    control.block_build = True
    if build_failure:
        control.failure = "loading"
    app = control.factory.create_app()

    async def run():
        async with app.router.lifespan_context(app):
            control.body_entered = True

    with ThreadPoolExecutor(max_workers=4) as pool:
        asyncio.get_running_loop().set_default_executor(pool)
        task = asyncio.create_task(run())
        try:
            assert await asyncio.to_thread(control.build_started.wait, 5)
            for _ in range(2):
                task.cancel()
                await asyncio.sleep(0)
                assert not task.done()
                assert control.closed == 0
                assert control.cache._instance is None  # Constructor has not published yet.
            control.release_build.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            control.release_build.set()
            await asyncio.gather(task, return_exceptions=True)
    assert control.build_finished.is_set()
    assert control.body_entered is False
    assert control.closed == 1
    _assert_cleared(control, app)


@pytest.mark.parametrize("include_pipeline", [False, True])
def test_http_inherits_applied_profile_and_reports_active_model(
    monkeypatch, lifecycle, include_pipeline
):
    from src.app.middleware.auth import APIKeyConfig
    from src.rag import production_profile

    control = lifecycle
    monkeypatch.setattr(control.settings.api, "api_keys", "synthetic-api-key")
    monkeypatch.setattr(APIKeyConfig, "_loaded", False)
    monkeypatch.setattr(control.settings.production, "production_profile", "synthetic")
    monkeypatch.setattr(production_profile, "apply_production_profile", control.real_apply_profile)
    monkeypatch.setattr(
        production_profile,
        "_PROFILE_REGISTRY",
        {"synthetic": {"retrieval": {"top_k": 2, "overfetch_multiplier": 3}}},
    )
    app = control.factory.create_app()
    with TestClient(app, headers={"X-API-Key": "synthetic-api-key"}) as http:
        response = http.post(
            "/chat",
            params={"include_pipeline": include_pipeline},
            json={"message": "synthetic question"},
        )
        assert response.status_code == 200
        events = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        terminal = [event for event in events if event["done"]]
        assert len(terminal) == 1
        assert terminal[0]["error"] is None
        assert control.fetch_ks
        assert set(control.fetch_ks) == {6}
        config_response = http.get("/config")
        assert config_response.status_code == 200
        view = config_response.json()
        assert view["retrieval"]["top_k"] == 2
        assert view["production_profile"] == view["configured_production_profile"] == "synthetic"
        assert view["llm"]["model_name"] == "synthetic-model"
        if include_pipeline:
            assert terminal[0]["pipeline"]["retrieval"]["top_k"] == 2
            assert terminal[0]["pipeline"]["generation"]["model"] == "synthetic-model"
        else:
            assert terminal[0]["pipeline"] is None
    assert control.state.production_profile is None
    assert control.state.retrieval_overrides == {}
    _assert_cleared(control, app)


@pytest.mark.asyncio
async def test_client_without_owned_transports_needs_no_close_hook(monkeypatch, lifecycle):
    control = lifecycle
    monkeypatch.setattr(control.factory, "get_client", object)
    app = control.factory.create_app()
    async with app.router.lifespan_context(app):
        assert app.state.llm_client is not None
    assert control.closed == 0
    _assert_cleared(control, app)


@pytest.mark.asyncio
async def test_cancellation_during_cleanup_drains_client_close(lifecycle):
    control = lifecycle
    control.block_close = True
    app = control.factory.create_app()

    async def run():
        async with app.router.lifespan_context(app):
            pass

    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(control.close_started.wait(), timeout=5)
        for _ in range(2):
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            assert control.state.vector_store_initialized is True
        control.release_close.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        control.release_close.set()
        await asyncio.gather(task, return_exceptions=True)
    assert control.closed == 1
    _assert_cleared(control, app)
