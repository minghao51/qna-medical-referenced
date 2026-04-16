# Testing Strategy

## Python Backend

### Framework & Setup
- **Test Framework**: pytest >= 8.0.0
- **Async Support**: pytest-asyncio
- **Coverage**: Default coverage via ruff
- **Markers**: Custom markers for test categories
- **Configuration**: `pytest.ini` in project root
- **Fixtures**: Centralized in `tests/conftest.py`

### Test Structure
```
tests/
├── conftest.py        # Test configuration and fixtures
├── fixtures/         # Test data files
└── test_*.py         # Test files organized by module
```

### Test Categories (Markers)
- `live_api`: Tests requiring real Qwen API access
- `deepeval`: DeepEval integration tests (slow, requires API)
- `e2e_real_apis`: End-to-end tests with real API integrations
- `slow`: Tests marked as slow (deselect with `-m "not slow"`)

### Test Patterns
- **Integration Tests**: Test real API interactions with mocking
- **Unit Tests**: Mock external dependencies
- **Fixtures**: Reusable test data setup
- **Golden Data**: Standard test datasets for consistency

### Mocking Strategy
- **API Calls**: Mock OpenAI client for unit tests
- **Vector Store**: In-memory mock for development
- **Storage**: Mock file system operations
- **LLM Responses**: Predefined responses for deterministic tests

### Live API Testing
- **Pre-check**: Verify API accessibility before tests
- **Conditional Execution**: Skip unless `RUN_LIVE_QWEN_TESTS=1`
- **Retry Logic**: Built into fixture setup
- **Cleanup**: Clear test data after runs

### Testing Configuration
```python
# pytest.ini
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

### Test Data Management
- **Fixtures**: JSON files in `tests/fixtures/`
- **Golden Conversations**: Standardized test data
- **Mock Data**: Deterministic responses for unit tests
- **Cleanup**: Ensure isolation between tests

## Frontend (SvelteKit)

### Framework & Setup
- **E2E Testing**: Playwright >= 1.58.0
- **Configuration**: `playwright.config.ts`
- **Port**: Dynamic port (4173 default, configurable)
- **Timeout**: 30s test timeout, 5s assertion timeout

### Test Structure
```
frontend/tests/
├── helpers.ts       # Test helpers and utilities
├── *.spec.ts        # End-to-end test files
└── reports/         # Test execution reports
```

### Test Execution
```bash
# Run all tests
npm test

# Run with UI
npm run test:ui

# Run headed (visible browser)
npm run test:headed

# Debug mode
npm run test:debug

# Show reports
npm run test:report
```

### Test Patterns
- **Component Testing**: Not implemented (Playwright only)
- **Page Navigation**: Route-based testing
- **API Mocking**: Test API responses with mock data
- **Visual Testing**: Screenshots and visual comparisons

### Mock Strategy
- **API Responses**: Mock JSON data in test files
- **Pipeline Data**: Structured mock objects
- **Timing**: Simulate performance metrics
- **Errors**: Test error states and recovery

## Test Data

### Golden Dataset
- **Location**: `tests/fixtures/golden_conversations.json`
- **Structure**: Standardized conversation format
- **Categories**: Multi-turn conversations by difficulty
- **Normalization**: Handled via `dataset_builder`

### Mock Data
- **Pipeline Responses**: Structured with all required fields
- **API Errors**: Consistent error formats
- **Performance Metrics**: Realistic timing data
- **Document Sources**: Medical document examples

## Coverage Approach

### Backend Coverage
- **Unit Tests**: All utility functions, business logic
- **Integration Tests**: API endpoints, database operations
- **Thresholds**: Not explicitly defined, but comprehensive

### Frontend Coverage
- **E2E Coverage**: Core user journeys
- **Critical Paths**: Chat flow, evaluation flow
- **Error Handling**: API error scenarios

### Test Execution
- **CI/CD**: Automated test execution on PRs
- **Parallel**: Sequential test execution (workers=1)
- **Retries**: 0 retries for deterministic tests
- **Reporting**: Default list reporter

## Test Utilities

### Backend Helpers
- `conftest.py`: Common fixtures and setup
- `golden_conversations_fixture`: Standard test data
- `_ensure_live_qwen_available`: API connectivity check

### Frontend Helpers
- `helpers.ts`: Test utility functions
- API mocking utilities
- Page interaction helpers

## Best Practices

### Test Organization
1. **One assertion per test** when possible
2. **Descriptive test names** (test_behavior_outcome)
3. **Arrange-Act-Assert** pattern
4. **Independent tests** (no inter-test dependencies)

### Data Management
1. **Clean state** before each test
2. **Minimal fixtures** for what's needed
3. **Realistic data** for integration tests
4. **Consistent formats** across tests

### Performance
1. **Mock external dependencies** for unit tests
2. **Use in-memory databases** when possible
3. **Batch operations** for performance tests
4. **Cache test data** when appropriate

### Documentation
1. **Test docstrings** for complex tests
2. **Marker explanations** in pytest.ini
3. **Configuration comments** in test files
4. **README with test instructions**
