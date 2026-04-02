from src.evals.assessment.retrieval_eval import reranking_ablation_configs
from src.rag import runtime
from src.rag.runtime import RetrievalDiversityConfig, _should_apply_diversification


def test_should_apply_diversification_matches_reranking_mode():
    assert (
        _should_apply_diversification(
            RetrievalDiversityConfig(enable_diversification=True, reranking_mode="cross_encoder")
        )
        is False
    )
    assert (
        _should_apply_diversification(
            RetrievalDiversityConfig(enable_diversification=True, reranking_mode="mmr")
        )
        is True
    )
    assert (
        _should_apply_diversification(
            RetrievalDiversityConfig(enable_diversification=True, reranking_mode="both")
        )
        is True
    )
    assert (
        _should_apply_diversification(
            RetrievalDiversityConfig(enable_diversification=False, reranking_mode="both")
        )
        is False
    )


def test_reranking_ablation_configs_define_distinct_modes():
    configs = dict(reranking_ablation_configs({"search_mode": "rrf_hybrid"}))

    assert configs["no_reranking"]["enable_diversification"] is False
    assert configs["no_reranking"]["enable_reranking"] is False

    assert configs["cross_encoder_only"]["enable_diversification"] is False
    assert configs["cross_encoder_only"]["enable_reranking"] is True
    assert configs["cross_encoder_only"]["reranking_mode"] == "cross_encoder"

    assert configs["mmr_only"]["enable_diversification"] is True
    assert configs["mmr_only"]["enable_reranking"] is False
    assert configs["mmr_only"]["reranking_mode"] == "mmr"

    assert configs["both_reranking"]["enable_diversification"] is True
    assert configs["both_reranking"]["enable_reranking"] is True
    assert configs["both_reranking"]["reranking_mode"] == "both"


def test_retrieve_context_applies_cross_encoder_without_mmr(monkeypatch):
    monkeypatch.setattr(runtime, "initialize_runtime_index", lambda: None)
    monkeypatch.setattr(runtime, "get_vector_store", lambda: object())
    monkeypatch.setattr(runtime, "_expand_queries", lambda query: [query])
    monkeypatch.setattr(
        runtime,
        "_extend_with_hype_questions",
        lambda vector_store, query, expanded_queries, enable_hype: (expanded_queries, []),
    )
    monkeypatch.setattr(
        runtime,
        "_retrieve_candidates",
        lambda vector_store, query, fetch_k, search_mode, pre_expanded_queries: [
            {
                "id": "a",
                "content": "doc",
                "source": "s1.pdf",
                "page": 1,
                "semantic_score": 1.0,
                "keyword_score": 0.0,
                "combined_score": 1.0,
                "rank": 1,
            }
        ],
    )

    seen: dict[str, object] = {}

    class StubReranker:
        def rerank(self, *, query, results, top_k):
            seen["query"] = query
            seen["results"] = results
            seen["top_k"] = top_k
            return type("StubResult", (), {"reranked_results": results})()

    monkeypatch.setattr("src.rag.reranker.get_reranker", lambda: StubReranker())

    def fake_diversify(results, top_k, **kwargs):
        seen["enable_diversification"] = kwargs["enable_diversification"]
        return results[:top_k]

    monkeypatch.setattr(runtime, "_diversify_results", fake_diversify)
    monkeypatch.setattr(
        runtime,
        "build_context_and_sources",
        lambda results: ("context", ["s1.pdf"], [{"label": "s1.pdf"}]),
    )

    context, sources = runtime.retrieve_context(
        "query",
        top_k=1,
        retrieval_options={"enable_reranking": True, "reranking_mode": "cross_encoder"},
    )

    assert context == "context"
    assert sources == [{"label": "s1.pdf"}]
    assert seen["query"] == "query"
    assert seen["top_k"] == 4
    assert seen["enable_diversification"] is False
