from src.config.context import get_runtime_state
from src.rag import runtime


class _FakeVectorStore:
    def __init__(self, contents: list[str] | None = None):
        self.documents = {
            "contents": list(contents or []),
            "index_metadata": {},
        }
        self.last_indexing_stats = {}
        self.cleared = False

    def clear(self) -> None:
        self.documents["contents"] = []
        self.cleared = True


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

    def fake_build_index(vector_store):
        build_calls.append(active_collection["name"])
        vector_store.documents["contents"] = ["built"]
        return {"attempted": 1, "inserted": 1}

    monkeypatch.setattr(runtime, "get_vector_store", fake_get_vector_store)
    monkeypatch.setattr(runtime, "get_vector_store_runtime_config", fake_get_runtime_config)
    monkeypatch.setattr(runtime, "_build_index_from_sources", fake_build_index)
    state = get_runtime_state()
    state.reset_vector_store_state()

    first = runtime.initialize_vector_store()
    active_collection["name"] = "collection_b"
    second = runtime.initialize_vector_store()

    assert first["status"] == "ready"
    assert first["reused_existing_index"] is True
    assert second["status"] == "built"
    assert second["reused_existing_index"] is False
    assert build_calls == ["collection_b"]
