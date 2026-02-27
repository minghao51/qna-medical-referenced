import json
from pathlib import Path

from src.evals.dataset_builder import build_retrieval_dataset, normalize_golden_queries


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

