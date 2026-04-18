# Code Conventions

## Code Style and Formatting

### Python (Backend)
- **Python version:** 3.12 (`requires-python = ">=3.12,<3.13"`)
- **Package manager:** `uv` — always `uv run <command>`, never bare `python`
- **Linting:** Ruff (`uv run ruff check`)
  - `line-length = 100`
  - `target-version = "py312"`
  - Selected rules: `E`, `F`, `I`, `N`, `W`
  - `E501` (line-too-long) is **ignored** — Ruff's line-length acts as a guide, not a hard error
- **Type checking:** mypy (`uv run mypy`)
  - `python_version = "3.12"`
  - `strict_optional = true`
  - `warn_return_any = true`, `warn_unused_ignores = true`, `warn_redundant_casts = true`
  - `ignore_missing_imports = true` (with specific overrides for `nltk`, `google`, `deepeval`)
  - `disable_error_code = ["import-untyped"]`
- **Formatting:** No explicit formatter (black/ruff format) configured — rely on Ruff's line-length guide
- **No pre-commit hooks** configured

### TypeScript/Frontend (SvelteKit 5)
- **Runtime:** Bun 1.2.5
- **Framework:** SvelteKit 5 + TypeScript (strict mode)
- **Type checking:** `svelte-check --tsconfig ./tsconfig.json` via `bun run check`
- **E2E testing:** Playwright
- **Build:** Vite 7

## Naming Conventions

### Files and Directories
- Python modules: `snake_case` (e.g., `vector_store.py`, `chat_history_store.py`)
- Test files: `test_<module_name>.py` (e.g., `test_settings.py`, `test_chunker.py`)
- Frontend: Svelte component files use PascalCase or kebab-case per SvelteKit conventions
- Config/experiment files: `snake_case.yaml` (e.g., `baseline.yaml`, `chunking_strategies.yaml`)
- Docs: `YYYYMMDD-filename.md` format

### Variables and Functions
- Variables: `snake_case` (e.g., `retrieval_options`, `chat_session_id`)
- Functions: `snake_case` (e.g., `retrieve_context`, `build_context_and_sources`)
- Private/internal functions: prefix with underscore (e.g., `_expand_queries`, `_resolve_retrieval_config`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `_VALID_SEARCH_MODES`, `PROJECT_ROOT`, `DATA_DIR`)
- Boolean variables: prefixed with `enable_`, `is_`, `has_`, `should_` (e.g., `enable_reranking`, `is_development`)

### Classes
- PascalCase (e.g., `ChatSource`, `RetrievedDocument`, `PipelineTrace`, `RuntimeState`, `ServiceContainer`)
- Pydantic models: PascalCase (e.g., `ChatRequest`, `ChatResponse`, `Settings`)
- Dataclasses: PascalCase (e.g., `RuntimeRetrievalConfig`, `RetrievalDiversityConfig`, `AssessmentConfig`)
- Exceptions: suffix with `Error` (e.g., `AppError`, `InvalidInputError`, `UpstreamServiceError`)

## Error Handling Patterns

### Exception Hierarchy
- `AppError(Exception)` — base application exception (dataclass with `message`, `status_code`, `code`, `extra`)
  - `InvalidInputError` (400)
  - `UpstreamServiceError` (502)
  - `ArtifactNotFoundError` (404)
  - `StorageError` (500)
- FastAPI exception handlers registered for `AppError`, `HTTPException`, and generic `Exception`
- All error responses include structured JSON: `{ "detail": "...", "error": { "code", "status_code", "request_id" } }`

### Patterns
- Use `raise UpstreamServiceError(...) from exc` for exception chaining
- LLM failures: catch `Exception`, log with `logger.exception(...)`, wrap in domain error
- Error responses always include `X-Request-ID` header when available
- Validation errors handled by Pydantic's `Field` constraints and `field_validator`

## Logging Patterns

### Logger Creation
- Module-level logger: `logger = logging.getLogger(__name__)` (standard pattern everywhere)
- Service classes: `self._logger = logging.getLogger(self.__class__.__name__)` via `BaseService`

