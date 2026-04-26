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
uv run pytest tests/unit/test_settings.py
uv run pytest tests/integration/test_retrieval.py -k hit_rate
uv run pytest tests/integration/test_evaluation_routes.py
```

## Test Areas

- `tests/unit/test_settings.py` covers config loading and defaults.
- `tests/unit/test_chunker.py` covers chunk sizing, overlap, and metadata propagation.
- `tests/unit/test_download_*.py` covers ingestion manifests and source downloads.
- `tests/unit/test_pdf_loader.py` covers PDF extraction structure and metadata.
- `tests/unit/test_keyword_index.py`, `tests/unit/test_embedding.py`, and `tests/integration/test_retrieval.py` cover indexing and retrieval behavior.
- `tests/unit/test_eval_*.py`, `tests/integration/test_pipeline_assessment_smoke.py`, and `tests/integration/test_pipeline_quality_upgrades.py` cover evaluation artifacts and metrics.
- `tests/integration/test_evaluation_routes.py` covers the API surface for evaluation results.
- `tests/integration/test_app_security.py` and `tests/unit/test_storage_history.py` cover API security and persistence behavior.

## Test Organization

Tests are organized into three tiers:
- `tests/unit/` — Fast isolated tests (no I/O, no external deps)
- `tests/integration/` — Tests with DB, filesystem, or service stack
- `tests/e2e/` — Full end-to-end workflow tests

## Markers

| Marker | Meaning |
|--------|---------|
| `unit` | Fast isolated tests |
| `integration` | Tests with DB/filesystem/services |
| `e2e` | Full workflow tests |
| `slow` | >1s tests |
| `live_api` | Requires live Qwen API access |
| `live_openrouter` | Requires live OpenRouter API access |
| `deepeval` | DeepEval integration tests (slow, requires API) |
| `e2e_real_apis` | End-to-end tests with real APIs |
| `network` | Needs internet access |
| `smoke` | Critical path tests |
| `serial` | Cannot run in parallel |

## Environment Notes

- Live-model behavior depends on `DASHSCOPE_API_KEY`.
- Tests marked `live_api` require real API access.
- If retrieval-oriented tests fail because the index is missing, rebuild with `uv run python -m src.cli.ingest`.
