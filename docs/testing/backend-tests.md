# Backend Tests

This repo has three practical backend test modes:

## Fast Feedback

```bash
uv run pytest
uv run ruff check .
```

Use this for normal development. Many tests use fixtures and local state only.

## Ingestion-Dependent Tests

Some retrieval, indexing, and evaluation tests are only meaningful after the corpus and vector index exist.

```bash
uv run python -m src.cli.ingest
uv run pytest
```

## Targeted Runs

```bash
uv run pytest tests/test_settings.py
uv run pytest tests/test_retrieval.py -k hit_rate
uv run pytest tests/test_evaluation_routes.py
```

## Test Areas

- `tests/test_settings.py` covers config loading and defaults.
- `tests/test_chunker.py` covers chunk sizing, overlap, and metadata propagation.
- `tests/test_download_*.py` covers ingestion manifests and source downloads.
- `tests/test_pdf_loader.py` covers PDF extraction structure and metadata.
- `tests/test_keyword_index.py`, `tests/test_embedding.py`, and `tests/test_retrieval.py` cover indexing and retrieval behavior.
- `tests/test_eval_*.py`, `tests/test_pipeline_assessment_smoke.py`, and `tests/test_pipeline_quality_upgrades.py` cover evaluation artifacts and metrics.
- `tests/test_evaluation_routes.py` covers the API surface for evaluation results.
- `tests/test_app_security.py` and `tests/test_storage_history.py` cover API security and persistence behavior.

## Environment Notes

- Live-model behavior depends on `DASHSCOPE_API_KEY`.
- Tests marked `live_api` require real API access.
- If retrieval-oriented tests fail because the index is missing, rebuild with `uv run python -m src.cli.ingest`.
