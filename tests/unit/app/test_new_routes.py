import hashlib
import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from src.app.routes import config, documents, experiments, health
from src.config.context import get_runtime_state


def _make_request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/documents",
        "headers": [],
        "app": FastAPI(),
    }
    request = Request(scope)
    request.state.request_id = "test-request-id"
    return request


class TestGetConfig:
    def test_returns_expected_keys(self):
        req = _make_request()
        req.state.auth = {"role": "admin"}
        result = config.get_config(req)
        assert "retrieval" in result
        assert "ingestion" in result
        assert "enrichment" in result
        assert "llm" in result

    def test_retrieval_has_required_fields(self):
        req = _make_request()
        req.state.auth = {"role": "admin"}
        result = config.get_config(req)
        retrieval = result["retrieval"]
        assert "search_mode" in retrieval
        assert "enable_diversification" in retrieval
        assert "mmr_lambda" in retrieval
        assert "top_k" in retrieval
        assert "enable_hyde" in retrieval
        assert "enable_reranking" in retrieval

    def test_enrichment_uses_retrieval_cfg_fallbacks(self):
        req = _make_request()
        req.state.auth = {"role": "admin"}
        result = config.get_config(req)
        assert "enable_keyword_extraction" in result["enrichment"]
        assert "enable_chunk_summaries" in result["enrichment"]

    def test_returns_effective_runtime_config(self, monkeypatch):
        import src.usecases.runtime_config as runtime_config_usecase

        monkeypatch.setattr(
            runtime_config_usecase,
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
        state = get_runtime_state()
        monkeypatch.setattr(
            state,
            "indexing_features",
            {"enable_keyword_extraction": True, "enable_chunk_summaries": False},
        )

        req = _make_request()
        req.state.auth = {"role": "admin"}
        result = config.get_config(req)

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
            documents.list_documents(request=_make_request(), limit=10, offset=0)
        assert exc_info.value.status_code == 503
        assert "not initialized" in exc_info.value.detail

    def test_list_documents_503_when_wrong_path_format(self, monkeypatch):
        from src.config.context import get_runtime_state

        get_runtime_state().reset_vector_store_state()
        get_runtime_state().set_vector_store_initialized("test-sig")

        class BrokenStore:
            @property
            def documents(self):
                raise Exception("chroma not available")

        monkeypatch.setattr(documents, "get_vector_store", lambda request: BrokenStore())

        req = _make_request()
        req.state.auth = {"role": "admin"}
        with pytest.raises(HTTPException) as exc_info:
            documents.list_documents(request=req, limit=10, offset=0)
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to load documents"

    def test_get_document_forwards_only_safe_source_fields(self, monkeypatch):
        from src.config.context import get_runtime_state

        get_runtime_state().reset_vector_store_state()
        get_runtime_state().set_vector_store_initialized("test-sig")

        store = MagicMock()
        store.get_document_by_id.return_value = {
            "id": "doc-1",
            "content": "excerpt",
            "metadata": {
                "canonical_label": "Lipid guideline",
                "display_label": None,
                "logical_name": "lipid_guideline",
                "source_url": "javascript:alert(1)",
                "domain": "example.org",
                "source_type": "pdf",
                "source_class": "guideline_pdf",
                "page": 4,
            },
            "content_length": 7,
        }
        monkeypatch.setattr(documents, "get_vector_store", lambda request: store)

        req = _make_request()
        req.state.auth = {"role": "admin"}
        result = documents.get_document("doc-1", req)

        assert result["canonical_label"] == "Lipid guideline"
        assert result["logical_name"] == "lipid_guideline"
        assert result["source_url"] is None
        assert result["domain"] == "example.org"
        assert result["source_type"] == "pdf"
        assert result["page"] == 4

    def test_get_document_404_when_not_found(self, monkeypatch):
        from src.config.context import get_runtime_state

        get_runtime_state().reset_vector_store_state()
        get_runtime_state().set_vector_store_initialized("test-sig")

        mock_store = MagicMock()
        mock_store.get_document_by_id.return_value = None
        monkeypatch.setattr(documents, "get_vector_store", lambda request: mock_store)

        req = _make_request()
        req.state.auth = {"role": "admin"}
        with pytest.raises(HTTPException) as exc_info:
            documents.get_document("nonexistent-id", req)
        assert exc_info.value.status_code == 404

    def test_list_documents_returns_compatible_response_shape(self, monkeypatch):
        from src.config.context import get_runtime_state

        get_runtime_state().reset_vector_store_state()
        get_runtime_state().set_vector_store_initialized("test-sig")

        mock_store = MagicMock()
        mock_store.list_documents_paginated.return_value = {
            "total": 2,
            "items": [
                {
                    "id": "doc-1",
                    "source": "a.pdf",
                    "page": 1,
                    "source_type": "pdf",
                    "source_class": "guideline_pdf",
                    "content_type": "paragraph",
                    "content_preview": "preview",
                    "content_length": 7,
                }
            ],
            "source_type_counts": {"pdf": 2},
            "global_source_type_counts": {"pdf": 2, "html": 1},
            "index_metadata": {"version": "v1"},
            "index_identity": "a" * 64,
        }
        monkeypatch.setattr(documents, "get_vector_store", lambda request: mock_store)

        req = _make_request()
        req.state.auth = {"role": "admin"}
        result = documents.list_documents(request=req, limit=50, offset=0, source_type="pdf")

        assert result["total"] == 2
        assert result["offset"] == 0
        assert result["limit"] == 50
        assert isinstance(result["items"], list)
        assert result["items"][0]["id"] == "doc-1"
        assert result["source_type_counts"] == {"pdf": 2}
        assert result["global_source_type_counts"] == {"pdf": 2, "html": 1}
        assert result["index_metadata"] == {"version": "v1"}
        assert result["index_identity"] == "a" * 64


class TestExperiments:
    @staticmethod
    def _request():
        request = _make_request()
        request.state.auth = {"role": "admin"}
        return request

    @staticmethod
    def _report_payload(name: str = "exp1") -> dict:
        return {
            "experiment_name": name,
            "timestamp": "2026-01-01T00:00:00Z",
            "winner": {"name": "variant1"},
            "any_target_met": True,
            "config": {},
            "baseline": {"name": "baseline", "metrics": {}},
            "variants": [],
        }

    def test_requires_authentication_for_all_experiment_routes(self):
        request = _make_request()
        with pytest.raises(HTTPException) as listed:
            experiments.list_experiments(request)
        with pytest.raises(HTTPException) as results:
            experiments.get_experiment_results("exp1", request)
        with pytest.raises(HTTPException) as config_data:
            experiments.get_experiment_config("exp1", request)
        assert [
            listed.value.status_code,
            results.value.status_code,
            config_data.value.status_code,
        ] == [
            401,
            401,
            401,
        ]

    def test_no_middleware_configuration_still_requires_route_authentication(
        self, monkeypatch, tmp_path
    ):
        from fastapi.testclient import TestClient

        monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", tmp_path / "outputs")
        app = FastAPI()
        app.include_router(experiments.router)
        client = TestClient(app)

        for path in (
            "/experiments",
            "/experiments/example/results",
            "/experiments/example/config",
        ):
            assert client.get(path).status_code == 401

    def test_list_experiments_returns_empty_when_no_files(self, monkeypatch, tmp_path):
        monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", tmp_path / "outputs")

        result = experiments.list_experiments(self._request())
        assert result == {"configs": [], "reports": []}

    def test_list_report_identity_uses_filename_and_exact_digest(self, monkeypatch, tmp_path):
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        raw = json.dumps(self._report_payload("display name"), indent=2).encode()
        (outputs_dir / "exp1_report.json").write_bytes(raw)
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", outputs_dir)

        result = experiments.list_experiments(self._request())
        report = result["reports"][0]
        assert report["report_id"] == "exp1"
        assert report["experiment_name"] == "display name"
        assert report["schema_kind"] == "legacy_feature_addition"
        assert report["availability"] == "available"
        assert report["report_sha256"] == hashlib.sha256(raw).hexdigest()
        assert report["file"] == "outputs/exp1_report.json"
        assert report["winner"] == "variant1"
        assert report["any_target_met"] is True
        assert str(tmp_path) not in json.dumps(result)

    def test_list_keeps_malformed_unsupported_and_oversized_reports_unavailable(
        self, monkeypatch, tmp_path
    ):
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        (outputs_dir / "malformed_report.json").write_text("{", encoding="utf-8")
        (outputs_dir / "unsupported_report.json").write_text("{}", encoding="utf-8")
        (outputs_dir / "oversized_report.json").write_bytes(b" " * (5 * 1024 * 1024 + 1))
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", outputs_dir)

        reports = {
            row["report_id"]: row
            for row in experiments.list_experiments(self._request())["reports"]
        }
        assert reports["malformed"]["availability"] == "unavailable"
        assert reports["malformed"]["error"] == "malformed"
        assert reports["unsupported"]["schema_kind"] == "unsupported"
        assert reports["unsupported"]["availability"] == "unsupported"
        assert "experiment_name" not in reports["unsupported"]
        assert reports["oversized"]["availability"] == "unavailable"
        assert reports["oversized"]["error"] == "oversized"

    def test_known_config_report_mismatch_is_explicit_and_has_results(self, monkeypatch, tmp_path):
        exp_dir = tmp_path / "experiments"
        exp_dir.mkdir()
        (exp_dir / "medical_semantic_exp.yaml").write_text(
            "schema_version: 1\nmetadata:\n  name: Medical semantic\nvariant_count: 0\n",
            encoding="utf-8",
        )
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        (outputs_dir / "medical_semantic_chunking_exp_report.json").write_text(
            json.dumps(self._report_payload("medical_semantic_chunking_exp")), encoding="utf-8"
        )
        monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", exp_dir)
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", outputs_dir)

        result = experiments.list_experiments(self._request())
        assert result["configs"][0]["experiment_id"] == "medical_semantic_exp"
        assert result["configs"][0]["has_results"] is True
        assert result["reports"][0]["config_ref"] == "medical_semantic_exp"

    def test_get_results_adds_archive_metadata_without_replacing_winner(
        self, monkeypatch, tmp_path
    ):
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        raw = json.dumps(self._report_payload(), indent=2).encode()
        (outputs_dir / "exp1_report.json").write_bytes(raw)
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", outputs_dir)

        result = experiments.get_experiment_results("exp1", self._request())
        assert result["winner"] == {"name": "variant1"}
        assert result["baseline"] == {"name": "baseline", "metrics": {}}
        assert result["_artifact"] == {
            "report_id": "exp1",
            "report_sha256": hashlib.sha256(raw).hexdigest(),
            "schema_kind": "legacy_feature_addition",
            "availability": "available",
            "config_ref": None,
            "config_binding": None,
            "case_records_availability": "not_exposed_by_report_api",
            "comparable": False,
        }

    def test_get_results_rejects_invalid_oversized_and_symlinked_reports(
        self, monkeypatch, tmp_path
    ):
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        (outputs_dir / "unsupported_report.json").write_text("{}", encoding="utf-8")
        (outputs_dir / "oversized_report.json").write_bytes(b" " * (5 * 1024 * 1024 + 1))
        outside = tmp_path / "outside.json"
        outside.write_text(json.dumps(self._report_payload()), encoding="utf-8")
        (outputs_dir / "linked_report.json").symlink_to(outside)
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", outputs_dir)

        for name, status in (("unsupported", 422), ("oversized", 422), ("linked", 404)):
            with pytest.raises(HTTPException) as exc_info:
                experiments.get_experiment_results(name, self._request())
            assert exc_info.value.status_code == status

    def test_get_results_404_when_missing(self, monkeypatch, tmp_path):
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        monkeypatch.setattr(experiments, "OUTPUTS_DIR", outputs_dir)

        with pytest.raises(HTTPException) as exc_info:
            experiments.get_experiment_results("nonexistent", self._request())
        assert exc_info.value.status_code == 404

    def test_invalid_experiment_names_are_rejected(self):
        for name in ("..", "../outside", "/absolute"):
            with pytest.raises(HTTPException) as exc_info:
                experiments.get_experiment_results(name, self._request())
            assert exc_info.value.status_code == 400

    def test_get_experiment_config_uses_bounded_existing_config(self, monkeypatch, tmp_path):
        exp_dir = tmp_path / "experiments"
        exp_dir.mkdir()
        (exp_dir / "valid_exp.yaml").write_text(
            "schema_version: 1\nmetadata:\n  name: Valid\n", encoding="utf-8"
        )
        outside = tmp_path / "outside.yaml"
        outside.write_text("schema_version: 1\n", encoding="utf-8")
        (exp_dir / "linked_exp.yaml").symlink_to(outside)
        monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", exp_dir)

        parsed = experiments.get_experiment_config("valid_exp", self._request())
        assert parsed["metadata"]["name"] == "Valid"
        with pytest.raises(HTTPException) as linked:
            experiments.get_experiment_config("linked_exp", self._request())
        assert linked.value.status_code == 404

    def test_get_experiment_config_404_when_missing(self, monkeypatch, tmp_path):
        exp_dir = tmp_path / "experiments"
        exp_dir.mkdir()
        monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", exp_dir)

        with pytest.raises(HTTPException) as exc_info:
            experiments.get_experiment_config("nonexistent", self._request())
        assert exc_info.value.status_code == 404


class TestHealthRoutes:
    def test_health_degraded_when_vector_store_not_initialized(self, monkeypatch):
        monkeypatch.setattr(
            health,
            "get_runtime_status",
            lambda: {
                "runtime": {"vector_store_initialized": False},
                "vector_store": {"initialized": False, "signature": None, "config": {}},
            },
        )

        result = health.health_check()

        assert result["status"] == "degraded"
        assert result["ready"] is False
        assert result["vector_store"]["initialized"] is False

    def test_health_healthy_when_vector_store_initialized(self, monkeypatch):
        monkeypatch.setattr(
            health,
            "get_runtime_status",
            lambda: {
                "runtime": {"vector_store_initialized": True},
                "vector_store": {"initialized": True, "signature": "sig", "config": {}},
            },
        )

        result = health.health_check()

        assert result["status"] == "healthy"
        assert result["ready"] is True
        assert result["vector_store"]["initialized"] is True
