import importlib


def _import_enrich_module():
    return importlib.import_module("src.ingestion.nodes.enrich")


class _FakeClient:
    pass


class TestHypeQuestions:
    def test_disabled_returns_empty(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t"}]
        assert ec.hype_questions(chunks, {"sample_rate": 1.0}, enable_hype=False) == {}

    def test_empty_chunks_returns_empty(self, monkeypatch):
        ec = _import_enrich_module()
        monkeypatch.setattr("src.infra.llm.qwen_client.get_client", lambda: _FakeClient())
        assert ec.hype_questions([], {"sample_rate": 1.0}, enable_hype=True) == {}

    def test_enabled_generates_questions(self, monkeypatch):
        ec = _import_enrich_module()
        recorded = {}

        async def fake_generate(chunks, client, sample_rate, max_chunks, questions_per_chunk):
            recorded["call"] = {
                "chunks": chunks,
                "sample_rate": sample_rate,
                "max_chunks": max_chunks,
                "questions_per_chunk": questions_per_chunk,
            }
            return {"c1": ["What is X?"]}

        monkeypatch.setattr("src.infra.llm.qwen_client.get_client", lambda: _FakeClient())
        monkeypatch.setattr(
            "src.ingestion.steps.hypothetical_questions.generate_hype_questions_for_chunks",
            fake_generate,
        )

        chunks = [{"id": "c1", "content": "text"}]
        config = {"sample_rate": 0.5, "max_chunks": 10, "questions_per_chunk": 3}
        result = ec.hype_questions(chunks, config, enable_hype=True)

        assert result == {"c1": ["What is X?"]}
        assert recorded["call"]["sample_rate"] == 0.5
        assert recorded["call"]["max_chunks"] == 10
        assert recorded["call"]["questions_per_chunk"] == 3


class TestEnrichmentResults:
    def test_both_disabled_returns_empty(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t"}]
        assert (
            ec.enrichment_results(
                chunks,
                {"sample_rate": 1.0},
                enable_keyword_extraction=False,
                enable_chunk_summaries=False,
            )
            == {}
        )

    def test_empty_chunks_returns_empty(self, monkeypatch):
        ec = _import_enrich_module()
        monkeypatch.setattr("src.infra.llm.qwen_client.get_client", lambda: _FakeClient())
        assert (
            ec.enrichment_results(
                [],
                {"sample_rate": 1.0},
                enable_keyword_extraction=True,
                enable_chunk_summaries=True,
            )
            == {}
        )

    def test_single_call_with_both_flags(self, monkeypatch):
        ec = _import_enrich_module()
        recorded = {}

        async def fake_enrich(
            chunks, client, *, enable_keywords, enable_summaries, sample_rate, max_chunks
        ):
            recorded["call"] = {
                "enable_keywords": enable_keywords,
                "enable_summaries": enable_summaries,
                "sample_rate": sample_rate,
                "max_chunks": max_chunks,
                "n_chunks": len(chunks),
            }
            return {"c1": {"keywords": ["diabetes"], "summary": "s"}}

        monkeypatch.setattr("src.infra.llm.qwen_client.get_client", lambda: _FakeClient())
        monkeypatch.setattr("src.ingestion.steps.enrich_chunks.enrich_chunks", fake_enrich)

        chunks = [{"id": "c1", "content": "t"}, {"id": "c2", "content": "t2"}]
        result = ec.enrichment_results(
            chunks,
            {"sample_rate": 0.25, "max_chunks": 7},
            enable_keyword_extraction=True,
            enable_chunk_summaries=True,
        )

        assert result == {"c1": {"keywords": ["diabetes"], "summary": "s"}}
        assert recorded["call"]["enable_keywords"] is True
        assert recorded["call"]["enable_summaries"] is True
        assert recorded["call"]["sample_rate"] == 0.25
        assert recorded["call"]["max_chunks"] == 7
        assert recorded["call"]["n_chunks"] == 2


class TestEnrichedChunks:
    def test_empty_chunks_returns_empty(self):
        ec = _import_enrich_module()
        assert ec.enriched_chunks([], {"c1": ["q"]}, {"c1": {"keywords": ["k"]}}, True, True) == []

    def test_no_results_returns_chunks_unchanged(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t"}]
        assert ec.enriched_chunks(chunks, {}, {}, True, True) == chunks

    def test_applies_hype_inline(self):
        ec = _import_enrich_module()
        chunks = [
            {"id": "c1", "content": "text1"},
            {"id": "c2", "content": "text2"},
        ]
        result = ec.enriched_chunks(
            chunks, {"c1": ["What is X?", "How does Y work?"]}, {}, False, False
        )
        assert result[0]["metadata"]["hypothetical_questions"] == ["What is X?", "How does Y work?"]
        assert "hypothetical_questions" not in result[1].get("metadata", {})

    def test_hype_preserves_existing_metadata(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t", "metadata": {"existing": "val"}}]
        result = ec.enriched_chunks(chunks, {"c1": ["q1"]}, {}, False, False)
        assert result[0]["metadata"]["existing"] == "val"
        assert result[0]["metadata"]["hypothetical_questions"] == ["q1"]

    def test_applies_keyword_and_summary_enrichment(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "long text"}]
        results = {"c1": {"keywords": ["diabetes", "glucose"], "summary": "A short summary."}}
        result = ec.enriched_chunks(chunks, {}, results, True, True)
        assert result[0]["metadata"]["extracted_keywords"] == ["diabetes", "glucose"]
        assert result[0]["metadata"]["chunk_summary"] == "A short summary."
        assert "summary" not in result[0]["metadata"]

    def test_non_matching_id_is_skipped(self):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t"}]
        result = ec.enriched_chunks(chunks, {}, {"c99": {"keywords": ["x"]}}, True, True)
        assert "extracted_keywords" not in result[0].get("metadata", {})


class TestWriteEnrichedChunks:
    def test_empty_list_skips_write(self, tmp_path):
        ec = _import_enrich_module()
        result = ec.write_enriched_chunks([], str(tmp_path))
        assert result["enriched_count"] == 0
        assert not (tmp_path / "enriched_chunks.parquet").exists()

    def test_writes_parquet(self, tmp_path):
        ec = _import_enrich_module()
        chunks = [{"id": "c1", "content": "t", "metadata": {"k": "v"}}]
        result = ec.write_enriched_chunks(chunks, str(tmp_path))
        assert result["enriched_count"] == 1
        assert (tmp_path / "enriched_chunks.parquet").exists()
