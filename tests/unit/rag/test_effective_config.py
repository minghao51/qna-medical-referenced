"""Effective settings, profile/run overlays, and explicit retrieval overrides."""

from types import SimpleNamespace

import pytest

from src.config import context, settings
from src.ingestion.indexing import factory
from src.rag import index, production_profile, runtime
from src.rag.config import get_runtime_retrieval_config, resolve_retrieval_config
from src.usecases.runtime_config import get_runtime_config_view


def _expected_index_metadata() -> dict:
    """Build metadata the no-build readiness gate expects for a frozen index.

    Reuses the production helper so the synthetic store cannot drift from the
    gate it is validated by.
    """
    from src.rag.index import _expected_index_metadata as expected

    return expected()


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch):
    monkeypatch.setattr(context, "_state", context.RuntimeState())
    monkeypatch.setattr(production_profile, "_PROFILE_REGISTRY", {})
    cache = factory.ChromaVectorStoreFactory
    monkeypatch.setattr(cache, "_instance", None)
    monkeypatch.setattr(cache, "_runtime_config", {})
    monkeypatch.setattr(cache, "_runtime_signature_value", None)
    monkeypatch.setattr(settings.hyde, "hyde_enabled", False)
    monkeypatch.setattr(settings.hype, "enabled", False)
    monkeypatch.setattr(settings.retrieval, "enable_reranking", False)
    monkeypatch.setattr(settings.retrieval, "medical_expansion_enabled", False)
    monkeypatch.setattr(settings.enrichment, "enable_keyword_extraction", False)
    monkeypatch.setattr(settings.enrichment, "enable_chunk_summaries", False)


@pytest.mark.parametrize(
    ("name", "group", "field"),
    [
        ("enable_hyde", "hyde", "hyde_enabled"),
        ("enable_hype", "hype", "enabled"),
        ("enable_medical_expansion", "retrieval", "medical_expansion_enabled"),
        ("enable_reranking", "retrieval", "enable_reranking"),
        ("enable_keyword_extraction", "enrichment", "enable_keyword_extraction"),
        ("enable_chunk_summaries", "enrichment", "enable_chunk_summaries"),
    ],
)
@pytest.mark.parametrize("source", ["settings", "profile"])
def test_explicit_false_wins_while_omission_and_none_inherit(
    monkeypatch, name, group, field, source
):
    if source == "settings":
        monkeypatch.setattr(getattr(settings, group), field, True)
    else:
        index.configure_runtime_for_experiment({"retrieval": {name: True}})

    assert getattr(resolve_retrieval_config(), name) is True
    assert getattr(resolve_retrieval_config({name: None}), name) is True
    assert getattr(resolve_retrieval_config({name: False}), name) is False


def test_profile_is_copied_and_explicit_request_options_win():
    retrieval = {"top_k": 2, "overfetch_multiplier": 3, "enable_reranking": True}
    index.configure_runtime_for_experiment({"retrieval": retrieval})
    retrieval["top_k"] = 99

    cfg = resolve_retrieval_config({"enable_reranking": False, "mmr_lambda": 0.0})
    assert cfg.top_k == 2
    assert cfg.overfetch_multiplier == 3
    assert cfg.enable_reranking is False
    assert cfg.mmr_lambda == 0.0
    assert get_runtime_config_view()["retrieval"]["top_k"] == 2


@pytest.mark.parametrize(
    "name", ["overfetch_multiplier", "max_chunks_per_source_page", "max_chunks_per_source"]
)
def test_zero_count_is_clamped_not_replaced_by_static_defaults(name):
    assert getattr(resolve_retrieval_config({name: 0}), name) == 1


def test_settings_reranking_mode_and_hyde_length_are_inherited(monkeypatch):
    monkeypatch.setattr(settings.retrieval, "reranking_mode", "mmr")
    monkeypatch.setattr(settings.hyde, "hyde_max_length", 321)
    cfg = resolve_retrieval_config()
    assert cfg.reranking_mode == "mmr"
    assert cfg.hyde_max_length == 321


def test_experiment_defaults_do_not_inherit_a_previously_applied_run():
    from src.experiments.config import _base_defaults

    index.configure_runtime_for_experiment({"retrieval": {"overfetch_multiplier": 9}})
    assert _base_defaults()["retrieval"]["overfetch_multiplier"] == 4


