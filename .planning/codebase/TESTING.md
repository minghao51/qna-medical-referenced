# Testing Strategy

## Test Framework

### Backend Testing
- **Framework**: pytest 9.0+
- **Configuration**: `pyproject.toml` [tool.pytest.ini_options]
- **Test discovery**: `tests/` directory, `test_*.py` pattern
- **Markers**: Custom pytest markers for test categorization

### Frontend Testing
- **Framework**: Playwright 1.58+
- **Configuration**: Playwright config in `frontend/`
- **Test location**: `frontend/tests/`
- **Scripts**: `npm run test`, `npm run test:ui`, `npm run test:headed`

## Test Organization

### Test Markers

```python
# Live API tests (requires actual Qwen API access)
@pytest.mark.live_api
def test_qwen_client_real_call():
    pass

# DeepEval integration tests (slow, requires API)
@pytest.mark.deepeval
def test_answer_evaluation_with_deepeval():
    pass

# End-to-end tests with real APIs
@pytest.mark.e2e_real_apis
def test_backend_e2e_real_apis():
    pass

# Slow tests (can be deselected with '-m "not slow"')
@pytest.mark.slow
def test_full_ingestion_pipeline():
    pass
```

### Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── test_app_security.py        # Authentication and authorization
├── test_backend_e2e_real_apis.py  # Full stack E2E tests
├── test_chat_sources.py        # Chat source citation tests
├── test_chunker.py             # Text chunking tests
├── test_deepeval_models.py     # DeepEval integration tests
├── test_download_pdfs_manifest.py   # PDF download tests
├── test_download_web_manifest.py    # Web scraping tests
├── test_embedding.py           # Embedding generation tests
├── test_eval_deepeval.py       # Evaluation framework tests
├── test_eval_error_handling.py     # Error handling tests
├── test_evaluation_routes.py        # Evaluation endpoint tests
├── test_experiment_config.py        # Experiment config tests
├── test_experiment_manifest.py      # Experiment manifest tests
├── test_hyde.py                # HyDE query expansion tests
├── test_orchestrator_deepeval.py    # Evaluation orchestrator tests
├── test_retrieval.py           # Retrieval quality tests
├── test_runtime_index_initialization.py  # Index initialization tests
├── test_wandb_tracking.py      # WandB integration tests
└── test_*.py                   # Additional test modules
```

## Test Fixtures

### Shared Fixtures (conftest.py)

```python
# Mock LLM client
@pytest.fixture
def mock_llm_client():
    client = Mock()
    client.generate.return_value = "Test response"
    client.generate_stream.return_value = iter(["chunk1", "chunk2"])
    return client

# Temporary file storage
@pytest.fixture
def temp_history_store(tmp_path):
    return FileChatHistoryStore(tmp_path / "history.json")

# Test application
@pytest.fixture
def test_client(monkeypatch, tmp_path):
    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index", lambda: None)
    app = create_app()
    app.state.llm_client = mock_llm_client()
    return TestClient(app)
```

### Test Data Factories

```python
# Create test documents
def create_test_document(title: str = "Test Doc") -> Document:
    return Document(
        title=title,
        content="Test content with medical information.",
        source="test.pdf",
        metadata={"page": 1}
    )

# Create test queries
def create_test_query(query: str = "What is cholesterol?") -> Query:
    return Query(text=query, session_id="test-session")
```

## Test Categories

### Unit Tests

**Purpose**: Test individual components in isolation

**Examples**:
- Text chunking algorithms
- Embedding generation
- Configuration loading
- Utility functions

```python
def test_chunk_document_by_sentences():
    doc = create_test_document()
    chunks = chunk_document(doc, strategy="sentence")
    assert len(chunks) > 0
    assert all(len(c.content) > 0 for c in chunks)
```

### Integration Tests

**Purpose**: Test interaction between components

**Examples**:
- RAG pipeline (retrieval + generation)
- Ingestion pipeline steps
- Evaluation orchestration

```python
def test_rag_pipeline_retrieval_and_generation():
    result = run_rag_pipeline("What is normal cholesterol?")
    assert result.answer is not None
    assert len(result.sources) > 0
    assert "cholesterol" in result.answer.lower()
```

### End-to-End Tests

**Purpose**: Test full application flow

**Examples**:
- Complete chat request flow
- Full ingestion pipeline
- Evaluation workflow

```python
@pytest.mark.e2e_real_apis
def test_backend_e2e_real_apis():
    client = TestClient(app)
    response = client.post("/chat", json={"message": "Test question"})
    assert response.status_code == 200
    assert "answer" in response.json()
```

### Evaluation Tests

**Purpose**: Validate RAG quality

**Examples**:
- Answer relevance
- Context precision/recall
- Faithfulness metrics

```python
@pytest.mark.deepeval
def test_answer_relevance_with_deepeval():
    result = evaluate_answer(
        query="What is cholesterol?",
        context=["Cholesterol is a lipid molecule..."],
        answer="Cholesterol is a type of fat found in blood."
    )
    assert result.relevance_score > 0.7
```

## Mocking Strategies

### LLM Client Mocking

```python
# Simple mock
@pytest.fixture
def mock_llm_client():
    client = Mock()
    client.generate.return_value = "Mock response"
    return client

# Streaming mock
@pytest.fixture
def mock_streaming_client():
    async def mock_stream():
        yield "chunk1"
        yield "chunk2"
        yield "chunk3"

    client = Mock()
    client.generate_stream = mock_stream
    return client
