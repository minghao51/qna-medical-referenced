from types import SimpleNamespace

from src.evals import pipeline_assessment as pa


class _Doc:
    def __init__(self, **kwargs):
        self._data = kwargs

    def model_dump(self):
        return dict(self._data)


class _Trace:
    def __init__(self, docs, total_time_ms=100, score_weights=None):
        self.retrieval = SimpleNamespace(documents=docs, score_weights=score_weights or {})
        self.total_time_ms = total_time_ms

    def model_dump(self):
        return {
            "retrieval": {"documents": [d.model_dump() for d in self.retrieval.documents]},
            "total_time_ms": self.total_time_ms,
        }


def test_evaluate_retrieval_reports_dedup_and_unique_source_metrics(monkeypatch):
    def fake_retrieve_context_with_trace(query: str, top_k: int = 5, retrieval_options=None):
        docs = [
            _Doc(
                id="c1",
                content="LDL target 1.8 mmol/L secondary prevention",
                source="lipid.pdf",
                page=2,
            ),
            _Doc(
                id="c1",
                content="LDL target 1.8 mmol/L secondary prevention",
                source="lipid.pdf",
                page=2,
            ),
            _Doc(id="c2", content="More lipid info", source="lipid.pdf", page=3),
        ]
        return (
            "ctx",
            ["lipid.pdf page 2", "lipid.pdf page 2", "lipid.pdf page 3"],
            _Trace(docs, total_time_ms=120),
        )

    import src.rag.runtime as runtime

    monkeypatch.setattr(runtime, "retrieve_context_with_trace", fake_retrieve_context_with_trace)

    rows, agg = pa.evaluate_retrieval(
        [
            {
                "query_id": "q1",
                "query": "LDL target",
                "expected_sources": ["lipid"],
                "expected_source_types": ["pdf"],
                "expected_keywords": ["LDL", "1.8"],
                "expected_chunk_id": "c1",
                "evidence_phrase": "1.8 mmol/L",
                "query_category": "threshold_comparison",
                "task_type": "pdf_guideline",
                "label_confidence": "high",
            }
        ],
        top_k=3,
        retrieval_options={"search_mode": "hybrid", "enable_diversification": True},
    )

    assert len(rows) == 1
    assert rows[0]["metrics"]["exact_chunk_hit"] == 1.0
    assert agg["duplicate_doc_ratio_mean"] > 0
    assert agg["dedup_hit_rate_at_k"] == 1.0
    assert "unique_source_precision_at_k" in agg
    assert agg["retrieval_options"]["search_mode"] == "hybrid"
    assert agg["by_expected_source_type"]["pdf"]["query_count"] == 1
    assert agg["by_query_category"]["threshold_comparison"]["exact_chunk_hit_rate"] == 1.0
    assert agg["by_task_type"]["pdf_guideline"]["evidence_hit_rate"] == 1.0


def test_evaluate_retrieval_reports_hyde_metrics(monkeypatch):
    """Test that HyDe metrics are tracked in retrieval evaluation."""

    def fake_retrieve_hyde(query: str, top_k: int = 5, retrieval_options=None):
        docs = [
            _Doc(
                id="c1",
                content="LDL target 1.8 mmol/L secondary prevention",
                source="lipid.pdf",
                page=2,
            ),
        ]
        score_weights = {
            "hyde_enabled": True,
            "hyde_max_length": 200,
            "query_embedding_timing_ms": 50,
        }
        return (
            "ctx",
            ["lipid.pdf page 2"],
            _Trace(docs, total_time_ms=120, score_weights=score_weights),
        )

    import src.rag.runtime as runtime

    monkeypatch.setattr(runtime, "retrieve_context_with_trace", fake_retrieve_hyde)

    rows, agg = pa.evaluate_retrieval(
        [
            {
                "query_id": "q1",
                "query": "LDL target",
                "expected_sources": ["lipid"],
                "expected_source_types": ["pdf"],
                "expected_keywords": ["LDL", "1.8"],
                "expected_chunk_id": "c1",
                "evidence_phrase": "1.8 mmol/L",
            }
        ],
        top_k=3,
    )

    assert len(rows) == 1
    assert rows[0]["metrics"]["hyde_enabled"] is True
    assert agg["hyde_enabled"] is True
    assert agg["hyde_queries_count"] == 1
    assert agg["hyde_hit_rate"] is not None
    assert agg["hyde_mrr"] is not None
    assert agg["hyde_source_hit_rate"] is not None


def test_evaluate_retrieval_reports_no_hyde_when_disabled(monkeypatch):
    """Test that HyDe metrics are not set when HyDe is disabled."""

    def fake_retrieve_no_hyde(query: str, top_k: int = 5, retrieval_options=None):
        docs = [
            _Doc(
                id="c1",
                content="LDL target 1.8 mmol/L secondary prevention",
                source="lipid.pdf",
                page=2,
            ),
        ]
        score_weights = {
            "hyde_enabled": False,
            "query_embedding_timing_ms": 50,
        }
        return (
            "ctx",
            ["lipid.pdf page 2"],
            _Trace(docs, total_time_ms=120, score_weights=score_weights),
        )

    import src.rag.runtime as runtime

    monkeypatch.setattr(runtime, "retrieve_context_with_trace", fake_retrieve_no_hyde)

    rows, agg = pa.evaluate_retrieval(
        [
            {
                "query_id": "q1",
                "query": "LDL target",
                "expected_sources": ["lipid"],
                "expected_source_types": ["pdf"],
                "expected_keywords": ["LDL", "1.8"],
                "expected_chunk_id": "c1",
                "evidence_phrase": "1.8 mmol/L",
            }
        ],
        top_k=3,
    )

    assert len(rows) == 1
    assert rows[0]["metrics"]["hyde_enabled"] is False
    assert agg["hyde_enabled"] is False
    assert "hyde_queries_count" in agg
    assert agg["hyde_queries_count"] == 0
    assert agg["hyde_hit_rate"] is None
    assert agg["hyde_mrr"] is None
