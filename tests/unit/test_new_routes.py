import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.app.routes import config, documents, experiments


class TestGetConfig:
    def test_returns_expected_keys(self):
        result = config.get_config()
        assert "retrieval" in result
        assert "ingestion" in result
        assert "enrichment" in result
        assert "llm" in result

    def test_retrieval_has_required_fields(self):
        result = config.get_config()
        retrieval = result["retrieval"]
        assert "search_mode" in retrieval
        assert "enable_diversification" in retrieval
        assert "mmr_lambda" in retrieval
        assert "top_k" in retrieval
        assert "enable_hyde" in retrieval
        assert "enable_reranking" in retrieval

    def test_enrichment_uses_retrieval_cfg_fallbacks(self):
        result = config.get_config()
        assert "enable_keyword_extraction" in result["enrichment"]
        assert "enable_chunk_summaries" in result["enrichment"]

    def test_returns_effective_runtime_config(self, monkeypatch):
        monkeypatch.setattr(
            config,
            "get_runtime_retrieval_config",
            lambda: {
                "search_mode": "semantic_only",
                "enable_diversification": False,
                "mmr_lambda": 0.25,
                "overfetch_multiplier": 7,
                "max_chunks_per_source_page": 1,
                "max_chunks_per_source": 2,
                "top_k": 9,
                "enable_hyde": True,
                "hyde_max_length": 250,
                "enable_hype": True,
                "enable_reranking": True,
                "reranking_mode": "both",
                "enable_medical_expansion": True,
                "medical_expansion_provider": "noop",
                "enable_query_understanding": True,
                "enable_keyword_extraction": True,
                "enable_chunk_summaries": False,
            },
        )

        result = config.get_config()

        assert result["retrieval"]["search_mode"] == "semantic_only"
        assert result["retrieval"]["top_k"] == 9
        assert result["retrieval"]["enable_reranking"] is True
        assert result["enrichment"]["enable_keyword_extraction"] is True
        assert result["enrichment"]["enable_chunk_summaries"] is False


class TestDocuments:
    def test_list_documents_503_when_store_not_initialized(self):
        from src.config.context import get_runtime_state

        get_runtime_state().reset_vector_store_state()
        with pytest.raises(HTTPException) as exc_info:
            documents.list_documents(limit=10, offset=0)
        assert exc_info.value.status_code == 503
        assert "not initialized" in exc_info.value.detail

    def test_list_documents_503_when_wrong_path_format(self, monkeypatch):
        from src.config.context import get_runtime_state

        get_runtime_state().reset_vector_store_state()
        get_runtime_state()._vector_store_initialized = True

        class BrokenStore:
            @property
            def documents(self):
                raise Exception("chroma not available")

        monkeypatch.setattr(documents, "get_vector_store", lambda: BrokenStore())

        with pytest.raises(HTTPException) as exc_info:
            documents.list_documents(limit=10, offset=0)
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "chroma not available"

    def test_get_document_404_when_not_found(self, monkeypatch):
        from src.config.context import get_runtime_state

        get_runtime_state().reset_vector_store_state()
        get_runtime_state()._vector_store_initialized = True

        mock_store = MagicMock()
        mock_store._collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
        monkeypatch.setattr(documents, "get_vector_store", lambda: mock_store)

        with pytest.raises(HTTPException) as exc_info:
            documents.get_document("nonexistent-id")
        assert exc_info.value.status_code == 404


class TestExperiments:
    def test_list_experiments_returns_empty_when_no_files(self, monkeypatch, tmp_path):
        monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", tmp_path / "outputs")

        result = experiments.list_experiments()
        assert "configs" in result
        assert "reports" in result
        assert result["configs"] == []
        assert result["reports"] == []

    def test_list_experiments_parses_reports(self, monkeypatch, tmp_path):
        exp_dir = tmp_path / "experiments"
        exp_dir.mkdir()

        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        report_data = {
            "experiment_name": "exp1",
            "timestamp": "2026-01-01T00:00:00Z",
            "winner": {"name": "variant1"},
            "any_target_met": True,
        }
        (outputs_dir / "exp1_report.json").write_text(json.dumps(report_data), encoding="utf-8")

        monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", exp_dir)
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", outputs_dir)

        result = experiments.list_experiments()
        assert len(result["reports"]) == 1
        assert result["reports"][0]["experiment_name"] == "exp1"
        assert result["reports"][0]["winner"] == "variant1"
        assert result["reports"][0]["any_target_met"] is True

    def test_list_experiments_uses_stable_experiment_id(self, monkeypatch, tmp_path):
        exp_dir = tmp_path / "experiments"
        exp_dir.mkdir()
        yaml_path = exp_dir / "my_exp.yaml"
        yaml_path.write_text("schema_version: 1\n", encoding="utf-8")

        outputs_dir = exp_dir / "outputs"
        outputs_dir.mkdir()
        (outputs_dir / "my_exp_report.json").write_text("{}", encoding="utf-8")

        monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", exp_dir)
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", outputs_dir)
        monkeypatch.setattr(
            experiments,
            "load_experiment_file",
            lambda _path: {
                "metadata": {"name": "Display Name With Spaces", "description": "desc"},
                "variants": [],
                "evaluation": {},
            },
        )

        result = experiments.list_experiments()
        assert len(result["configs"]) == 1
        cfg = result["configs"][0]
        assert cfg["experiment_id"] == "my_exp"
        assert cfg["name"] == "Display Name With Spaces"
        assert cfg["has_results"] is True

    def test_get_experiment_results_404_when_missing(self, monkeypatch, tmp_path):
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", outputs_dir)

        with pytest.raises(HTTPException) as exc_info:
            experiments.get_experiment_results("nonexistent")
        assert exc_info.value.status_code == 404

    def test_get_experiment_config_404_when_missing(self, monkeypatch, tmp_path):
        exp_dir = tmp_path / "experiments"
        exp_dir.mkdir()
        monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", exp_dir)

        with pytest.raises(HTTPException) as exc_info:
            experiments.get_experiment_config("nonexistent")
        assert exc_info.value.status_code == 404
