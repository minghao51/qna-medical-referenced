# Backend Tests

This repo has three practical backend test modes:

## Fast Feedback (offline, deterministic)

```bash
uv run pytest -m "not slow and not live_api and not live_openrouter and not deepeval and not e2e_real_apis and not network"
uv run ruff check .
```

This is the gate CI should use and the one to use for normal development:
roughly 50 seconds, no provider calls, no corpus or index required.
A bare `uv run pytest` also works, but `tests/conftest.py` only auto-skips
`live_api` tests; `slow` tests are still selected, so the run is much longer.

## Why a run can appear to hang for hours

Two independent effects:

1. **Unmarked live-network tests.** Some "unit" tests drive real retrieval and
   DeepEval judges (each 60–210 s) or construct a real provider client. If they
   are not marked `live_api` or `slow`, a default run executes them.
   All such tests are now marked; `tests/conftest.py` skips `live_api` unless
   `RUN_LIVE_QWEN_TESTS=1`.
2. **Orphaned process behind a pipe.** `timeout 600 uv run pytest ... | tail`
   kills `uv`, but the pytest child keeps running and holds the pipe, so the
   shell waits far longer than the timeout.

Use a hard kill and a file redirect when bounding a run:

```bash
timeout -s KILL 900 uv run pytest -q > /tmp/pytest.log 2>&1; echo "exit=$?"
```

## Running live/slow tests deliberately

```bash
RUN_LIVE_QWEN_TESTS=1 uv run pytest -m "slow or live_api"
```

Live tests spend real provider quota and require the configured provider key
(`APP__LLM__DASHSCOPE_API_KEY`, or the active provider's key).

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

- Live-model behavior depends on the active provider's nested key
  (`APP__LLM__DASHSCOPE_API_KEY`, `APP__LLM__GEMINI_API_KEY`, …). Flat names
  such as `DASHSCOPE_API_KEY` are ignored: settings use `APP__` with `__` nesting.
- Tests marked `live_api` require real API access and are skipped unless
  `RUN_LIVE_QWEN_TESTS=1`.
- ChromaDB store/search/migration tests run **offline** in CI with stubbed embeddings (deterministic vectors via the `fake_chroma_embeddings` fixture in `tests/integration/conftest.py`); NLTK stopwords resolve from a vendored copy in `tests/integration/fixtures/nltk_data`.
- If retrieval-oriented tests fail because the index is missing, rebuild with `uv run python -m src.cli.ingest`.