def test_run_replaces_prior_profile_and_reset_clears_overrides():
    production_profile._PROFILE_REGISTRY["synthetic"] = {
        "retrieval": {"top_k": 2, "enable_reranking": True}
    }
    assert production_profile.apply_production_profile("synthetic") is True
    assert get_runtime_config_view()["production_profile"] == "synthetic"
    index.configure_runtime_for_experiment({"retrieval": {"top_k": 3}})
    assert get_runtime_config_view()["production_profile"] is None
    assert resolve_retrieval_config().top_k == 3
    assert resolve_retrieval_config().enable_reranking is False
    context.reset_runtime_state()
    assert resolve_retrieval_config().top_k == 5
    assert get_runtime_config_view()["production_profile"] is None


def test_unknown_requested_profile_does_not_claim_to_be_applied(monkeypatch):
    monkeypatch.setattr(settings.production, "production_profile", "not-a-profile")
    assert production_profile.apply_production_profile("not-a-profile") is False
    assert get_runtime_config_view()["production_profile"] is None


def test_serving_profile_preserves_the_configured_collection_name(monkeypatch):
    monkeypatch.setattr(settings.storage, "collection_name", "medical_docs")

    assert production_profile.apply_production_profile("baseline") is True

    assert get_runtime_config_view()["production_profile"] == "baseline"
    assert (
        factory.ChromaVectorStoreFactory.get_runtime_config()["collection_name"] == "medical_docs"
    )

    # Experiment runs are unchanged: the registered profile keeps its derived
    # suffixed collection and an experiment run still applies it.
    registered = production_profile.get_production_profile("baseline")
    assert registered["embedding_index"]["collection_name_suffix"] == "comprehensive_ablation"
    index.configure_runtime_for_experiment(registered)
    assert (
        factory.ChromaVectorStoreFactory.get_runtime_config()["collection_name"]
        == "medical_docs_comprehensive_ablation"
    )


@pytest.mark.parametrize(
    ("provider", "custom_litellm", "expected"),
    [
        ("qwen", "", "synthetic-qwen"),
        ("gemini", "", "synthetic-gemini"),
        ("litellm", "", "openrouter/synthetic-router"),
        ("litellm", "custom/model", "custom/model"),
    ],
)
def test_config_view_reports_configured_provider_model(
    monkeypatch, provider, custom_litellm, expected
):
    monkeypatch.setattr(settings.llm, "provider", provider)
    monkeypatch.setattr(settings.llm, "model_name", "synthetic-qwen")
    monkeypatch.setattr(settings.llm, "gemini_model_name", "synthetic-gemini")
    monkeypatch.setattr(settings.llm, "openrouter_model", "synthetic-router")
    monkeypatch.setattr(settings.llm, "litellm_model", custom_litellm)
    assert get_runtime_config_view()["llm"]["model_name"] == expected


@pytest.fixture
def retrieval_leaves(monkeypatch):
    seen = SimpleNamespace(searches=[], reranks=[], hype=[])

    class Store:
        def __init__(self, **kwargs):
            assert "indexing_features" not in kwargs
            self.documents = {
                "contents": ["synthetic evidence"],
                "index_metadata": _expected_index_metadata(),
            }
            self.last_indexing_stats = {}

        def similarity_search_with_trace(self, query, *, top_k, search_mode):
            seen.searches.append((query, top_k, search_mode))
            results = [
                {
                    "id": str(i),
                    "content": "synthetic evidence",
                    "source": f"synthetic-{i}.txt",
                    "combined_score": 1.0 - i / 10,
                    "rank": i + 1,
                }
                for i in range(3)
            ]
            return results, {"result_count": 3, "score_weights": {}}

        def search_hypothetical_questions(self, query, *, limit):
            seen.hype.append(query)
            return ["synthetic indexed question"]

    class Reranker:
        def rerank(self, *, query, results, top_k, min_score):
            seen.reranks.append((query, top_k, min_score))
            return SimpleNamespace(
                reranked_results=results,
                model_name="synthetic-reranker",
                timing_ms=0,
                candidates_count=len(results),
                output_count=len(results),
                filtered_out_count=0,
            )

    monkeypatch.setattr(factory, "ChromaVectorStore", Store)
    monkeypatch.setattr("src.rag.reranker.get_reranker", Reranker)
    return seen