### Structured Logging
- Use `log_event(logger, level, "event_name", **fields)` from `src.app.logging` for structured JSON logs
- Use standard `logger.info/warning/error/exception(...)` for formatted messages
- SSE stream failures: log with request context (request_id, session_id)

### Configuration
- Logging configured via `configure_logging(level)` using `dictConfig`
- Format: `"%(asctime)s %(levelname)s %(name)s %(message)s"`
- Level controlled by `settings.log_level` (default: `"INFO"`)

## Type Usage

### Annotations
- Use Python 3.12+ union syntax: `str | None` instead of `Optional[str]`
- Both styles exist in codebase (`Optional` in schemas, `X | None` in newer code)
- Use `from __future__ import annotations` in modules with forward references
- Type `Any` used for external/client dependencies (LLM clients, vector store)
- `dict[str, Any]` for unstructured configuration/options dicts

### Data Models
- **Pydantic BaseModel** for API schemas, request/response models, and trace models
  - Use `Field(...)` with constraints: `Field(..., min_length=1, max_length=2000)`
  - Use `field_validator` for input sanitization
- **dataclasses** for internal config objects and non-serializable data
  - `@dataclass(frozen=True)` for immutable value objects (e.g., `APIKeyRecord`, `AuthContext`)
- **typing.Protocol** for interfaces (e.g., `ChatHistoryStore`)

### Model Patterns
- Pydantic models use `model_config = SettingsConfigDict(...)` for settings
- Use `model_dump()` (not `.dict()`) for serialization
- Properties with `@property` for computed values (e.g., `settings.cors_origins`)

## Common Code Patterns and Idioms

### Application Factory Pattern
- `create_app()` in `src/app/factory.py` builds the FastAPI app
- Middleware added in specific order: CORS → RateLimit → APIKey → RequestID
- Lifespan context manager handles startup/shutdown
- `app.state` holds runtime services (llm_client, chat_history_store, container)

### Dependency Injection
- `ServiceContainer` dataclass in `src/infra/di.py` manages lazy-initialized services
- Global singleton via `get_container()` / `reset_container()`
- Factory pattern for vector stores: `VectorStoreFactory.get_vector_store(config)`
- Constructor injection in services (e.g., `RAGService(vector_store_service)`)

### Configuration
- `src/config/settings.py`: Pydantic `BaseSettings` loads from `.env` and env vars
- Singleton: `settings = Settings()` exported from `src/config/__init__.py`
- `src/config/paths.py`: canonical filesystem paths derived from settings
- `src/config/context.py`: `RuntimeState` for mutable runtime config (thread-safe with `threading.Lock`)
- `configure_runtime_for_experiment()` applies experiment YAML overrides at runtime

### RAG Pipeline
- Entry points: `retrieve_context()` (simple), `retrieve_context_with_trace()` (with timing), `retrieve_context_with_trace_async()` (with HyDE)
- Pipeline stages: query expansion → retrieval → reranking → diversification → context assembly
- Config resolved via `_resolve_retrieval_config(overrides)` with validation and clamping
- Async generators for streaming responses (`stream_chat_message`)

### SSE Streaming
- Chat endpoint returns `StreamingResponse` with `text/event-stream`
- Generator yields `data: {json}\n\n` events
- Terminal event includes `done: True`, sources, pipeline trace, and optional error

### Experiment Configuration
- YAML-based experiment configs loaded via custom YAML parser (`parse_simple_yaml`)
- Deep-merge with defaults via `_deep_merge()`
- Config hashing for cache invalidation (`_config_hash()`)
- Variant support: base config + variant overrides resolved at runtime

## Import Conventions

### Ordering
- Standard library first: `import json`, `import logging`, `from pathlib import Path`
- Third-party next: `from fastapi import ...`, `from pydantic import ...`, `import pytest`
- Local imports last: `from src.config import settings`, `from src.rag.runtime import ...`

### Patterns
- Absolute imports from `src.` package root: `from src.config import settings`
- Lazy imports inside functions for heavy dependencies: `from src.rag.hyde import ...` (avoids circular imports and defers loading)
- Re-exports via `__init__.py`: `from src.config.settings import settings as settings`
- `from __future__ import annotations` at top of files using forward references or modern type syntax
