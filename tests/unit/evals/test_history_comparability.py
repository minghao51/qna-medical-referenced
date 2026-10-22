import json
from pathlib import Path

import pytest

from src.evals.artifact_service import EvaluationService


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_history_preserves_diagnostics_but_never_aggregates_incomparable_runs(tmp_path):
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    artifacts = {
        "20261016T000004Z_incomplete": {
            "manifest.json": {
                "comparable": True,
                "experiment": {"index_config_hash": "same"},
                "config": {"experiment_config": {"metadata": "unsupported-shape"}},
            },
            "summary.json": {"status": "incomplete"},
        },
        "20261016T000003Z_unsupported": {
            "manifest.json": {
                "artifact_contract_version": 999,
                "comparable": True,
                "experiment": {"index_config_hash": "same"},
            },
            "summary.json": {
                "status": "error",
                "duration_s": 3.5,
                "failed_thresholds_count": True,
            },
            "retrieval_metrics.json": {"query_count": True, "latency_p50_ms": True},
        },
        "20261016T000002Z_versioned": {
            "manifest.json": {
                "artifact_contract_version": 1,
                "comparable": True,
                "experiment": {"index_config_hash": "same"},
            },
            "summary.json": {
                "status": "failed",
                "duration_s": True,
                "failed_thresholds_count": 2,
                "l6_answer_quality_metrics": {
                    "status": "incomplete",
                    "answer_relevancy": {"mean": float("nan"), "count": True},
                },
            },
            "retrieval_metrics.json": {
                "query_count": 2,
                "hit_rate_at_k": float("nan"),
                "mrr": True,
                "ndcg_at_k": 0.75,
                "latency_p50_ms": float("inf"),
                "latency_p95_ms": 15,
            },
        },
        "20261016T000001Z_legacy": {
            "manifest.json": {
                "comparable": True,
                "experiment": {"index_config_hash": "same"},
            },
            "summary.json": {
                "status": "ok",
                "duration_s": 2,
                "failed_thresholds_count": 0,
            },
            "retrieval_metrics.json": {
                "query_count": 1,
                "hit_rate_at_k": 1.0,
                "mrr": 0.8,
                "latency_p50_ms": 10,
            },
        },
    }
    original_bytes: dict[Path, bytes] = {}
    run_dirs = {}
    for run_name, files in artifacts.items():
        run_dir = evals_dir / run_name
        run_dir.mkdir()
        run_dirs[run_name] = run_dir
        for filename, payload in files.items():
            path = run_dir / filename
            _write_json(path, payload)
            original_bytes[path] = path.read_bytes()

    service = EvaluationService(evals_dir, evals_dir / "latest_run.txt")
    runs = service.local_history_runs(10)
    summary = service.aggregate_history_summary(runs)

    assert [run["artifact_compatibility"] for run in runs] == [
        "legacy",
        "unsupported",
        "versioned",
        "legacy",
    ]
    assert all(run["comparable"] is False for run in runs)
    assert {run["index_config_hash"] for run in runs} == {"same"}
    assert [run["status"] for run in runs] == ["incomplete", "error", "failed", "ok"]
    assert runs[0]["retrieval_metrics"]["hit_rate_at_k"] is None
    assert runs[1]["duration_s"] == 3.5
    assert runs[1]["failed_thresholds_count"] is None
    assert runs[1]["retrieval_metrics"]["query_count"] is None
    assert runs[1]["retrieval_metrics"]["latency_p50_ms"] is None
    assert runs[2]["duration_s"] is None
    assert runs[2]["retrieval_metrics"]["hit_rate_at_k"] is None
    assert runs[2]["retrieval_metrics"]["mrr"] is None
    assert runs[2]["retrieval_metrics"]["ndcg_at_k"] == 0.75
    assert runs[2]["l6_answer_quality_metrics"]["answer_relevancy"] == {
        "mean": None,
        "count": None,
    }
    assert summary == {
        "total_runs": 4,
        "avg_hit_rate": None,
        "avg_mrr": None,
        "avg_latency_p50": None,
        "avg_duration": None,
        "sources": {"local": 4},
    }
    json.dumps({"runs": runs, "summary": summary}, allow_nan=False)
    for path, original in original_bytes.items():
        assert path.read_bytes() == original

    unsupported_payload = service.load_run_payload(run_dirs["20261016T000003Z_unsupported"])
    assert unsupported_payload["comparable"] is False
    assert unsupported_payload["manifest"]["comparable"] is False
    json.dumps(unsupported_payload, allow_nan=False)
    for path, original in original_bytes.items():
        assert path.read_bytes() == original


