import importlib


def _import_enrich_module():
    return importlib.import_module("src.ingestion.components.04_enrich")


class TestHypeQuestionsPath:
    def test_returns_expected_path(self):
        ec = _import_enrich_module()
        assert ec.hype_questions_path("/gold") == "/gold/hype_questions.parquet"


class TestKeywordExtractionsPath:
    def test_returns_expected_path(self):
        ec = _import_enrich_module()
        assert ec.keyword_extractions_path("/gold") == "/gold/keyword_extractions.parquet"


class TestSummariesPath:
    def test_returns_expected_path(self):
        ec = _import_enrich_module()
        assert ec.summaries_path("/gold") == "/gold/summaries.parquet"


class TestApplyHypeQuestions:
    def test_empty_chunks_returns_unchanged(self):
        ec = _import_enrich_module()
        assert ec.apply_hype_questions([], {"c1": ["q1"]}) == []

    def test_empty_hype_returns_chunks_unchanged(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "text"}]
        assert ec.apply_hype_questions(chunks, {}) == chunks

    def test_both_empty(self):
        ec = _import_enrich_module()
        assert ec.apply_hype_questions([], {}) == []

    def test_applies_matching_questions(self):
        ec = _import_enrich_module()
        chunks = [
            {"id": "c1", "content": "text1"},
            {"id": "c2", "content": "text2"},
        ]
        hype = {"c1": ["What is X?", "How does Y work?"]}
        result = ec.apply_hype_questions(chunks, hype)
        assert result[0]["metadata"]["hypothetical_questions"] == ["What is X?", "How does Y work?"]
        assert "hypothetical_questions" not in result[1].get("metadata", {})

    def test_preserves_existing_metadata(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t", "metadata": {"existing": "val"}}]
        hype = {"c1": ["q1"]}
        result = ec.apply_hype_questions(chunks, hype)
        assert result[0]["metadata"]["existing"] == "val"
        assert result[0]["metadata"]["hypothetical_questions"] == ["q1"]


class TestApplyKeywordExtractions:
    def test_empty_chunks(self):
        ec = _import_enrich_module()
        assert ec.apply_keyword_extractions([], {"c1": {"keywords": ["k"]}}) == []

    def test_empty_extractions(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t"}]
        assert ec.apply_keyword_extractions(chunks, {}) == chunks

    def test_applies_keywords(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t"}]
        kw = {"c1": {"keywords": ["diabetes", "glucose"]}}
        result = ec.apply_keyword_extractions(chunks, kw)
        assert result[0]["metadata"]["extracted_keywords"] == ["diabetes", "glucose"]

    def test_non_matching_id_is_skipped(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t"}]
        kw = {"c99": {"keywords": ["x"]}}
        result = ec.apply_keyword_extractions(chunks, kw)
        assert "extracted_keywords" not in result[0].get("metadata", {})


class TestApplySummaries:
    def test_empty_chunks(self):
        ec = _import_enrich_module()
        assert ec.apply_summaries([], {"c1": {"summary": "s"}}) == []

    def test_empty_summaries(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t"}]
        assert ec.apply_summaries(chunks, {}) == chunks

    def test_applies_summaries(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "long text"}]
        summaries = {"c1": {"summary": "A short summary."}}
        result = ec.apply_summaries(chunks, summaries)
        assert result[0]["metadata"]["summary"] == "A short summary."

    def test_missing_summary_key_defaults_empty(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t"}]
        summaries = {"c1": {}}
        result = ec.apply_summaries(chunks, summaries)
        assert result[0]["metadata"]["summary"] == ""
