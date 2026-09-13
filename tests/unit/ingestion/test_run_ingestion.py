"""Unit tests for the run_ingestion library entry (roadmap P3.2)."""

from pathlib import Path
from typing import Any

from src.ingestion import pipeline as ingestion_pipeline
from src.ingestion.pipeline import (
    IngestionRunConfig,
    _config_signature,
    _get_cached_driver,
    run_ingestion,
)


def _config(**overrides: Any) -> IngestionRunConfig:
    defaults: dict[str, Any] = {"project_root": Path("/tmp/proj")}
    defaults.update(overrides)
    return IngestionRunConfig(**defaults)


class TestDriverCache:
    def test_same_config_reuses_cached_driver(self, monkeypatch):
        built = []

        def fake_builder(**kwargs):
            driver = object()
            built.append(driver)
            return driver

        monkeypatch.setattr(ingestion_pipeline, "build_ingestion_pipeline", fake_builder)
        ingestion_pipeline._DRIVER_CACHE["driver"] = None
        ingestion_pipeline._DRIVER_CACHE["signature"] = None

        first = _get_cached_driver(_config())
        second = _get_cached_driver(_config())

        assert first is second
        assert len(built) == 1

    def test_different_config_rebuilds_driver(self, monkeypatch):
        built = []

        def fake_builder(**kwargs):
            driver = object()
            built.append(driver)
            return driver

        monkeypatch.setattr(ingestion_pipeline, "build_ingestion_pipeline", fake_builder)
        ingestion_pipeline._DRIVER_CACHE["driver"] = None
        ingestion_pipeline._DRIVER_CACHE["signature"] = None

        first = _get_cached_driver(_config())
        second = _get_cached_driver(_config(enable_hype=True))

        assert first is not second
        assert len(built) == 2

    def test_signature_ignores_hype_config_dict_ordering(self):
        a = _config(hype_config={"sample_rate": 0.1, "max_chunks": 5, "questions_per_chunk": 2})
        b = _config(hype_config={"questions_per_chunk": 2, "max_chunks": 5, "sample_rate": 0.1})

        assert _config_signature(a) == _config_signature(b)


class TestIngestionRunConfigFromRuntimeState:
    def test_maps_indexing_features_overrides(self, monkeypatch):
        monkeypatch.setattr(
            "src.ingestion.indexing.factory.get_vector_store_runtime_config",
            lambda: {
                "indexing_features": {
                    "enable_hype": True,
                    "hype_sample_rate": 0.5,
                    "hype_max_chunks": 7,
                    "hype_questions_per_chunk": 3,
                    "enable_keyword_extraction": True,
                    "keyword_extraction_sample_rate": 0.25,
                    "keyword_extraction_max_chunks": 9,
                }
            },
        )

        config = IngestionRunConfig.from_runtime_state(force_rebuild=True, force_html_convert=True)

        assert config.skip_download is True
        assert config.force_rebuild is True
        assert config.force_html_convert is True
        assert config.enable_hype is True
        assert config.enable_keyword_extraction is True
        assert config.enable_chunk_summaries is False
        assert config.hype_config == {
            "sample_rate": 0.5,
            "max_chunks": 7,
            "questions_per_chunk": 3,
        }
        assert config.enrichment_config == {"sample_rate": 0.25, "max_chunks": 9}

    def test_empty_features_fall_back_to_settings_defaults(self, monkeypatch):
        monkeypatch.setattr(
            "src.ingestion.indexing.factory.get_vector_store_runtime_config",
            dict,
        )
        from src.config import PROJECT_ROOT, settings

        config = IngestionRunConfig.from_runtime_state()

        assert config.project_root == PROJECT_ROOT
        assert config.skip_download is True
        assert config.force_rebuild is False
        assert config.force_html_convert is False
        assert config.enable_hype is settings.hype.enabled
        assert config.enable_keyword_extraction is settings.enrichment.enable_keyword_extraction
        assert config.hype_config == {
            "sample_rate": settings.hype.sample_rate,
            "max_chunks": settings.hype.max_chunks,
            "questions_per_chunk": settings.hype.questions_per_chunk,
        }


class TestRunIngestionResultMapping:
    def test_maps_dag_results_to_stats(self, monkeypatch):
        class _FakeDriver:
            def execute(self, final_vars):
                return {
                    "write_silver_documents": {"pdf_count": 2, "markdown_count": 3},
                    "write_gold_chunks": {"chunk_count": 11},
                    "write_reference_data": {"reference_count": 4},
                    "write_enriched_chunks": {"enriched_count": 11},
                    "hype_questions": {"c1": ["q1"], "c2": ["q2", "q3"]},
                    "embed_chunks": [
                        {"attempted": 15, "inserted": 13, "skipped_duplicate_content": 2}
                    ],
                }

        monkeypatch.setattr(ingestion_pipeline, "_get_cached_driver", lambda config: _FakeDriver())

        result = run_ingestion(_config())

        assert result.attempted == 15
        assert result.inserted == 13
        assert result.skipped_duplicate_content == 2
        assert result.pdf_document_count == 2
        assert result.markdown_document_count == 3
        assert result.reference_document_count == 4
        assert result.chunk_count == 11
        assert result.hype_chunk_count == 2
        assert result.enriched_chunk_count == 11
        stats = result.to_stats()
        assert set(stats) == {
            "attempted",
            "inserted",
            "skipped_duplicate_content",
            "build_elapsed_ms",
            "pdf_document_count",
            "markdown_document_count",
            "reference_document_count",
            "chunk_count",
            "hype_chunk_count",
            "enriched_chunk_count",
        }
