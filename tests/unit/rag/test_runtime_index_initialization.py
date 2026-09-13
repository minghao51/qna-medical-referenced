from src.config.context import get_runtime_state
from src.rag import index as rag_index


class _FakeVectorStore:
    def __init__(self, contents: list[str] | None = None):
        self.documents = {
            "contents": list(contents or []),
            "index_metadata": {},
        }
        self.last_indexing_stats: dict[str, int] = {}
        self.cleared = False

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
