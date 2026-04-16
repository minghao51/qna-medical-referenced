# Codebase Conventions

## Python Backend

### Code Style & Formatting
- **Line Length**: 100 characters (ruff config)
- **Python Version**: 3.12 required
- **Type Checking**: MyPy with strict mode enabled
- **Linter**: Ruff with E, F, I, N, W rules (E501 ignored)
- **Format**: Black-compatible formatting

### Naming Patterns
- **Classes**: PascalCase (e.g., `VectorStore`, `AppError`)
- **Functions**: snake_case (e.g., `similarity_search`, `log_event`)
- **Variables**: snake_case with descriptive names
- **Constants**: UPPER_SNAKE_CASE (e.g., `L6_ANSWER_QUALITY_ROWS`)
- **Private members**: Leading underscore (e.g., `_error_payload`)

### Error Handling
- **Base Exception**: `AppError` dataclass with HTTP semantics
- **Specific Errors**:
  - `InvalidInputError` (400)
  - `UpstreamServiceError` (502)
  - `ArtifactNotFoundError` (404)
  - `StorageError` (500)
- **Error Response Format**:
  ```json
  {
    "detail": "Error message",
    "error": {
      "code": "error_code",
      "status_code": 400,
      "request_id": "req-id"
    }
  }
  ```
- **Request ID Tracking**: Added to error headers for traceability

### Logging
- **Structured Logging**: JSON-formatted logs with `log_event()` function
- **Format**: `%(asctime)s %(levelname)s %(name)s %(message)s`
- **Levels**: INFO, WARNING, ERROR, DEBUG
- **JSON Payload**: Events logged with sorted keys for consistency
- **Logger Names**: Module-level loggers (e.g., `__name__`)

### File Organization
- **Source Structure**: 
  ```
  src/
  ├── app/          # FastAPI application
  ├── infra/        # Infrastructure (LLM, storage)
  ├── usecases/     # Business logic
  ├── rag/          # RAG components
  ├── ingestion/    # Data processing
  ├── evals/        # Evaluation pipeline
  ├── config/       # Configuration management
  └── cli/          # CLI commands
  ```
- **Tests**: `tests/` directory with `conftest.py`
- **Fixtures**: `tests/fixtures/` for test data

### Configuration
- **Settings**: Pydantic BaseSettings with .env support
- **Environment**: Development, test, staging, production
- **Secrets**: Environment variables only (no hardcoded values)

### Patterns
- **Dependency Injection**: Custom DI container in `src/infra/di.py`
- **Middleware**: Request ID, auth, rate limiting
- **Async/Await**: Throughout for I/O operations
- **Type Hints**: Required for all functions and classes
- **Protocol**: Defined interfaces for storage

## Frontend (SvelteKit)

### Code Style
- **Language**: TypeScript with strict mode
- **Framework**: SvelteKit with Svelte 5
- **Build Tool**: Vite
- **Testing**: Playwright for E2E tests

### Naming Patterns
- **Components**: PascalCase (e.g., `StepCard.svelte`)
- **Functions**: camelCase (e.g., `getApiBaseUrl`)
- **Variables**: camelCase
- **Constants**: UPPER_SNAKE_CASE

### File Organization
```
frontend/src/
├── routes/         # SvelteKit routes
├── lib/
│   ├── components/ # Reusable components
│   ├── utils/      # Utility functions
│   └── types.ts    # TypeScript definitions
└── tests/          # Playwright tests
```

### Frontend Patterns
- **API Integration**: Centralized API utilities with error handling
- **State Management**: Svelte stores + local state
- **Routing**: File-based routing with +page.svelte
- **Styling**: CSS modules with global styles

## Shared Conventions

### Code Quality
- **Imports**: Explicit imports, avoid relative imports when possible
- **Documentation**: Module-level docstrings, function-level comments
- **Validation**: Pydantic schemas for data models
- **Testing**: Pytest with markers for test categories

### Performance
- **Batch Processing**: For embeddings and operations
- **Caching**: Configurable caching for expensive operations
- **Connection Pooling**: HTTP clients with proper pooling

### Security
- **API Keys**: Environment variables only
- **CORS**: Configurable allowed origins
- **Input Validation**: Pydantic models for all inputs
- **Rate Limiting**: Middleware for API endpoints

### Monitoring
- **Request IDs**: Trace across API boundaries
- **Structured Logging**: JSON for parsing
- **Error Tracking**: Consistent error formats
- **Metrics**: Custom metrics for evaluation pipeline