```

### External API Mocking

```python
# Mock HTTP requests
@pytest.fixture
def mock_http_client(monkeypatch):
    async def mock_get(url):
        return MockResponse(content="Mock content", status_code=200)

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
```

### File System Mocking

```python
# Use tmp_path fixture
def test_file_operations(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")
    assert test_file.read_text() == "Test content"
```

## Running Tests

### Backend Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_chat_sources.py

# Run with markers
uv run pytest -m "not slow"  # Skip slow tests
uv run pytest -m "unit"      # Run only unit tests

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run live API tests (requires actual API keys)
uv run pytest -m live_api

# Run E2E tests (requires ENABLE_REAL_API_TESTS=1)
ENABLE_REAL_API_TESTS=1 uv run pytest -m e2e_real_apis
```

### Frontend Tests

```bash
cd frontend

# Run all Playwright tests
npm run test

# Run in UI mode (interactive)
npm run test:ui

# Run in headed mode (show browser)
npm run test:headed

# Run specific test file
npx playwright test chat.spec.ts

# Show test report
npm run test:report
```

## Test Coverage

### Coverage Configuration

```toml
[tool.coverage.run]
source = ["src"]
omit = [
    "tests/*",
    "*/__pycache__/*",
    "*/__init__.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

### Coverage Goals

- **Overall coverage**: >80%
- **Critical paths**: >90%
  - RAG pipeline
  - Chat orchestration
  - Error handling

## Continuous Integration

### Test Commands

```bash
# Full verification (as specified in CLAUDE.md)
uv run pytest                    # Backend tests
cd frontend && npm run e2e       # Frontend E2E tests
uv run ruff check .              # Linting
uv run ruff format --check .     # Format check
uv run mypy src/                 # Type checking
cd frontend && npm run test:run  # Frontend unit tests
```

### Test Pipelines

1. **Fast feedback** (run first):
   - Linting: `ruff check .`
   - Type checking: `mypy src/`
   - Unit tests: `pytest -m "not slow and not live_api"`

2. **Full verification** (run on main):
   - All tests: `pytest`
   - E2E tests: `pytest -m e2e_real_apis`
   - Frontend tests: `npm run test`

## Debugging Tests

### Verbose Output

```bash
# Show print statements
uv run pytest -s

# Show verbose output
uv run pytest -vv

# Show local variables on failure
uv run pytest -l
```

### Debugging Specific Tests

```bash
# Drop into debugger on failure
uv run pytest --pdb

# Run specific test
uv run pytest tests/test_chat.py::test_chat_endpoint

# Run until first failure
uv run pytest -x
```

### Playwright Debugging

```bash
# Run in debug mode
npm run test:debug

# Run with inspector
npx playwright test --debug

# Run specific test in headed mode
npx playwright test chat.spec.ts --headed
```

## Test Data Management

### Fixtures Directory

```
tests/
├── fixtures/
│   ├── documents/          # Test PDFs and documents
│   ├── html/              # Test HTML files
│   └── expected_results/  # Expected evaluation results
```

### Test Data Loading

```python
# Load test document
@pytest.fixture
def test_document():
    with open("tests/fixtures/documents/test.pdf", "rb") as f:
        return f.read()

# Load expected results
@pytest.fixture
def expected_results():
    with open("tests/fixtures/expected_results/eval_results.json") as f:
        return json.load(f)
```

## Best Practices

### Test Naming

```python
# Good: Descriptive names
def test_chat_returns_sources_when_context_available():
    pass

# Bad: Vague names
def test_chat_works():
    pass
```

### Test Structure

```python
# Arrange-Act-Assert pattern
def test_retrieval_returns_relevant_documents():
    # Arrange
    query = "What is cholesterol?"
    vector_store = setup_test_vector_store()

    # Act
    results = vector_store.search(query, top_k=5)

    # Assert
    assert len(results) == 5
    assert all("cholesterol" in r.content.lower() for r in results)
```

### Test Independence

```python
# Each test should be independent
def test_first_operation():
    result = operation_one()
    assert result.success

def test_second_operation():
    # Don't depend on test_first_operation
    result = operation_two()
    assert result.success
```

### Async Testing

```python
# Use pytest-asyncio for async tests
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result is not None
```

## Performance Testing

### Benchmark Tests

```python
# Measure retrieval performance
def test_retrieval_performance(benchmark):
    query = "Test query"
    result = benchmark(retrieve_documents, query)
    assert result is not None
```

### Load Testing

```python
# Test concurrent requests
@pytest.mark.asyncio
async def test_concurrent_chat_requests():
    tasks = [send_chat_request(f"Message {i}") for i in range(10)]
    results = await asyncio.gather(*tasks)
    assert all(r.status_code == 200 for r in results)
```

## Security Testing

### Authentication Tests

```python
def test_chat_requires_valid_api_key():
    response = client.post("/chat", json={"message": "test"})
    assert response.status_code == 401

def test_chat_accepts_valid_api_key():
    headers = {"X-API-Key": "valid-key"}
    response = client.post("/chat", json={"message": "test"}, headers=headers)
    assert response.status_code == 200
```

### Rate Limiting Tests

```python
def test_rate_limiting_enforced():
    for i in range(20):  # Exceed rate limit
        response = client.post("/chat", json={"message": f"test {i}"})
        if i > 10:
            assert response.status_code == 429
```

## Test Maintenance

### Regular Updates

1. **Review failing tests**: Check if tests or code needs updates
2. **Update fixtures**: Keep test data current
3. **Refactor tests**: Improve test clarity and maintainability
4. **Remove obsolete tests**: Delete tests for deprecated features

### Test Documentation

- **Docstrings**: Explain complex test scenarios
- **Comments**: Clarify non-obvious test logic
- **README**: Document test setup and requirements
