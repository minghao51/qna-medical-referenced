# Backend Tests

`scripts/check_backend.sh` is the single backend command surface; the `Makefile`
only wraps it. Both work from the repository root, and the script works where
`make` is unavailable.

```bash
make help                      # or: bash scripts/check_backend.sh help
make test                      # fast offline gate (no coverage), ~40s
make test-offline              # offline gate including slow tests
make coverage                  # fast selection with one project-wide report
make lint                      # read-only static gates, never auto-fixes
make smoke                     # smoke-marked tests only
make unit / make integration   # tier-restricted diagnosis runs
make frontend-check            # svelte-check + production build
make frontend-test             # Playwright suite
```

Extra arguments are forwarded to pytest, e.g. `make test -- -k ingestion -x`
(or `bash scripts/check_backend.sh fast -k ingestion -x`).

## What each mode selects

| Mode | Selection | Side effects |
|---|---|---|
| `fast` | `not slow and not live_api and not live_openrouter and not e2e_real_apis and not deepeval and not network` | none (no coverage) |
| `offline` | same selection without `not slow` | none; still synthetic, no corpus rebuild |
| `unit` / `integration` | `fast` selection restricted to that tier (`unit` adds `-n auto`) | none |
| `coverage` | `fast` selection plus `--cov=src --cov-report=term-missing:skip-covered --cov-fail-under=80` | writes `.coverage` |
| `lint` | Ruff check, Ruff format check, mypy `src`, import-linter, Bandit `-ll`, docs consistency | none; stops at the first failure |
| `smoke` | `-m smoke` | none |
| `frontend-check` | `bun run check`, `bun run build` in `frontend/` | writes `frontend/build` |
| `frontend-test` | `bun run test` (Playwright, requires installed browsers) | reports only |

The marker expression is defined once in the script. No mode selects live,
network or DeepEval tests, and no mode needs a provider key, so offline CI never
attaches secrets.

## Coverage

`make coverage` is the only coverage command. The floor defaults to **80%**
(override with `QNA_COVERAGE_FLOOR`). On 2026-10-31 the fast selection measured
**82%** locally with every optional dependency group installed; CI installs only
the `dev` group, so treat 80 as a floor with deliberate headroom, not a target
to lower if it fails. Bump it only from a clean-environment measurement.

Plain `uv run pytest` no longer collects coverage; add `--cov=src` yourself when
you want it for a targeted run.

## Project data is read-only for tests

Tests may read `data/` fixtures but must never write it. `tests/conftest.py`
fingerprints the whole `data/` tree at session start and fails the run if
anything was created, modified or removed, listing the paths. Isolate a test
with `persist_directory=tmp_path / "chroma"` (or by patching
`settings.storage.chroma_persist_directory`) and by patching
`src.ingestion.artifacts.DATA_PROCESSED_DIR` for artifact writes.

`tests/unit/test_test_isolation_policy.py` additionally rejects
`ChromaVectorStore(...)` constructions in tests without an explicit location or
the `fake_chroma_embeddings` fixture.

Deliberate data work (live runs, fixture regeneration) disables the guard with
`QNA_TEST_DATA_GUARD=0` or any live opt-in flag.

## Live and slow tests

Live opt-ins are independent; a test that needs several needs every one of them:

```bash
RUN_LIVE_QWEN_TESTS=1 uv run pytest -m live_api
RUN_LIVE_OPENROUTER_TESTS=1 uv run pytest -m live_openrouter
ENABLE_REAL_API_TESTS=1 uv run pytest -m e2e_real_apis
```

They spend real provider quota and require the provider key. They are never
selected by the shared commands above.

## Why a run can appear to hang for hours

Two independent effects:

1. **Unmarked live-network tests.** Every such test is marked `live_api` or
   `slow` today, and the shared commands exclude them.
2. **Orphaned process behind a pipe.** `timeout 600 uv run pytest ... | tail`
   kills `uv`, but the pytest child keeps running and holds the pipe. Bound a
   run with a hard kill and a file redirect:

```bash
timeout -s KILL 900 uv run pytest -q > /tmp/pytest.log 2>&1; echo "exit=$?"
```

## Targeted runs

```bash
uv run pytest tests/unit/config/test_settings.py
uv run pytest tests/integration/ingestion/test_retrieval.py -k hit_rate
uv run pytest tests/unit/app/test_evaluation_routes.py -q
```

## Test areas

- `tests/unit/config/test_settings.py` — config loading and defaults.
- `tests/unit/ingestion/test_chunker.py` — chunk sizing, overlap, metadata propagation.
- `tests/unit/ingestion/test_pdf_loader.py` — PDF extraction structure and metadata.
- `tests/unit/ingestion/test_embedding_spans.py` — embedding telemetry without provider calls.
- `tests/integration/ingestion/test_keyword_index.py`,
  `tests/integration/ingestion/test_embedding.py` and
  `tests/integration/ingestion/test_retrieval.py` — indexing and retrieval behaviour.
- `tests/unit/evals/` and `tests/integration/evals/` — evaluation artifacts, metrics
  and the offline L5/index checks (`test_source_metadata_pipeline.py`).
- `tests/unit/app/test_evaluation_routes.py` — evaluation API surface.
- `tests/integration/app/test_app_security.py` and
  `tests/unit/infra/test_storage_history.py` — API security and persistence.
- `tests/unit/evals/test_pipeline_assessment_smoke.py` — the `smoke` selection.

## Test organisation

- `tests/unit/` — fast isolated tests (no I/O, no external deps)
- `tests/integration/` — DB, filesystem or service stack involved
- `tests/e2e/` — full end-to-end workflows

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

## Environment notes

- Live-model behaviour depends on the active provider's nested key
  (`APP__LLM__DASHSCOPE_API_KEY`, `APP__LLM__GEMINI_API_KEY`, …). Flat names
  such as `DASHSCOPE_API_KEY` are ignored: settings use `APP__` with `__` nesting.
- ChromaDB store/search/migration tests run **offline** with stubbed embeddings
  (deterministic vectors via the `fake_chroma_embeddings` fixture in
  `tests/integration/conftest.py`); NLTK stopwords resolve from the vendored copy
  in `tests/integration/fixtures/nltk_data`.
- If retrieval-oriented tests fail because the index is missing, rebuild with
  `uv run python -m src.cli.ingest` (this writes project data; run it outside a
  guarded test session).
