# CONVENTIONS.md - Code Style, Patterns

## Python Conventions

### Linting
- **Tool**: Ruff
- **Config**: `pyproject.toml`
- **Target**: Python 3.13
- **Line Length**: 100 characters

```toml
[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]  # Line too long
```

### Type Hints
- Use Python 3.13+ syntax (e.g., `list[str]` instead of `List[str]`)
- Use `Optional[X]` instead of `X | None` for compatibility

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `QwenClient`)
- **Functions/variables**: `snake_case` (e.g., `get_client`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)

### Import Order (per Ruff)
1. Standard library
2. Third-party
3. Local application

## Svelte/TypeScript Conventions

### Component Structure
- Use Svelte 5 runes (`$state`, `$derived`)
- Script at top, styles at bottom
- Props via `let { prop } = $props()`

### File Naming
- Components: `PascalCase.svelte`
- Types: `kebab-case.ts`

### TypeScript
- Strict mode enabled
- Use explicit types for function parameters

## API Design

### REST Endpoints
- `GET` - Retrieve data
- `POST` - Create new resources
- `DELETE` - Remove resources

### Request/Response
- Use Pydantic models for validation
- Include `Union` types for optional fields

## Pipeline Conventions

### Stage Naming
- Prefix pipeline stages with `L{0-6}_` (e.g., `L0_download.py`)
- Each stage has clear single responsibility

### Document Structure
```python
{
    "id": "unique_document_id",
    "source": "source_filename.pdf",
    "page": 1,  # optional
    "content": "document text..."
}
```

## Middleware Order
1. RequestIDMiddleware2. RateLimit (tracing)
Middleware (throttling)
3. APIKeyMiddleware (authentication)

## Error Handling
- Return HTTP 500 for unexpected errors
- Log errors with `logger.error()`
- Never expose internal error details to clients

## Testing Conventions
- Test files: `test_*.py` in `tests/`
- Fixtures: `conftest.py`
- E2E tests: `*.spec.ts` in `frontend/tests/`

## Configuration
- Use Pydantic Settings for environment variables
- Load `.env` file via `python-dotenv`
- Sensible defaults with optional overrides
