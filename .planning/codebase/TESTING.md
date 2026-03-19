# Testing

## Framework & Tools

### Backend Testing
- **Framework**: pytest
- **Config**: `pyproject.toml`
- **Runner**: `uv run pytest`
- **Type Checking**: mypy for `src/planweaver`

### Frontend Testing
- **Framework**: Playwright (E2E)
- **Runner**: `cd frontend && npm run e2e`
- **Unit Tests**: `cd frontend && npm run test:run`
- **Browser Automation**: Full Chromium/Firefox/Safari support

## Test Structure

### Backend Test Organization
```
tests/
├── test_answer_eval_*.py        # Answer evaluation tests
├── test_chat_sources.py         # Chat functionality
├── test_dataset_builder.py      # Dataset building
├── test_eval_pipeline_*.py      # Pipeline evaluation
├── test_experiment_config.py    # Configuration tests
├── test_medical_metrics.py      # Domain-specific metrics
├── test_orchestrator_*.py       # Evaluation orchestration
├── test_pipeline_*.py           # Pipeline integration
├── test_synthetic_generator.py  # Test data generation
└── test_wandb_tracking.py       # W&B integration
```

### Test Categories
- **Unit Tests**: Individual function/class testing
- **Integration Tests**: Service integration
- **Pipeline Tests**: End-to-end pipeline validation
- **Live API Tests**: Conditional execution with environment variables
- **E2E Tests**: Full user journey testing

## Testing Patterns

### Pytest Configuration
- **Markers**: Custom markers for test categorization
- **Fixtures**: Shared test setup/teardown
- **Monkeypatch**: Dependency mocking
- **Parametrize**: Data-driven testing

### Mocking Strategy
- **External APIs**: Mocked by default
- **LLM Calls**: Stubbed for unit tests
- **File I/O**: Temporary test directories
- **Environment**: Test-specific config

### Frontend E2E Tests
- **Critical User Flows**: Chat interface, evaluation dashboard
- **Browser Coverage**: Chromium, Firefox, WebKit
- **Network Mocking**: API response stubbing
- **Screenshot Capture**: Failure documentation

## Coverage

### Backend Coverage
- **Target**: Comprehensive test coverage
- **Key Areas**:
  - Chat orchestration (`src/usecases/chat.py`)
  - RAG runtime (`src/rag/runtime.py`)
  - Evaluation pipeline (`src/evals/`)
  - Configuration (`src/config/`)
  - API routes (`src/app/routes/`)

### Frontend Coverage
- **E2E**: Critical user paths
- **Components**: Key UI components
- **API Integration**: Frontend-backend communication

## Running Tests

### Backend Tests
```bash
# Full test suite
uv run pytest

# Specific test file
uv run pytest tests/test_chat_sources.py

# With markers
uv run pytest -m "not slow"

# Coverage report
uv run pytest --cov=src
```

### Frontend Tests
```bash
# E2E tests
cd frontend && npm run e2e

# Unit tests
cd frontend && npm run test:run
```

## Linting & Type Checking

### Python
```bash
# Linting
uv run ruff check .

# Formatting
uv run ruff format --check .

# Type checking
uv run mypy src/planweaver
```

### Frontend
```bash
# Type checking
npm run check
```

## Test Data Management
- **Synthetic Generation**: `test_synthetic_generator.py`
- **Dataset Builder**: `test_dataset_builder.py`
- **Fixtures**: Shared test data in pytest fixtures
- **Cleanup**: Automatic test isolation

## Continuous Integration
- **Pre-commit**: Linting and formatting checks
- **CI Pipeline**: Full test suite execution
- **Artifact Collection**: Test reports and coverage

## Best Practices
- **Isolation**: Each test should be independent
- **Speed**: Mock external dependencies
- **Clarity**: Descriptive test names
- **Maintenance**: Keep tests updated with code changes
