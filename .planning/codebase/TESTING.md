# Testing

## Backend Testing

### Framework: pytest

#### Configuration
- **Test path**: `tests/` directory
- **Python files**: `test_*.py`
- **Test classes**: `Test*`
- **Test functions**: `test_*`
- **Custom markers**: `@pytest.mark.live_api` for tests requiring live API access

### Test Structure

```
tests/
├── conftest.py                          # Shared fixtures
├── test_settings.py                     # Configuration tests
├── test_eval_metrics.py                 # Metric calculations
├── test_chunker.py                      # Document chunking
├── test_embedding.py                    # Embedding functionality
├── test_retrieval.py                    # RAG retrieval
├── test_eval_artifacts.py               # Artifact handling
├── test_pipeline_assessment_smoke.py    # Pipeline integration
├── test_eval_pipeline_cli.py            # CLI testing
└── test_runtime_index_initialization.py # Index initialization
```

### Test Patterns

#### Unit Tests
```python
def test_settings_defaults():
    settings = Settings(dashscope_api_key="test-key")
    assert settings.model_name == "qwen3.5-flash"
    assert settings.embedding_model == "text-embedding-v4"
```

#### API Testing
- Live API tests skipped by default
- Enable with `RUN_LIVE_QWEN_TESTS=1`
- Pre-check verifies API availability
- HTTP exception testing for error cases

#### Metric Testing
```python
def test_rank_metrics_basic():
    rel = [0, 1, 0, 1]
    assert hit_rate_at_k(rel) == 1.0
    assert precision_at_k(rel, 4) == 0.5
    assert recall_at_k(rel, total_relevant=2) == 1.0
```

#### Integration Tests
- Full pipeline testing
- Optional data download
- Vector store initialization
- End-to-end evaluation workflows

### Fixtures (conftest.py)

#### Environment Setup
```python
@pytest.fixture
def mock_env_vars():
    os.environ["DASHSCOPE_API_KEY"] = "test-key-1,test-key-2"
    yield
    del os.environ["DASHSCOPE_API_KEY"]
```

#### Live API Pre-check
```python
@pytest.fixture
def skip_if_no_live_api():
    if not os.environ.get("RUN_LIVE_QWEN_TESTS"):
        pytest.skip("Set RUN_LIVE_QWEN_TESTS=1 to run live API tests")
```

### Test Organization

#### Grouping
- Feature-based test grouping
- Smoke tests for critical paths
- Integration tests for full workflows
- Unit tests for individual components

#### Test Data
- Golden queries for evaluation
- Mock responses for external APIs
- Fixtures shared across tests

### Test Execution

#### Commands
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_retrieval.py

# Run with verbose output
uv run pytest -v

# Run live API tests
RUN_LIVE_QWEN_TESTS=1 uv run pytest
```

## Frontend Testing

### Framework: Playwright

#### Configuration
- **Test location**: `frontend/tests/`
- **Language**: TypeScript/JavaScript
- **Base URL**: `PLAYWRIGHT_BASE_URL` environment variable

#### Test Scripts
```json
{
  "test": "playwright test",
  "test:ui": "playwright test --ui",
  "test:headed": "playwright test --headed",
  "test:debug": "playwright test --debug",
  "test:report": "playwright show-report"
}
```

### Test Structure

```
frontend/tests/
├── chat.spec.ts      # Chat interface tests
└── setup.ts          # Test configuration
```

### Test Patterns

#### Page Load Tests
```typescript
test('chat page loads correctly', async ({ page }) => {
  await page.goto(BASE_URL);
  await expect(page).toHaveTitle(/Health Screening Q&A/);
  await expect(page.locator('h1')).toContainText('Health Screening Q&A');
});
```

#### Interaction Tests
```typescript
test('can type in input field', async ({ page }) => {
  const input = page.locator('textarea');
  await input.click();
  await input.pressSequentially('Test question');
  await expect(input).toHaveValue('Test question');
});
```

#### Accessibility
- Use accessible selectors
- Test with screen reader in mind
- Keyboard navigation support

## Special Testing Features

### Live API Testing

#### Conditional Execution
```python
@pytest.mark.live_api
def test_qwen_chat():
    if not os.environ.get("RUN_LIVE_QWEN_TESTS"):
        pytest.skip("Set RUN_LIVE_QWEN_TESTS=1 to run")
    # Test code here
```

#### Pre-check Functionality
- Verifies API availability
- Validates credentials
- Skips gracefully if unavailable

### Evaluation Testing

#### Metrics Coverage
- Hit Rate (HR)
- Normalized Discounted Cumulative Gain (NDCG)
- Precision at K
- Recall at K
- Mean Reciprocal Rank (MRR)

#### Pipeline Assessment
- Step-by-step validation
- Artifact verification
- Performance tracking

#### Example
```python
def test_pipeline_end_to_end():
    result = run_pipeline(test_query)
    assert result.status == "success"
    assert result.metrics["hit_rate"] > 0.8
```

### Performance Testing

#### Timing Measurements
- Pipeline operation timing
- Index initialization performance
- Retrieval speed metrics
- LLM response time tracking

#### Example
```python
def test_retrieval_performance():
    start = time.time()
    results = vector_store.search(query)
    duration = time.time() - start
    assert duration < 1.0  # Should complete in < 1 second
```

## Testing Best Practices

### Backend

#### Principles
- Isolated tests (no shared state)
- Fast execution (unit tests > integration tests)
- Clear test names (describe what and why)
- One assertion per test (when possible)

#### Mocking
- Use mock API keys for testing
- No explicit mocking framework
- Live API tests are optional

#### Coverage
- Focus on critical functionality
- Integration tests cover end-to-end scenarios
- No explicit coverage percentage requirement

### Frontend

#### Principles
- Test user behavior, not implementation
- Use accessible selectors
- Wait for elements before interaction
- Clean up after tests

#### Selectors
- Prefer data-testid attributes
- Use accessibility roles
- Avoid fragile CSS selectors

#### Example
```typescript
// Good
const button = page.getByRole('button', { name: 'Submit' });

// Avoid
const button = page.locator('.btn-primary.large');
```

## Test Data Management

### Golden Queries
- Predefined queries for evaluation
- Expected results for validation
- Version-controlled in codebase

### Fixtures
- Shared test data in conftest.py
- Reusable components across tests
- Minimal setup/teardown

### Mock Responses
- Predictable responses for external APIs
- Consistent across test runs
- Easy to update

## Continuous Integration

### Test Execution
- All tests run in CI/CD
- Live API tests optionally skipped
- Fast feedback for developers

### Quality Gates
- All tests must pass before merge
- No new test failures allowed
- Performance regression detection

## Debugging Tests

### Backend
```bash
# Run with verbose output
uv run pytest -v

# Run specific test with output
uv run pytest tests/test_retrieval.py::test_search -v -s

# Drop into debugger
uv run pytest --pdb
```

### Frontend
```bash
# Run in debug mode
bun run test:debug

# Run with UI
bun run test:ui

# Run headed to see browser
bun run test:headed
```