def test_run_listing_projects_invalid_measurements_without_changing_metadata(tmp_path):
    run_dir = tmp_path / "20261016T000001Z_listing"
    run_dir.mkdir()
    tracking = {"value": "diagnostic label", "count": "metadata"}
    summary = {
        "status": "failed",
        "duration_s": float("nan"),
        "failed_thresholds_count": True,
        "tracking": tracking,
    }
    _write_json(run_dir / "summary.json", summary)
    _write_json(run_dir / "retrieval_metrics.json", {"query_count": 1})
    original = (run_dir / "summary.json").read_bytes()
    service = EvaluationService(tmp_path, tmp_path / "latest_run.txt")

    runs = service.get_all_runs()

    assert len(runs) == 1
    assert runs[0]["duration_s"] is None
    assert runs[0]["failed_thresholds_count"] is None
    assert runs[0]["tracking"] == tracking
    json.dumps(runs, allow_nan=False)
    assert (run_dir / "summary.json").read_bytes() == original


def test_individual_diagnostics_preserve_boolean_findings_and_configuration(tmp_path):
    run_dir = tmp_path / "20261016T000001Z_diagnostics"
    run_dir.mkdir()
    manifest = {
        "config": {
            "experiment_config": {
                "metadata": {"name": "synthetic", "value": "diagnostic label", "count": "label"}
            }
        }
    }
    finding = {
        "metric": "l5.embedding_dim_consistent",
        "value": False,
        "threshold_value": 1.0,
    }
    _write_json(run_dir / "manifest.json", manifest)
    _write_json(run_dir / "summary.json", {"failed_thresholds": [finding]})
    service = EvaluationService(tmp_path, tmp_path / "latest_run.txt")

    payload = service.load_run_payload(run_dir)

    assert payload["manifest"] == manifest
    assert payload["experiment_config"]["metadata"]["value"] == "diagnostic label"
    assert payload["failed_thresholds"] == [finding]
    assert payload["summary"]["failed_thresholds"] == [finding]


@pytest.mark.parametrize(
    ("stage", "field"),
    [
        ("l1", "retention_ratio_median"),
        ("l2", "chars_per_page_median"),
        ("l3", "chunk_length_median"),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, None),
        (False, None),
        (None, None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        ("unmeasured", None),
        (0, 0),
        (0.0, 0.0),
        (12.5, 12.5),
    ],
)
def test_median_projection_preserves_finite_measurements_and_diagnostic_metadata(
    tmp_path, stage, field, value, expected
):
    run_dir = tmp_path / "20261016T000001Z_median"
    run_dir.mkdir()
    finding = {"metric": "l5.embedding_dim_consistent", "value": False}
    artifacts = {
        "summary.json": {"status": "incomplete", "failed_thresholds": [finding]},
        "manifest.json": {
            "config": {"experiment_config": {"metadata": {field: True}}},
        },
        "step_metrics.json": {stage: {"aggregate": {field: value}, "records": [{field: value}]}},
    }
    for name, data in artifacts.items():
        _write_json(run_dir / name, data)
    original = {name: (run_dir / name).read_bytes() for name in artifacts}
    service = EvaluationService(tmp_path, tmp_path / "latest_run.txt")

    payload = service.load_run_payload(run_dir)

    metrics = payload["step_metrics"][stage]
    for projected in (metrics["aggregate"][field], metrics["records"][0][field]):
        if expected is None:
            assert projected is None
        else:
            assert projected == expected
            assert type(projected) is type(expected)
    assert payload["experiment_config"]["metadata"][field] is True
    assert payload["manifest"]["config"]["experiment_config"]["metadata"][field] is True
    assert payload["failed_thresholds"] == [finding]
    json.dumps(payload, allow_nan=False)
    assert {name: (run_dir / name).read_bytes() for name in artifacts} == original


@pytest.mark.parametrize("stage", ["l1", "l2", "l3"])
def test_missing_median_is_not_invented_as_zero(tmp_path, stage):
    run_dir = tmp_path / "20261016T000001Z_missing-median"
    run_dir.mkdir()
    _write_json(run_dir / "step_metrics.json", {stage: {"aggregate": {}, "records": [{}]}})
    service = EvaluationService(tmp_path, tmp_path / "latest_run.txt")

    metrics = service.load_run_payload(run_dir)["step_metrics"][stage]

    assert metrics == {"aggregate": {}, "records": [{}]}


def test_empty_history_has_null_aggregates_and_zero_counts(tmp_path):
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    service = EvaluationService(evals_dir, evals_dir / "latest_run.txt")

    summary = service.aggregate_history_summary(service.local_history_runs(10))

    assert summary == {
        "total_runs": 0,
        "avg_hit_rate": None,
        "avg_mrr": None,
        "avg_latency_p50": None,
        "avg_duration": None,
        "sources": {},
    }
