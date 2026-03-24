# Testing Practices

This document outlines the testing frameworks, patterns, and conventions used throughout the qna-medical-referenced codebase.

## Testing Frameworks

### Backend Testing

**Pytest** is the primary testing framework for Python backend code:

```bash
# Run all backend tests
uv run pytest

# Run specific test file
uv run pytest tests/test_settings.py

# Run with verbose output
uv run pytest -v

# Run specific marker
uv run pytest -m "not slow"
uv run pytest -m "e2e_real_apis"

# Run with coverage
uv run pytest --cov=src
```

**Configuration** (`pyproject.toml`):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "live_api: requires live Qwen API access",
    "deepeval: marks tests as DeepEval integration tests (slow, requires API)",
    "e2e_real_apis: marks tests as end-to-end tests with real API integrations (requires ENABLE_REAL_API_TESTS=1)",
    "slow: marks tests as slow (deselect with '-m \"not slow\"')"
]
```

**Async testing** uses `pytest-asyncio`:
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result is not None
```

### Frontend Testing

**Playwright** is used for end-to-end browser testing:

```bash
# Run all E2E tests
cd frontend && npm run test

# Run with UI mode
cd frontend && npm run test:ui

# Run in headed mode (see browser)
cd frontend && npm run test:headed

# Debug mode
cd frontend && npm run test:debug

# View test report
cd frontend && npm run test:report
```

**Configuration** (`playwright.config.ts`):
```typescript
export default defineConfig({
	testDir: './tests',
	retries: 0,
	timeout: 30000,
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	workers: 1,
	reporter: 'list',
	use: {
		baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5174',
		trace: 'on-first-retry',
	},
});
```

## Test Structure and Organization

### Backend Test Organization

**Test files mirror source structure**:
```
tests/
├── test_settings.py                    # Configuration tests
├── test_chat_multi_turn.py             # Chat use case tests
├── test_backend_e2e_real_apis.py       # End-to-end integration tests
├── test_eval_artifacts.py              # Evaluation artifact tests
├── test_evaluation_routes.py           # API route tests
└── test_deepeval_models.py             # DeepEval integration tests
```

**Test class organization**:
```python
class TestMultiTurnSessionPersistence:
    """Test that chat history persists correctly across multiple turns."""

    def test_three_turn_conversation_persists_history(self, monkeypatch, tmp_path):
        """Verify that after 3 turns, all user and assistant messages are in history."""
        client = _build_client(monkeypatch, tmp_path)
        # ... test implementation

    def test_different_sessions_have_isolated_history(self, monkeypatch, tmp_path):
        """Verify that different sessions maintain separate histories."""
        # ... test implementation
```

### Frontend Test Organization

**Test files grouped by feature**:
```
frontend/tests/
├── quality-metrics.spec.ts     # Quality metrics dashboard tests
├── chat.spec.ts                # Chat interface tests
├── pipeline.spec.ts            # Pipeline visualization tests
├── markdown-rendering.spec.ts  # Markdown rendering tests
└── visual-verification.spec.ts # Visual regression tests
```

**Test describe blocks**:
```typescript
test.describe('Quality Metrics Dashboard', () => {
	test.setTimeout(60000);

	test.beforeEach(async ({ page }) => {
		await mockEvaluationApi(page);
		await page.goto('/eval');
	});

	test('displays chunk quality distribution in L3 card', async ({ page }) => {
		const l3Card = page.locator('.step-card').filter({ hasText: 'L3' });
		await expect(l3Card).toBeVisible();
		// ... assertions
	});
});
```

## Fixtures and Mocking

### Backend Fixtures

**Pytest fixtures** for common test setup:

```python
@pytest.fixture(scope="session")
def real_api_config():
    """Load real API credentials from environment."""
    return {
        "dashscope_api_key": os.getenv("DASHSCOPE_API_KEY"),
        "wandb_project": os.getenv("WANDB_PROJECT"),
        "enable_real_tests": os.getenv("ENABLE_REAL_API_TESTS") == "1",
    }

@pytest.fixture
def skip_without_real_apis(real_api_config):
    """Skip test unless real APIs are explicitly enabled."""
    if not real_api_config["enable_real_tests"]:
        pytest.skip("Set ENABLE_REAL_API_TESTS=1 to run real API tests")
    if not real_api_config["dashscope_api_key"]:
        pytest.skip("Set DASHSCOPE_API_KEY to run real API tests")

@pytest.fixture
def temp_vector_store():
    """Create a temporary vector store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup
        yield get_vector_store()
        # Cleanup handled by context manager
```

**Monkeypatching for dependency injection**:
```python
def _build_client(monkeypatch, tmp_path: Path):
    """Build test client with mocked dependencies."""
    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index", lambda: None)
    monkeypatch.setattr("src.usecases.chat.retrieve_context", _fake_retrieve_context)
    monkeypatch.setattr(settings, "api_keys", "")
    app = create_app()
    app.state.llm_client = DummyLLMClient()
    return TestClient(app)
```

