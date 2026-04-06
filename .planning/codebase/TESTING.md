# Testing Patterns

**Analysis Date:** 2026-04-06

## Test Framework

**Runner:**
- Backend: pytest 8.0+ with pytest-asyncio
- Config: `pyproject.toml` `[tool.pytest.ini_options]`
- Frontend: Playwright Test 1.58+
- Config: `frontend/playwright.config.ts`

**Assertion Library:**
- Backend: pytest built-in `assert`
- Frontend: Playwright `expect` API

**Run Commands:**
```bash
pytest                          # Run all tests
pytest -m "not slow"            # Skip slow tests
pytest -m "not live_api"        # Skip live API tests
pytest tests/test_chunker.py    # Run specific file
pytest -k "chunk_size"          # Run tests matching keyword
npm run test                    # Run Playwright E2E tests
npm run test:ui                 # Playwright with UI
npm run test:headed             # Playwright with browser visible
npm run test:debug              # Playwright debug mode
```

## Test File Organization

**Location:**
- Backend: `tests/` directory at project root (separate from `src/`)
- Frontend: `frontend/tests/` directory

**Naming:**
- Backend: `test_<module>.py` (e.g., `test_chunker.py`, `test_settings.py`)
- Frontend: `<feature>.spec.ts` (e.g., `chat.spec.ts`, `pipeline.spec.ts`)

**Structure:**
```
tests/
├── conftest.py              # Shared fixtures and hooks
├── fixtures/                # JSON test data files
│   ├── golden_conversations.json
│   ├── golden_queries*.json
│   └── sample_medical.txt
├── test_*.py                # Test modules (53 files)
frontend/tests/
├── chat.spec.ts
├── markdown-rendering.spec.ts
├── pipeline.spec.ts
├── quality-metrics.spec.ts
└── visual-verification.spec.ts
```

## Test Structure

**Suite Organization:**
```python
# Class-based tests for related functionality
class TestTextChunker:
    def test_chunk_text_basic(self):
        chunker = TextChunker(chunk_size=800, chunk_overlap=150)
        chunks = chunker.chunk_text(text, "test.pdf", "doc1")
        assert len(chunks) > 0

# Function-based tests for simple cases
def test_settings_defaults():
    assert Settings.model_fields["model_name"].default == "qwen3.5-flash"

# Async tests with pytest.mark.asyncio
@pytest.mark.asyncio
async def test_network_timeout_with_retry():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [Exception("Timeout"), mock_response]
```

**Patterns:**
- Setup: Inline object creation or fixtures from `conftest.py`
- Teardown: Not explicitly used; pytest handles cleanup
- Assertion: Direct `assert` statements with descriptive messages

## Mocking

**Framework:** `unittest.mock` (`Mock`, `patch`)

**Patterns:**
```python
from unittest.mock import Mock, patch

# Patch external dependencies
with patch("httpx.AsyncClient.get") as mock_get:
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"%PDF-1.4\n%test content"
    mock_get.side_effect = [Exception("Timeout"), mock_response]

# Patch LLM client
with patch("src.infra.llm.qwen_client.QwenClient.generate") as mock_gen:
    mock_gen.return_value = "Test answer with sufficient content."
```

**What to Mock:**
- External API calls (HTTP clients, LLM providers)
- Network operations (downloads, web requests)
- Heavy dependencies (cross-encoder models, embedding models)

**What NOT to Mock:**
- Business logic under test
- Configuration/settings (use explicit values)
- File system operations (use `tempfile` for isolation)

## Fixtures and Factories

**Test Data:**
```python
# conftest.py - Shared fixtures
@pytest.fixture
def golden_conversations_fixture() -> list[dict]:
    """Load golden conversations from fixture file."""
    from src.evals.dataset_builder import normalize_golden_conversations
    fixture_path = Path(__file__).parent / "fixtures" / "golden_conversations.json"
    return normalize_golden_conversations(fixture_path)

@pytest.fixture
def multi_turn_categories() -> list[str]:
    return ["contextual_followup", "clarification", "topic_shift", "cross_document"]
```

**Location:**
- Fixtures: `tests/conftest.py`
- JSON data: `tests/fixtures/`
- Inline test data for simple cases

## Coverage

**Requirements:** None enforced (no coverage threshold configured)

**View Coverage:**
```bash
pytest --cov=src --cov-report=html  # Generate HTML report (if pytest-cov installed)
```

## Test Types

**Unit Tests:**
- Scope: Individual functions, classes, and modules
- Approach: Direct instantiation, inline test data, focused assertions
- Examples: `test_chunker.py`, `test_settings.py`, `test_embedding.py`

**Integration Tests:**
- Scope: Multi-component interactions (retrieval + reranking, chat flows)
- Approach: `@pytest.mark.live_api` for tests requiring real API access
- Examples: `test_chat_multi_turn.py`, `test_retrieval.py`, `test_chroma_store.py`

**E2E Tests:**
- Backend: `test_backend_e2e_real_apis.py` (requires `ENABLE_REAL_API_TESTS=1`)
- Frontend: Playwright browser tests (`frontend/tests/*.spec.ts`)
- Framework: Playwright with Chromium, single worker, 30s timeout

**Evaluation Tests:**
- DeepEval integration tests marked with `@pytest.mark.deepeval`
- LLM-as-a-judge evaluation pipelines
- Examples: `test_eval_deepeval.py`, `test_answer_eval_deepeval.py`

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_evaluate_answer_quality():
    dataset = [{"query": "Test query", "query_id": "test_001"}]
    results, aggregate = await evaluate_answer_quality_async(dataset, top_k=3)
    assert len(results) > 0
```

**Error Testing:**
```python
def test_chunker_rejects_unsupported_strategy():
    with pytest.raises(ValueError, match="does not support strategy 'legacy'"):
        TextChunker(chunk_size=80, chunk_overlap=10, strategy="legacy")
```

**Conditional Test Skipping:**
```python
# conftest.py - Auto-skip based on environment
def pytest_collection_modifyitems(config, items):
    if not LIVE_QWEN_ENABLED:
        skip_live = pytest.mark.skip(reason="Set RUN_LIVE_QWEN_TESTS=1")
        for item in items:
            if "live_api" in item.keywords:
                item.add_marker(skip_live)
```

**Test Markers:**
- `@pytest.mark.live_api` - Requires live Qwen API (`RUN_LIVE_QWEN_TESTS=1`)
- `@pytest.mark.deepeval` - DeepEval integration tests (slow)
- `@pytest.mark.e2e_real_apis` - Real API E2E tests (`ENABLE_REAL_API_TESTS=1`)
- `@pytest.mark.slow` - Slow tests (deselect with `-m "not slow"`)

---

*Testing analysis: 2026-04-06*