@pytest.mark.asyncio
async def test_real_builtin_profile_executes_reranker_and_explicit_disable_skips_it(
    retrieval_leaves,
):
    assert production_profile.apply_production_profile("baseline_cross_encoder") is True
    _, sources, trace = await runtime.retrieve_context_with_trace_async("synthetic query", top_k=2)
    assert len(sources) == 2
    assert retrieval_leaves.reranks
    assert trace.retrieval.score_weights["enable_reranking"] is True
    retrieval_leaves.reranks.clear()
    await runtime.retrieve_context_with_trace_async(
        "synthetic query", top_k=2, retrieval_options={"enable_reranking": False}
    )
    assert retrieval_leaves.reranks == []


@pytest.mark.parametrize("async_path", [False, True])
@pytest.mark.asyncio
async def test_runtime_inherits_top_k_and_hype_but_explicit_arguments_win(
    retrieval_leaves, async_path
):
    import asyncio

    index.configure_runtime_for_experiment(
        {"retrieval": {"top_k": 2, "overfetch_multiplier": 3, "enable_hype": True}}
    )
    retrieve = (
        runtime.retrieve_context_with_trace_async
        if async_path
        else runtime.retrieve_context_with_trace
    )
    if async_path:
        _, sources, trace = await retrieve("synthetic query")
        first_search_count = len(retrieval_leaves.searches)
        _, overridden, override_trace = await retrieve(
            "synthetic query", top_k=1, retrieval_options={"enable_hype": False, "top_k": 3}
        )
    else:
        _, sources, trace = await asyncio.to_thread(retrieve, "synthetic query")
        first_search_count = len(retrieval_leaves.searches)
        _, overridden, override_trace = await asyncio.to_thread(
            retrieve,
            "synthetic query",
            top_k=1,
            retrieval_options={"enable_hype": False, "top_k": 3},
        )
    assert len(sources) == trace.retrieval.top_k == 2
    assert len(overridden) == override_trace.retrieval.top_k == 1
    assert retrieval_leaves.hype == ["synthetic query"]
    assert first_search_count > 0
    assert len(retrieval_leaves.searches) > first_search_count
    assert all(entry[1] == 6 for entry in retrieval_leaves.searches[:first_search_count])
    assert all(entry[1] == 3 for entry in retrieval_leaves.searches[first_search_count:])
    assert get_runtime_retrieval_config()["top_k"] == 2


def test_query_routing_cannot_override_an_explicit_disable(monkeypatch):
    index.configure_runtime_for_experiment({"retrieval": {"enable_query_understanding": True}})
    monkeypatch.setattr(
        "src.rag.query_understanding.classifier.classify_query",
        lambda query: SimpleNamespace(
            query_type=SimpleNamespace(value="synthetic"), confidence=1.0
        ),
    )
    monkeypatch.setattr(
        "src.rag.query_understanding.router.get_retrieval_params_for_query",
        lambda *args: {"enable_diversification": True, "overfetch_multiplier": 9},
    )
    _, _, cfg, _ = runtime._prepare_query(
        "synthetic query", {"enable_diversification": False, "overfetch_multiplier": 2}
    )
    assert cfg.enable_diversification is False
    assert cfg.overfetch_multiplier == 2


def test_runtime_snapshot_copies_new_overlays():
    index.configure_runtime_for_experiment(
        {"retrieval": {"top_k": 2}, "ingestion": {"enable_hype": True}}
    )
    state = context.get_runtime_state()
    snapshot = state.snapshot()
    snapshot["retrieval_overrides"]["top_k"] = 99
    snapshot["indexing_features"]["enable_hype"] = False
    assert state.retrieval_overrides["top_k"] == 2
    assert state.indexing_features["enable_hype"] is True


@pytest.mark.parametrize("async_path", [False, True])
@pytest.mark.asyncio
async def test_empty_query_inherits_top_k_without_initializing(async_path):
    index.configure_runtime_for_experiment({"retrieval": {"top_k": 2}})
    if async_path:
        result = await runtime.retrieve_context_with_trace_async(" ")
    else:
        result = runtime.retrieve_context_with_trace(" ")
    assert result[0] == ""
    assert result[1] == []
    assert result[2].retrieval.top_k == 2
    assert factory.ChromaVectorStoreFactory._instance is None