**Dummy/fake implementations**:
```python
class DummyLLMClient:
    """Dummy LLM client for testing."""
    def generate(self, prompt: str, context: str) -> str:
        return f"answer:{prompt[:50]}"

    async def a_generate_stream(self, prompt: str, context: str):
        response = f"answer:{prompt[:50]}"
        for token in response.split():
            yield token + " "
        yield ""

def _fake_retrieve_context(query: str, top_k: int = 5, retrieval_options=None):
    """Fake retrieval for testing."""
    del top_k, retrieval_options
    return f"context for {query}", [{"label": f"Source for {query}"}]
```

### Frontend Fixtures

**Mock API responses** in test setup:
```typescript
async function mockEvaluationApi(page: Page) {
	await page.route(`${API_URL}/evaluation/latest`, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify(evaluationFixture)
		});
	});
}

async function proxyBrowserApiRequests(page: Page) {
	if (API_URL === 'http://localhost:8000') return;
	await page.route('http://localhost:8000/**', async (route) => {
		const proxiedUrl = route.request().url().replace('http://localhost:8000', API_URL);
		const response = await route.fetch({ url: proxiedUrl });
		await route.fulfill({ response });
	});
}
```

**Test data fixtures**:
```typescript
const evaluationFixture = {
	run_dir: '20260320T101010.123456Z_baseline',
	step_metrics: {
		l1: { aggregate: { /* ... */ } },
		l2: { aggregate: { /* ... */ } },
		l3: { aggregate: { /* ... */ } }
	},
	retrieval_metrics: { /* ... */ }
};
```

## Test Data Management

### Temporary Files and Directories

**Use pytest's `tmp_path` fixture** for file-based tests:
```python
def test_artifact_store_writes_json_jsonl_text(tmp_path: Path):
    store = ArtifactStore(tmp_path, "my run")
    store.write_json("a.json", {"x": 1})
    store.write_jsonl("b.jsonl", [{"n": 1}, {"n": 2}])
    store.write_text("c.txt", "hello")

    assert (store.run_dir / "a.json").exists()
    assert (store.run_dir / "c.txt").read_text(encoding="utf-8") == "hello"
```

**Cleanup is automatic** - pytest removes temp directories after tests complete.

### Test Data Builders

**Create minimal test data** focused on what's being tested:
```python
def test_run_index_reuses_indexed_run(tmp_path: Path):
    run_dir = tmp_path / "20260319T000000.000000Z_demo"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({
            "run_identity": "abc123",
            "config": {},
            "git_head": "deadbeef"
        }),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps({"status": "ok"}),
        encoding="utf-8"
    )

    update_run_index(tmp_path, run_identity="abc123", run_dir=run_dir)
    assert find_reusable_run(tmp_path, "abc123") == run_dir
```

## Test Markers and Categories

### Backend Test Markers

**Use markers to categorize tests**:

```python
# Fast unit tests (no markers)
def test_settings_defaults():
    """Test schema defaults without depending on local environment overrides."""
    assert Settings.model_fields["model_name"].default == "qwen3.5-flash"

# Integration tests requiring real APIs
@pytest.mark.e2e_real_apis
@pytest.mark.slow
async def test_l6_answer_generation_with_real_llm(skip_without_real_apis):
    """Test L6: Generate answer for real medical query using LLM."""
    # ... test implementation

# DeepEval integration tests
@pytest.mark.deepeval
@pytest.mark.slow
async def test_deepeval_faithfulness_metric():
    """Test DeepEval faithfulness metric computation."""
    # ... test implementation
```

**Running tests by category**:
```bash
# Skip slow tests
uv run pytest -m "not slow"

# Run only E2E tests (with environment variable)
ENABLE_REAL_API_TESTS=1 uv run pytest -m e2e_real_apis

# Run all tests except live API tests
uv run pytest -m "not live_api"
```

### Frontend Test Organization

**Tests organized by feature and user flow**:
```typescript
test.describe('Quality Metrics Dashboard', () => {
	test.describe('L3 Metrics', () => {
		test('displays chunk quality distribution', async ({ page }) => { });
		test('displays section integrity metric', async ({ page }) => { });
	});

	test.describe('Retrieval Metrics', () => {
		test('displays deduplication subsection', async ({ page }) => { });
		test('displays high-confidence subset', async ({ page }) => { });
	});
});
```

## Assertion Patterns

### Backend Assertions

