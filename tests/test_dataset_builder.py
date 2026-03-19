import json
from pathlib import Path

import pytest

from src.evals.dataset_builder import build_retrieval_dataset, normalize_golden_queries


def _write_cached_run(
    run_dir: Path,
    *,
    dataset: list[dict],
    compatibility: dict | None,
) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "retrieval_dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
    manifest = {"dataset": {"compatibility": compatibility}} if compatibility is not None else {}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_normalize_golden_queries_works():
    path = Path("tests/fixtures/golden_queries.json")
    records = normalize_golden_queries(path)
    assert records
    assert all("query_id" in r for r in records)
    assert all(r["dataset_origin"] == "golden_fixture" for r in records)


def test_build_retrieval_dataset_offline_disable_llm(tmp_path: Path):
    dataset_file = tmp_path / "dataset.json"
    dataset_file.write_text(
        json.dumps(
            {
                "golden_queries": [
                    {"query": "Q1", "expected_keywords": ["a"], "expected_sources": ["Lipid"]},
                    {"query": "Q1", "expected_keywords": ["a"], "expected_sources": ["Lipid"]},
                    {"query": "Q2", "expected_keywords": ["b"], "expected_sources": ["Diabetes"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    bundle = build_retrieval_dataset(dataset_path=dataset_file, enable_llm_generation=False)
    assert bundle["stats"]["fixture_records"] == 3
    assert bundle["stats"]["merged_records"] == 2
    assert bundle["generation_attempts"][0]["status"] == "skipped"


def test_build_retrieval_dataset_uses_fixture_by_default_even_when_cache_exists(
    tmp_path: Path, monkeypatch
):
    evals_dir = tmp_path / "data" / "evals"
    run_dir = evals_dir / "20260313T000000Z_cached-run"
    run_dir.mkdir(parents=True)
    cached_dataset = [
        {
            "query_id": "cached_1",
            "query": "Cached question",
            "expected_keywords": ["cached"],
            "expected_sources": ["CacheSource"],
            "label_confidence": "high",
            "dataset_split": "regression",
            "dataset_origin": "cached_eval",
        }
    ]
    (run_dir / "retrieval_dataset.json").write_text(json.dumps(cached_dataset), encoding="utf-8")
    (evals_dir / "latest_run.txt").write_text(str(run_dir), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    fixture_dir = tmp_path / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    fixture_path = fixture_dir / "golden_queries.json"
    fixture_path.write_text(
        json.dumps(
            {
                "golden_queries": [
                    {
                        "query": "Fixture question",
                        "expected_keywords": ["fixture"],
                        "expected_sources": ["Fixture"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    bundle = build_retrieval_dataset(enable_llm_generation=False)

    assert bundle["stats"]["reused_cached_dataset"] is False
    assert bundle["stats"]["dataset_path"].endswith("tests/fixtures/golden_queries.json")
    assert bundle["dataset"][0]["query"] == "Fixture question"


def test_build_retrieval_dataset_falls_back_to_fixture_without_cache(tmp_path: Path, monkeypatch):
    fixture_dir = tmp_path / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    fixture_path = fixture_dir / "golden_queries.json"
    fixture_path.write_text(
        json.dumps(
            {
                "golden_queries": [
                    {
                        "query": "Fixture question",
                        "expected_keywords": ["fixture"],
                        "expected_sources": ["Fixture"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    bundle = build_retrieval_dataset(enable_llm_generation=False)

    assert bundle["stats"]["reused_cached_dataset"] is False
    assert bundle["stats"]["dataset_path"].endswith("tests/fixtures/golden_queries.json")
    assert bundle["dataset"][0]["query"] == "Fixture question"


def test_build_retrieval_dataset_reuses_cached_json_only_when_enabled(tmp_path: Path, monkeypatch):
    evals_dir = tmp_path / "data" / "evals"
    run_dir = evals_dir / "20260313T000000Z_cached-run"
    cached_dataset = [
        {
            "query_id": "cached_1",
            "query": "Cached question",
            "expected_keywords": ["cached"],
            "expected_sources": ["CacheSource"],
            "label_confidence": "high",
            "dataset_split": "regression",
            "dataset_origin": "cached_eval",
        }
    ]
    fixture_dir = tmp_path / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    fixture_path = fixture_dir / "golden_queries.json"
    fixture_path.write_text(
        json.dumps(
            {"golden_queries": [{"query": "Fixture question", "expected_sources": ["Fixture"]}]}
        ),
        encoding="utf-8",
    )
    compatibility = {
        "dataset_path": str(fixture_path.resolve()),
        "dataset_split": None,
        "min_label_confidence": "low",
        "enable_llm_generation": False,
        "max_synthetic_questions": 0,
        "sample_docs_per_source_type": 0,
        "seed": 0,
        "max_queries": None,
        "sample_seed": 42,
        "reuse_requirements": {},
    }
    _write_cached_run(run_dir, dataset=cached_dataset, compatibility=compatibility)
    (evals_dir / "latest_run.txt").write_text(str(run_dir), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    bundle = build_retrieval_dataset(enable_llm_generation=False, reuse_cached_dataset=True)

    assert bundle["stats"]["reused_cached_dataset"] is True
    assert bundle["stats"]["dataset_path"].endswith("retrieval_dataset.json")
    assert bundle["dataset"][0]["query"] == "Cached question"
    assert bundle["generation_attempts"][0]["reason"] == "reused_cached_dataset"
    assert bundle["stats"]["reused_from_run_dir"] == str(run_dir)


def test_build_retrieval_dataset_rejects_incompatible_latest_and_uses_older_compatible_run(
    tmp_path: Path, monkeypatch
):
    evals_dir = tmp_path / "data" / "evals"
    fixture_dir = tmp_path / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    fixture_path = fixture_dir / "golden_queries.json"
    fixture_path.write_text(
        json.dumps(
            {"golden_queries": [{"query": "Fixture question", "expected_sources": ["Fixture"]}]}
        ),
        encoding="utf-8",
    )
    compatible_contract = {
        "dataset_path": str(fixture_path.resolve()),
        "dataset_split": "regression",
        "min_label_confidence": "high",
        "enable_llm_generation": False,
        "max_synthetic_questions": 0,
        "sample_docs_per_source_type": 0,
        "seed": 0,
        "max_queries": None,
        "sample_seed": 42,
        "reuse_requirements": {"vector_file_sha256": "abc"},
    }
    latest_run = evals_dir / "20260314T000000Z_latest"
    older_run = evals_dir / "20260313T000000Z_older"
    _write_cached_run(
        latest_run,
        dataset=[
            {"query": "Wrong dataset", "label_confidence": "medium", "dataset_split": "regression"}
        ],
        compatibility={**compatible_contract, "min_label_confidence": "medium"},
    )
    _write_cached_run(
        older_run,
        dataset=[
            {
                "query": "Compatible dataset",
                "label_confidence": "high",
                "dataset_split": "regression",
            }
        ],
        compatibility=compatible_contract,
    )
    (evals_dir / "latest_run.txt").write_text(str(latest_run), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    bundle = build_retrieval_dataset(
        enable_llm_generation=False,
        reuse_cached_dataset=True,
        dataset_split="regression",
        min_label_confidence="high",
        reuse_requirements={"vector_file_sha256": "abc"},
    )

    assert bundle["dataset"][0]["query"] == "Compatible dataset"
    assert bundle["stats"]["reused_from_run_dir"] == str(older_run)
    assert bundle["stats"]["reuse_rejections"]
    assert bundle["stats"]["reuse_rejections"][0]["run_dir"] == str(latest_run)


def test_build_retrieval_dataset_fails_closed_when_no_compatible_cached_run_exists(
    tmp_path: Path, monkeypatch
):
    evals_dir = tmp_path / "data" / "evals"
    run_dir = evals_dir / "20260313T000000Z_cached-run"
    _write_cached_run(
        run_dir,
        dataset=[{"query": "Cached question"}],
        compatibility=None,
    )
    (evals_dir / "latest_run.txt").write_text(str(run_dir), encoding="utf-8")
    fixture_dir = tmp_path / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "golden_queries.json").write_text(
        json.dumps(
            {"golden_queries": [{"query": "Fixture question", "expected_sources": ["Fixture"]}]}
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="no compatible prior dataset"):
        build_retrieval_dataset(enable_llm_generation=False, reuse_cached_dataset=True)


def test_build_retrieval_dataset_reuses_custom_artifact_dir(tmp_path: Path, monkeypatch):
    evals_dir = tmp_path / "custom-evals"
    run_dir = evals_dir / "20260313T000000Z_cached-run"
    fixture_dir = tmp_path / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    fixture_path = fixture_dir / "golden_queries.json"
    fixture_path.write_text(
        json.dumps(
            {"golden_queries": [{"query": "Fixture question", "expected_sources": ["Fixture"]}]}
        ),
        encoding="utf-8",
    )
    compatibility = {
        "dataset_path": str(fixture_path.resolve()),
        "dataset_split": None,
        "min_label_confidence": "low",
        "enable_llm_generation": False,
        "max_synthetic_questions": 0,
        "sample_docs_per_source_type": 0,
        "seed": 0,
        "max_queries": None,
        "sample_seed": 42,
        "reuse_requirements": {},
    }
    _write_cached_run(
        run_dir,
        dataset=[{"query": "Cached question", "expected_sources": ["CacheSource"]}],
        compatibility=compatibility,
    )
    (evals_dir / "latest_run.txt").write_text(str(run_dir), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    bundle = build_retrieval_dataset(
        enable_llm_generation=False,
        reuse_cached_dataset=True,
        artifact_dir=evals_dir,
    )

    assert bundle["stats"]["reused_cached_dataset"] is True
    assert bundle["dataset"][0]["query"] == "Cached question"


def test_build_retrieval_dataset_samples_queries_deterministically(tmp_path: Path):
    dataset_file = tmp_path / "dataset.json"
    dataset_file.write_text(
        json.dumps(
            {
                "golden_queries": [
                    {
                        "query": f"Q{i}",
                        "expected_keywords": [f"k{i}"],
                        "expected_sources": [f"S{i}"],
                    }
                    for i in range(6)
                ]
            }
        ),
        encoding="utf-8",
    )

    first = build_retrieval_dataset(
        dataset_path=dataset_file,
        enable_llm_generation=False,
        max_queries=2,
        sample_seed=7,
    )
    second = build_retrieval_dataset(
        dataset_path=dataset_file,
        enable_llm_generation=False,
        max_queries=2,
        sample_seed=7,
    )
    third = build_retrieval_dataset(
        dataset_path=dataset_file,
        enable_llm_generation=False,
        max_queries=2,
        sample_seed=9,
    )

    assert [item["query"] for item in first["dataset"]] == [
        item["query"] for item in second["dataset"]
    ]
    assert first["stats"]["was_sampled"] is True
    assert first["stats"]["sampled_records"] == 2
    assert third["stats"]["sample_seed"] == 9
    assert [item["query"] for item in first["dataset"]] != [
        item["query"] for item in third["dataset"]
    ]
