# Testing Guide

## Testing Frameworks

### Backend (Python)
- **pytest** (>=9.0) — primary test runner
- **pytest-asyncio** (>=0.23.0) — async test support via `@pytest.mark.asyncio`
- **FastAPI TestClient** (`fastapi.testclient.TestClient`) — HTTP-level integration tests
- **unittest.mock** (`patch`, `MagicMock`) — mocking external dependencies
- **DeepEval** (>=3.9.0,<4.0.0) — LLM evaluation metrics (optional, `[evaluation]` extra)

### Frontend
- **Playwright** (`@playwright/test`) — E2E browser tests (6 spec files)
- **svelte-check** — type checking (not unit tests)

## How to Run Tests

### Backend
```bash
# All backend tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test categories
uv run pytest tests/unit/        # Unit tests only
uv run pytest tests/integration/ # Integration tests only
uv run pytest tests/e2e/         # E2E tests only

# Skip slow / live API tests (default behavior — these are auto-skipped)
uv run pytest

# Run live Qwen API tests
RUN_LIVE_QWEN_TESTS=1 uv run pytest -m live_api

# Run live OpenRouter tests
RUN_LIVE_OPENROUTER_TESTS=1 uv run pytest -m live_openrouter

# Run real API E2E tests
ENABLE_REAL_API_TESTS=1 uv run pytest -m e2e_real_apis

# Run DeepEval integration tests
uv run pytest -m deepeval

# Run only non-slow tests
uv run pytest -m "not slow"

# Lint check
uv run ruff check

# Type check (repo root; checks both src/ and tests/)
uv run mypy

# Security lint
uv run bandit -c pyproject.toml
```

### Full Pre-commit Check
```bash
# Run all pre-commit hooks on all files
uv run pre-commit run --all-files
```

### Frontend
```bash
cd frontend
bun run check       # Type check (svelte-check)
bun run test        # Playwright E2E tests
bun run test:ui     # Playwright with UI mode
bun run test:headed # Playwright headed mode
bun run build       # Verify build succeeds
```

## Test Structure and Organization

### Directory Layout
```
tests/
├── conftest.py                          # Global fixtures and hooks
├── fixtures/                            # Test data fixtures
│   ├── golden_queries.json              # Standard test queries
│   ├── golden_queries_expanded.json     # Extended query set
│   ├── golden_queries_comprehensive.json
│   ├── golden_queries_diverse.json
│   ├── golden_queries_all.json
│   ├── golden_conversations.json        # Multi-turn conversation fixtures
│   └── sample_medical.txt
├── unit/                                # Unit tests — fast, isolated, no I/O
│   ├── test_chunker.py
│   ├── test_configuration.py
│   ├── test_settings.py
│   ├── test_di_container.py
│   ├── test_embedding_cache.py
│   ├── test_eval_metrics.py
│   ├── test_experiment_config.py
│   ├── test_feature_ablation_runner.py
│   ├── test_hyde.py
│   ├── test_litellm_client.py
│   ├── test_medical_chunking.py
│   ├── test_medical_metrics.py
│   ├── test_production_profile.py
│   ├── test_query_understanding_classifier.py
│   ├── test_reranker.py
│   ├── test_retrieval_reranking_modes.py
│   ├── test_runtime_index_initialization.py
│   ├── test_runtime_retrieval_diversity.py
│   ├── test_search.py
│   ├── test_storage_history.py
│   ├── test_synthetic_generator.py
│   ├── test_thresholds.py
│   ├── test_wandb_history.py
│   ├── test_wandb_tracking.py
│   └── ... (65 files, flat — mirrored to package dirs in Phase 2)
├── integration/                         # Integration tests — DB, filesystem, HTTP
│   ├── test_app_security.py
│   ├── test_chat_multi_turn.py
│   ├── test_chat_sources.py
│   ├── test_chroma_migration.py
│   ├── test_chroma_search.py
│   ├── test_chroma_store.py
│   ├── test_concurrent_access.py
│   ├── test_embedding.py
│   ├── test_keyword_index.py
│   ├── test_pdf_loader.py
│   ├── test_performance_regression.py
│   ├── test_retrieval.py
│   └── ... (~15 files total)
└── e2e/                                # End-to-end tests — full pipeline with real APIs
    ├── test_backend_e2e_real_apis.py
    └── test_hamilton_pipeline.py
```

