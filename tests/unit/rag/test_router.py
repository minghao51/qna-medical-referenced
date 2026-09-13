from src.rag.query_understanding.classifier import QueryClassification, QueryType
from src.rag.query_understanding.router import (
    RetrievalParams,
    RetrievalRoute,
    RetrievalRouter,
    get_retrieval_params_for_query,
    get_retrieval_router,
    route_retrieval,
)


def _classification(query_type: QueryType, confidence: float = 0.9, reasoning: str = "test"):
    return QueryClassification(query_type=query_type, confidence=confidence, reasoning=reasoning)


class TestRetrievalParams:
    def test_defaults(self):
        params = RetrievalParams()
        assert params.overfetch_multiplier == 4
        assert params.max_chunks_per_source_page == 2
        assert params.mmr_lambda == 0.75
        assert params.enable_diversification is True
        assert params.search_mode == "rrf_hybrid"
        assert params.similarity_threshold is None
        assert params.min_chunks == 3
        assert params.enable_multi_source is False


class TestRetrievalRouter:
    def test_route_returns_retrieval_route(self):
        router = RetrievalRouter()
        route = router.route(_classification(QueryType.DEFINITION))
        assert isinstance(route, RetrievalRoute)
        assert isinstance(route.params, RetrievalParams)
        assert "definition" in route.reasoning.lower()

    def test_route_definition_params(self):
        router = RetrievalRouter()
        route = router.route(_classification(QueryType.DEFINITION))
        assert route.params.similarity_threshold == 0.6
        assert route.params.overfetch_multiplier == 2
        assert route.suggested_post_processing == []

    def test_route_comparison_adds_contrast_post_processing(self):
        router = RetrievalRouter()
        route = router.route(_classification(QueryType.COMPARISON))
        assert "explicit_contrast" in route.suggested_post_processing
        assert route.params.enable_multi_source is True

    def test_route_reference_range_adds_table_post_processing(self):
        router = RetrievalRouter()
        route = router.route(_classification(QueryType.REFERENCE_RANGE))
        assert "prioritize_tables" in route.suggested_post_processing

    def test_route_complex_adds_multi_query_decomposition(self):
        router = RetrievalRouter()
        route = router.route(_classification(QueryType.COMPLEX))
        assert "multi_query_decomposition" in route.suggested_post_processing
        assert route.params.overfetch_multiplier == 6
        assert route.params.enable_multi_source is True

    def test_route_treatment_has_no_post_processing(self):
        router = RetrievalRouter()
        route = router.route(_classification(QueryType.TREATMENT))
        assert route.suggested_post_processing == []

    def test_route_symptom_query(self):
        router = RetrievalRouter()
        route = router.route(_classification(QueryType.SYMPTOM_QUERY))
        assert route.params.similarity_threshold == 0.55
        assert route.params.min_chunks == 4

    def test_route_risk_factor(self):
        router = RetrievalRouter()
        route = router.route(_classification(QueryType.RISK_FACTOR))
        assert route.params.min_chunks == 4
        assert route.params.similarity_threshold is None

    def test_route_follow_up(self):
        router = RetrievalRouter()
        route = router.route(_classification(QueryType.FOLLOW_UP))
        assert route.params.overfetch_multiplier == 3

    def test_custom_params_override(self):
        custom = {QueryType.DEFINITION: RetrievalParams(overfetch_multiplier=99)}
        router = RetrievalRouter(custom_params=custom)
        route = router.route(_classification(QueryType.DEFINITION))
        assert route.params.overfetch_multiplier == 99

    def test_custom_params_do_not_affect_other_types(self):
        custom = {QueryType.DEFINITION: RetrievalParams(overfetch_multiplier=99)}
        router = RetrievalRouter(custom_params=custom)
        route = router.route(_classification(QueryType.COMPARISON))
        assert route.params.overfetch_multiplier == 5

    def test_all_query_types_have_params(self):
        router = RetrievalRouter()
        for qt in QueryType:
            route = router.route(_classification(qt))
            assert isinstance(route.params, RetrievalParams)

    def test_reasoning_includes_query_type(self):
        router = RetrievalRouter()
        route = router.route(
            _classification(QueryType.TREATMENT, reasoning="user asked about meds")
        )
        assert "treatment" in route.reasoning
        assert "user asked about meds" in route.reasoning


class TestGetRetrievalOptions:
    def test_returns_dict_with_expected_keys(self):
        router = RetrievalRouter()
        opts = router.get_retrieval_options(_classification(QueryType.DEFINITION))
        assert "overfetch_multiplier" in opts
        assert "max_chunks_per_source_page" in opts
        assert "max_chunks_per_source" in opts
        assert "mmr_lambda" in opts
        assert "enable_diversification" in opts
        assert "search_mode" in opts

    def test_does_not_include_similarity_threshold(self):
        router = RetrievalRouter()
        opts = router.get_retrieval_options(_classification(QueryType.DEFINITION))
        assert "similarity_threshold" not in opts
        assert "min_chunks" not in opts


class TestGetRetrievalRouter:
    def test_returns_router_instance(self):
        router = get_retrieval_router()
        assert isinstance(router, RetrievalRouter)

    def test_with_custom_params(self):
        custom = {QueryType.TREATMENT: RetrievalParams(overfetch_multiplier=50)}
        router = get_retrieval_router(custom_params=custom)
        route = router.route(_classification(QueryType.TREATMENT))
        assert route.params.overfetch_multiplier == 50


class TestGetRetrievalParamsForQuery:
    def test_with_precomputed_classification(self):
        classification = _classification(QueryType.COMPARISON)
        result = get_retrieval_params_for_query("any query", classification=classification)
        assert result["enable_diversification"] is True
        assert result["overfetch_multiplier"] == 5


class TestRouteRetrieval:
    def test_with_precomputed_classification(self):
        classification = _classification(QueryType.COMPLEX)
        route = route_retrieval("any query", classification=classification)
        assert isinstance(route, RetrievalRoute)
        assert "multi_query_decomposition" in route.suggested_post_processing