**Use descriptive assertions**:
```python
# Good: descriptive failure message
assert len(history) == 6, f"Expected 6 messages, got {len(history)}"
assert "LDL-C" in history[0]["content"], "First message should mention LDL-C"

# Good: check specific properties
assert history[0]["role"] == "user"
assert history[1]["role"] == "assistant"

# Good: verify structure
assert "answer" in result
assert "sources" in result
assert len(result["sources"]) > 0, "No sources found"
```

**Use pytest's approx for floating point**:
```python
assert metric_data["score"] == pytest.approx(0.85, abs=0.01)
```

### Frontend Assertions

**Use Playwright's expect API**:
```typescript
// Visibility checks
await expect(l3Card).toBeVisible();
await expect(qualityChart).toBeVisible();

// Content checks
await expect(l1Card.getByText('Content Density')).toBeVisible();
await expect(page.getByRole('tab', { name: 'Retrieval' })).toBeVisible();

// Count checks
await expect(labels).toHaveCount(3);
await expect(lowSegment).toHaveCount(1);

// Class checks
const hasWarningClass = await boilerplateValue.evaluate(el => el.classList.contains('warning'));
expect(hasWarningClass).toBeTruthy();
```

## Coverage Expectations

### Backend Coverage

**Aim for high coverage on critical paths**:
- Chat endpoint: >90% coverage
- Retrieval logic: >85% coverage
- Configuration: >100% coverage (test all defaults)
- Evaluation metrics: >80% coverage (some paths depend on external APIs)

**Run coverage report**:
```bash
uv run pytest --cov=src --cov-report=html --cov-report=term
```

### Frontend Coverage

**E2E tests cover critical user flows**:
- Chat interaction (send message, receive response, view sources)
- Multi-turn conversations (history persistence)
- Quality metrics dashboard (view all metrics, check thresholds)
- Pipeline visualization (trace display, step details)

**Visual verification** tests ensure UI correctness:
- Markdown rendering
- Chart display
- Responsive layout

## Integration vs Unit Tests

### Unit Tests

**Test individual functions/classes in isolation**:
```python
def test_settings_custom_values():
    """Test Settings with custom values (unit test)."""
    settings = Settings(
        _env_file=None,
        dashscope_api_key="test-key",
        model_name="qwen-plus",
        max_message_length=5000,
    )
    assert settings.model_name == "qwen-plus"
    assert settings.max_message_length == 5000
```

### Integration Tests

**Test multiple components working together**:
```python
def test_three_turn_conversation_persists_history(self, monkeypatch, tmp_path):
    """Integration test: chat endpoint + history store + session management."""
    client = _build_client(monkeypatch, tmp_path)

    response1 = client.post("/chat", json={"message": "What is LDL-C target?"})
    session_id = response1.cookies.get("chat_session_id")

    response2 = client.post("/chat", json={"message": "What if patient has diabetes?"})
    response3 = client.post("/chat", json={"message": "Should they get high-intensity statin?"})

    history_response = client.get("/history")
    history = history_response.json()["history"]

    assert len(history) == 6  # 3 user + 3 assistant messages
```

### End-to-End Tests

**Test complete workflows with real APIs**:
```python
@pytest.mark.e2e_real_apis
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2e_complete_pipeline(skip_without_real_apis, tmp_path):
    """Test complete L0-L6 pipeline end-to-end with real APIs.

    Validates:
    - L0: Document download
    - L1-L2: HTML/Markdown conversion
    - L3: Chunking
    - L4-L5: Vector store and retrieval
    - L6: Answer generation and evaluation
    - Artifact persistence
    """
    # Load and chunk documents
    documents = get_documents()
    chunked_docs = chunk_documents(documents)

    # Build vector store
    vector_store = get_vector_store()
    stats = vector_store.add_documents(chunked_docs)

    # Test retrieval
    query = "What is the LDL-C target for high-risk patients?"
    results = vector_store.similarity_search(query, top_k=3)

    # Generate and evaluate answer
    dataset = [{"query": query, "query_id": "e2e_pipeline_001"}]
    eval_results, aggregate = await evaluate_answer_quality_async(dataset)

    assert len(eval_results) == 1
    assert "answer" in eval_results[0]
    assert "metrics" in eval_results[0]
```

## Best Practices

1. **Test isolation**: Each test should be independent and not depend on other tests
2. **Descriptive names**: Test names should clearly describe what is being tested
3. **Arrange-Act-Assert**: Structure tests clearly (setup, execute, verify)
4. **Mock external dependencies**: Use fixtures and monkeypatching to avoid real API calls in unit tests
5. **Use markers**: Tag tests appropriately (slow, e2e, integration)
6. **Test data minimality**: Use the simplest test data that exercises the code path
7. **Cleanup**: Ensure tests clean up resources (use fixtures and context managers)
8. **Fast feedback**: Keep unit tests fast (<1s each), integrate slow tests separately
9. **Meaningful assertions**: Assert what matters, not just implementation details
10. **Test error paths**: Don't just test happy paths, test error handling too