@pytest.mark.parametrize("async_path", [False, True])
@pytest.mark.parametrize("query", ["", "synthetic query"])
@pytest.mark.asyncio
async def test_explicit_zero_top_k_is_clamped_before_all_return_paths(
    retrieval_leaves, async_path, query
):
    import asyncio

    index.configure_runtime_for_experiment({"retrieval": {"top_k": 2, "overfetch_multiplier": 3}})
    if async_path:
        _, _, trace = await runtime.retrieve_context_with_trace_async(query, top_k=0)
    else:
        _, _, trace = await asyncio.to_thread(runtime.retrieve_context_with_trace, query, top_k=0)
    assert trace.retrieval.top_k == 1
    if query:
        assert retrieval_leaves.searches
        assert all(entry[1] == 3 for entry in retrieval_leaves.searches)
    else:
        assert retrieval_leaves.searches == []
        assert factory.ChromaVectorStoreFactory._instance is None


@pytest.mark.parametrize("async_path", [False, True])
@pytest.mark.parametrize("include_pipeline", [False, True])
@pytest.mark.parametrize("top_k", [None, 1])
@pytest.mark.asyncio
async def test_chat_usecases_inherit_or_override_profile(
    retrieval_leaves, async_path, include_pipeline, top_k
):
    import asyncio
    from contextlib import nullcontext

    from src.usecases.chat import process_chat_message, stream_chat_message

    index.configure_runtime_for_experiment({"retrieval": {"top_k": 2, "overfetch_multiplier": 3}})
    saved = []
    history = SimpleNamespace(
        get_history=lambda session: [],
        turn=lambda session: nullcontext(),
        save_turn=lambda session, message, response: saved.extend(
            [("user", message), ("assistant", response)]
        ),
    )

    class Client:
        model = "synthetic-generation-model"

        def generate(self, *, prompt, context):
            assert "synthetic evidence" in context
            return "synthetic answer"

        async def a_generate_stream(self, *, prompt, context):
            yield self.generate(prompt=prompt, context=context)

    kwargs = {
        "llm_client": Client(),
        "history_store": history,
        "message": "synthetic query",
        "session_id": "synthetic",
        "include_pipeline": include_pipeline,
        "top_k": top_k,
    }
    if async_path:
        events = [event async for event in stream_chat_message(**kwargs)]
        terminal = events[-1][1]
        assert terminal["done"] is True
        sources = terminal["sources"]
        trace = terminal["pipeline"]
    else:
        result = await asyncio.to_thread(process_chat_message, **kwargs)
        sources = result["sources"]
        trace = result["pipeline"]
    effective_k = 2 if top_k is None else top_k
    assert len(sources) == effective_k
    assert all(entry[1] == effective_k * 3 for entry in retrieval_leaves.searches)
    assert [role for role, _ in saved] == ["user", "assistant"]
    if include_pipeline:
        assert trace.retrieval.top_k == effective_k
        assert trace.generation.model == "synthetic-generation-model"
    else:
        assert trace is None


def test_evaluation_adapter_and_runner_preserve_effective_controls(retrieval_leaves):
    from src.evals.assessment.retrieval_eval import evaluate_retrieval
    from src.experiments.config import _base_defaults, build_run_assessment_kwargs

    experiment = _base_defaults()
    experiment["retrieval"].update(
        {
            "top_k": 2,
            "overfetch_multiplier": 3,
            "enable_reranking": True,
            "rerank_score_threshold": 0.25,
        }
    )
    kwargs = build_run_assessment_kwargs(experiment)
    assert kwargs["retrieval_options"]["rerank_score_threshold"] == 0.25
    assert "enable_hype" not in kwargs["retrieval_options"]
    index.configure_runtime_for_experiment(experiment)
    rows, aggregate = evaluate_retrieval(
        [{"query": "synthetic query", "expected_sources": ["synthetic-0.txt"]}],
        top_k=kwargs["top_k"],
        retrieval_options=kwargs["retrieval_options"],
    )
    assert rows[0]["trace"]["retrieval"]["top_k"] == 2
    assert len(rows[0]["retrieved_docs"]) == 2
    assert aggregate["reranking_enabled"] is True
    assert retrieval_leaves.reranks[0][2] == 0.25
    assert all(entry[1] == 6 for entry in retrieval_leaves.searches)