### Test File Naming
- All test files: `test_<feature_or_module>.py`
- Test classes: `Test<Feature>` (e.g., `TestTextChunker`)
- Test functions: `test_<behavior>` (e.g., `test_settings_defaults`, `test_chat_requires_valid_api_key`)

### Test Grouping
Tests are grouped into subdirectories by scope:
- `tests/unit/` — fast, isolated tests (no I/O, no external deps) — 65 files (flat layout; mirrored to package dirs in Phase 2)
- `tests/integration/` — tests with DB, filesystem, or service stack — ~15 files
- `tests/e2e/` — full end-to-end workflow tests — 2 files

## pytest Configuration

Defined in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
minversion = "9.0"
addopts = ["--strict-markers", "-ra", "--durations=10", "--import-mode=importlib"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

markers = [
    "unit: fast isolated tests (no I/O, no external deps)",
    "integration: tests with DB, filesystem, or service stack",
    "e2e: full end-to-end workflow tests",
    "slow: >1s tests",
    "live_api: requires live Qwen API access",
    "live_openrouter: requires live OpenRouter API access",
    "deepeval: DeepEval integration tests (slow, requires API)",
    "e2e_real_apis: end-to-end tests with real APIs (requires ENABLE_REAL_API_TESTS=1)",
    "network: needs internet access",
    "smoke: critical path tests",
    "serial: cannot run in parallel",
]
```

## Test Markers and Selection

| Marker | Purpose | How to Enable |
|--------|---------|---------------|
| `live_api` | Tests calling live Qwen/Dashscope API | `RUN_LIVE_QWEN_TESTS=1` |
| `live_openrouter` | Tests calling live OpenRouter API | `RUN_LIVE_OPENROUTER_TESTS=1` |
| `deepeval` | DeepEval LLM evaluation tests | Always active (auto-skipped without API key) |
| `e2e_real_apis` | Full E2E with real APIs | `ENABLE_REAL_API_TESTS=1` |
| `slow` | Slow-running tests | `-m "not slow"` to skip |
| `asyncio` | Async test functions | `@pytest.mark.asyncio` |
| `unit` | Fast isolated tests | Auto-selected by `pytest tests/unit/` |
| `integration` | Tests with deps | Auto-selected by `pytest tests/integration/` |
| `e2e` | Full workflow tests | Auto-selected by `pytest tests/e2e/` |
| `smoke` | Critical path tests | `-m smoke` |
| `serial` | Cannot run in parallel | `-m serial` |

Live API tests are **auto-skipped** by default via `pytest_collection_modifyitems` and `pytest_runtest_setup` hooks in `conftest.py`. These hooks also perform a pre-flight API check before running live tests.

## Test Fixtures

### Global Fixtures (conftest.py)
- **`golden_conversations_fixture`** — `list[dict]` of normalized golden conversations
- **`golden_conversations_raw`** — `dict` raw JSON from `golden_conversations.json`
- **`multi_turn_categories`** — valid conversation categories list
- **`multi_turn_difficulties`** — valid difficulty levels list
- **`multi_turn_splits`** — valid dataset splits list

### Built-in Fixtures Used
- **`monkeypatch`** — patch settings, modules, and functions (primary mocking mechanism)
- **`tmp_path`** — temporary directory for file-based tests (chat history, rate limit DB)
- **`pytest`** (import) — `pytest.raises()` for exception assertions, `pytest.mark` for markers

### Fixture Data
Test fixtures live in `tests/fixtures/` as JSON files:
- `golden_queries*.json` — test query sets at various scales
- `golden_conversations.json` — multi-turn conversations for evaluation tests
- `sample_medical.txt` — sample medical text for ingestion tests

### Per-Directory conftest.py
- `tests/conftest.py` — global fixtures and hooks
- `tests/integration/conftest.py` — integration-specific fixtures
- `tests/e2e/conftest.py` — E2E-specific fixtures

## Mocking Patterns

### Primary Approach: `monkeypatch`
The codebase strongly prefers `monkeypatch.setattr()` over `unittest.mock.patch()`:

```python
def test_example(monkeypatch, tmp_path):
    # Patch module-level functions
    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index", lambda: None)

    # Patch settings attributes
    monkeypatch.setattr(settings, "api.api_keys", "secret-key")
    monkeypatch.setattr(settings, "api.rate_limit_per_minute", 10)
```

### Mocking LLM Responses
Create dummy client classes or async generators:

```python
class DummyLLMClient:
    def generate(self, prompt: str, context: str) -> str:
        return f"answer:{prompt}:{len(context)}"

async def mock_stream_chat_message(**kwargs):
    yield ("ok", {"done": True, "sources": [], "pipeline": None})
```

### Mocking with `unittest.mock.patch`
Used in async contexts and for more complex mocking:

```python
from unittest.mock import patch

with patch("src.infra.llm.qwen_client.QwenClient.a_generate") as mock_gen:
    mock_gen.side_effect = [Exception("Timeout"), "Success response"]
    # ...
```

### Test Client Pattern
For HTTP-level tests, build a `TestClient` with patched dependencies:

```python
def _build_client(monkeypatch, tmp_path, *, api_keys="secret-key", rate_limit=10):
    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index", lambda: None)
    app = create_app()
    app.state.llm_client = DummyLLMClient()
    app.state.chat_history_store = FileChatHistoryStore(tmp_path / "chat_history.json")
    return TestClient(app)
```

### SSE Response Parsing
Helper for parsing Server-Sent Events in tests:

```python
def _parse_sse_events(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.split("\n") if line.startswith("data: ")]
```

## Test Class Patterns

### Class-Based Tests
Used for grouping related unit tests (e.g., `TestTextChunker`):
```python
class TestTextChunker:
    def test_chunk_text_basic(self):
        ...

    def test_chunk_size_respected(self):
        ...
```

### Function-Based Tests
Used for integration and endpoint tests:
```python
def test_chat_requires_valid_api_key(monkeypatch, tmp_path):
    ...

@pytest.mark.asyncio
async def test_dashscope_api_timeout_retry():
    ...
```

## CI Pipeline

### GitHub Actions (`.github/workflows/ci.yml`)
Runs on push to `main` and all pull requests:

1. **Backend job** (ubuntu-latest):
   - Python 3.12 setup + uv
   - `uv sync --frozen --dev`
   - `uv run ruff check` (lint)
   - `uv run mypy` (type check)
   - `uv run pytest` (tests)

2. **Frontend job** (ubuntu-latest):
   - Bun 1.2.5 setup
   - `bun install --frozen-lockfile`
   - `bun run check` (type check)
   - `bun run build` (build verification)

3. **Docker job**:
   - Build backend image (`Dockerfile`)
   - Build frontend image (`frontend/Dockerfile`)

### Docs Consistency (`.github/workflows/docs-consistency.yml`)
- Runs `scripts/check_docs_consistency.sh` for doc integrity

## Key Testing Conventions

1. **Always use `uv run`** — never bare `python` or `pytest`
2. **Prefer `monkeypatch`** over `unittest.mock.patch` for simple attribute/function patching
3. **Use `tmp_path`** for any file-based test to avoid state leakage
4. **Patch at the usage site** — e.g., `"src.app.routes.chat.stream_chat_message"` not the definition site
5. **Build TestClient fresh** per test via helper functions that patch all external dependencies
6. **Use descriptive test names** — `test_<behavior>_<condition>_<expected_outcome>`
7. **Test both happy and error paths** — separate test functions for success and failure cases
8. **Live API tests must be gated** with markers and auto-skip hooks in `conftest.py`
9. **Settings tests should use `Settings(_env_file=None, ...)`** to avoid environment coupling
10. **Tests organized by scope** in subdirectories: `tests/unit/`, `tests/integration/`, `tests/e2e/`
