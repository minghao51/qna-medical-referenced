"""Tests for thread safety of shared runtime state.

Validates that the RuntimeContext, vector store initialization, and config
mutations work correctly under concurrent access.
"""

import threading
import time


class TestRuntimeContextConcurrency:
    """Verify RuntimeContext is safe under concurrent reads/writes."""

    def test_concurrent_config_updates_no_crash(self):
        """Rapid concurrent updates to chunking config should not raise."""
        from src.config.context import get_runtime_state

        state = get_runtime_state()
        errors: list[Exception] = []

        def toggle_chunking(iterations: int):
            try:
                for i in range(iterations):
                    state.structured_chunking_enabled = i % 2 == 0
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=toggle_chunking, args=(100,)) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent config updates caused errors: {errors}"

    def test_concurrent_read_write_consistency(self):
        """Readers should see valid boolean values, never partial state."""
        from src.config.context import get_runtime_state

        state = get_runtime_state()
        state.page_classification_enabled = True
        errors: list[Exception] = []

        def writer():
            for i in range(200):
                state.page_classification_enabled = i % 2 == 0

        def reader():
            for _ in range(200):
                val = state.page_classification_enabled
                if not isinstance(val, bool):
                    errors.append(TypeError(f"Expected bool, got {type(val)}"))

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Readers saw non-boolean values: {errors}"


class TestVectorStoreInitConcurrency:
    """Verify vector store initialization uses proper locking."""

    def test_concurrent_initialize_no_duplicate_builds(self, tmp_path, monkeypatch):
        """Multiple threads calling initialize_runtime_index should not crash."""
        build_counts = {"count": 0}
        lock = threading.Lock()

        # Patch the run_ingestion delegate to count invocations
        import src.rag.index as index_mod

        class _FakeVectorStore:
            def __init__(self):
                self.documents = {"contents": [], "index_metadata": {}}
                self.last_indexing_stats = {}

            def clear(self):
                self.documents = {"contents": [], "index_metadata": {}}
                self.last_indexing_stats = {}

        fake_store = _FakeVectorStore()
        monkeypatch.setattr(index_mod, "get_vector_store", lambda: fake_store)

        class _FakeIngestionResult:
            def to_stats(self):
                return {
                    "attempted": 0,
                    "inserted": 0,
                    "skipped_duplicate_content": 0,
                    "embedding_stats": {},
                }

        def counting_run_ingestion(config):
            with lock:
                build_counts["count"] += 1
            fake_store.documents["contents"] = ["chunk-1"]
            fake_store.last_indexing_stats = {"inserted": 1}
            # Simulate slow build to increase contention
            time.sleep(0.05)
            return _FakeIngestionResult()

        monkeypatch.setattr(index_mod, "run_ingestion", counting_run_ingestion)

        # Reset init state
        from src.config.context import get_runtime_state

        get_runtime_state().reset_vector_store_state()

        errors: list[Exception] = []

        def init_store():
            try:
                index_mod.initialize_runtime_index()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=init_store) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent init errors: {errors}"
        assert build_counts["count"] == 1


class TestDiversityConcurrency:
    """Verify _diversify_results is safe under concurrent calls."""

    def test_concurrent_diversify_calls(self):
        """Multiple threads calling _diversify_results should not interfere."""
        from src.rag.diversification import diversify_results

        results = [
            {
                "id": f"doc_{i}",
                "content": f"Content for document {i}",
                "source": f"source_{i % 3}",
                "page": i % 5,
                "combined_score": 1.0 - i * 0.01,
            }
            for i in range(20)
        ]

        errors: list[Exception] = []
        all_outputs: list[list[dict]] = []

        def diversify():
            try:
                output = diversify_results(
                    results,
                    top_k=5,
                    max_chunks_per_source_page=2,
                    max_chunks_per_source=3,
                )
                all_outputs.append(output)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=diversify) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent diversify errors: {errors}"
        # All outputs should be identical (pure function with same inputs)
        for output in all_outputs[1:]:
            assert len(output) == len(all_outputs[0])
            assert [d["id"] for d in output] == [d["id"] for d in all_outputs[0]]
