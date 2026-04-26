from types import SimpleNamespace

from src.services.rag_service import RAGService


class _FakeVectorStoreService:
    def search(self, **kwargs):
        del kwargs
        return [
            {
                "id": "doc-1",
                "content": "LDL guidance content",
                "source": "guideline.pdf",
                "page": 1,
                "metadata": {"source_type": "pdf"},
            }
        ]


def test_rag_service_retrieve_context_uses_result_dicts_for_formatting(monkeypatch):
    monkeypatch.setattr(
        "src.rag.runtime._resolve_retrieval_config",
        lambda _overrides: SimpleNamespace(
            overfetch_multiplier=2,
            search_mode="rrf_hybrid",
            mmr_lambda=0.75,
            max_chunks_per_source_page=2,
            max_chunks_per_source=3,
            enable_diversification=True,
            reranking_mode="both",
            enable_medical_expansion=False,
            medical_expansion_provider="noop",
        ),
    )
    monkeypatch.setattr(
        "src.rag.runtime._prepare_expanded_queries",
        lambda _query, **_kwargs: (["query"], []),
    )
    monkeypatch.setattr(
        "src.rag.runtime._diversify_results",
        lambda results, **_kwargs: results,
    )
    monkeypatch.setattr(
        "src.rag.runtime._build_retrieved_documents",
        lambda _results: ["placeholder"],
    )

    captured = {}

    def _fake_build_context_and_sources(results):
        captured["results"] = results
        return "context text", ["guideline.pdf page 1"], []

    monkeypatch.setattr(
        "src.rag.formatting.build_context_and_sources",
        _fake_build_context_and_sources,
    )

    service = RAGService(vector_store_service=_FakeVectorStoreService())
    payload = service.retrieve_context("What is LDL?", top_k=1)

    assert payload["context"] == "context text"
    assert payload["sources"] == ["guideline.pdf page 1"]
    assert payload["retrieved_documents"] == ["placeholder"]
    assert captured["results"][0]["id"] == "doc-1"
    assert "content" in captured["results"][0]
