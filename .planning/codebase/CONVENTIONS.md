# Code Conventions

This document outlines the coding standards and conventions used throughout the qna-medical-referenced codebase.

## Python Code Style

### Linting and Formatting

The project uses **Ruff** for linting and code formatting:

```bash
# Run linter
uv run ruff check .

# Format code
uv run ruff format .

# Check formatting without making changes
uv run ruff format --check .
```

**Configuration** (`pyproject.toml`):
- Line length: 100 characters
- Target Python version: 3.13
- Enabled rule sets: E (errors), F (pyflakes), I (import sorting), N (naming), W (warnings)
- Ignored: E501 (line length handled by formatter)

### Type Checking

**MyPy** is used for static type checking:

```bash
uv run mypy src/planweaver
```

**Configuration**:
- Python version: 3.13
- Warn on return_any and unused_configs
- Ignore missing imports for third-party libraries (nltk, google, deepeval)
- Disabled error codes: `import-untyped`, `annotation-unchecked`

### Naming Conventions

**Functions and Variables**: `snake_case`
```python
def process_chat_message(*, llm_client, message: str) -> dict[str, Any]:
    chat_start = time.time()
    resolved_session_id = session_id or "default"
```

**Classes**: `PascalCase`
```python
class AppError(Exception):
    """Base application exception with HTTP semantics."""
```

**Constants**: `UPPER_SNAKE_CASE`
```python
MAX_MESSAGE_LENGTH = 2000
DEFAULT_TOP_K = 5
```

**Private/Internal**: Single leading underscore
```python
def _build_history_context(history: list[dict[str, str]]) -> str:
    """Internal helper function."""
```

### Type Hints

**Mandatory for all function signatures**:
```python
from typing import Any, AsyncGenerator, Optional

def process_chat_message(
    *,
    llm_client: Any,
    history_store: ChatHistoryStore,
    message: str,
    session_id: Optional[str],
    include_pipeline: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
```

**Type preferences**:
- Use `dict[str, Any]` over `Dict` from typing (Python 3.9+ style)
- Use `list[str]` over `List[str]`
- Use `str | None` over `Optional[str]` (but Optional is still used in some places)
- Use `*` to force keyword-only arguments when appropriate

### Error Handling

**Custom exception hierarchy** with domain-specific errors:

```python
@dataclass
class AppError(Exception):
    """Base application exception with HTTP semantics."""
    message: str
    status_code: int = 500
    code: str = "application_error"
    extra: dict[str, Any] | None = None

class InvalidInputError(AppError):
    def __init__(self, message: str, *, extra: dict[str, Any] | None = None):
        super().__init__(message=message, status_code=400, code="invalid_input", extra=extra)

class UpstreamServiceError(AppError):
    def __init__(self, message: str = "Upstream service failure"):
        super().__init__(message=message, status_code=502, code="upstream_service_error")
```

**Error handling patterns**:
- Wrap external API calls with domain exceptions
- Always chain exceptions: `raise UpstreamServiceError(...) from exc`
- Use try-except blocks for cleanup in async generators
- Log errors before re-raising with context

```python
try:
    response = client.generate(prompt=message, context=full_context)
except Exception as exc:
    raise UpstreamServiceError("An error occurred processing your request") from exc
```

### Logging

**Structured logging with JSON payloads**:

```python
import logging
import json

logger = logging.getLogger(__name__)

def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = {"event": event, **{k: v for k, v in fields.items() if v is not None}}
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))
```

**Usage patterns**:
- Module-level loggers: `logger = logging.getLogger(__name__)`
- Structured events with context: `log_event(logger, logging.INFO, "chat_started", session_id=session_id)`
- Error logging with stack traces when needed: `logger.error("Error during stream: %s", exc)`

### Documentation

**Module-level docstrings** (Google style):
```python
"""Chat orchestration logic for RAG-based conversations.

This module contains the core chat processing logic that coordinates retrieval,
generation, and history persistence. It serves as the use case layer that
orchestrates the RAG pipeline and LLM client to produce chat responses.

Flow:
    1. Retrieve conversation history for the session
    2. Perform RAG retrieval (with or without pipeline trace)
    3. Combine history context and retrieved context
    4. Generate response using LLM
    5. Save user message and assistant response to history
    6. Return response with sources and optional pipeline trace

Example:
    Process a chat message:
        from src.usecases.chat import process_chat_message
        from src.infra.llm import get_client

        result = process_chat_message(
            llm_client=get_client(),
            message="What is a normal CBC count?",
            session_id="user-123",
            include_pipeline=True
        )
        print(result["response"])
"""
```

**Function docstrings** (Args/Returns/Side effects):
```python
def process_chat_message(
    *,
    llm_client: Any,
    history_store: ChatHistoryStore,
    message: str,
    session_id: Optional[str],
    include_pipeline: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
    """Run retrieval + generation, persist history, and optionally include a trace.

    This is the main chat processing function that orchestrates the entire
    RAG pipeline. It retrieves relevant context, generates a response, and
    tracks timing information for monitoring and debugging.

    Args:
        llm_client: LLM client instance (QwenClient or compatible)
        message: User's question or message
        session_id: Session identifier for history persistence.
                   If None, uses "default" session
        include_pipeline: If True, includes detailed pipeline trace with timing
        top_k: Number of documents to retrieve from vector store (default: 5)

    Returns:
        Dictionary containing:
            - "response": Generated assistant response text
            - "sources": List of retrieved document sources
            - "pipeline": PipelineTrace object if include_pipeline=True, else None

    Side effects:
        - Saves user message and assistant response to chat history store
        - Updates pipeline trace with timing information if tracing enabled
    """
```

**Inline comments**: Use sparingly, prefer self-documenting code
```python
# Bad: obvious comment
x = x + 1  # increment x

# Good: explain why, not what
resolved_session_id = session_id or "default"  # Use default session if none provided
```

### Code Organization

**Directory structure**:
```
src/
├── app/                 # FastAPI application layer (routes, middleware, schemas)
├── config/              # Configuration and settings
├── evals/               # Evaluation logic and metrics
├── experiments/         # Experiment tracking (W&B integration)
├── ingestion/           # Document processing pipeline (L0-L5)
├── infra/               # Infrastructure services (LLM client, storage)
├── rag/                 # RAG runtime logic
├── source_metadata.py   # Source metadata management
└── usecases/            # Business logic orchestration (chat, pipeline)
```

**Import ordering**:
1. Standard library imports
2. Third-party imports
3. Local application imports (from src.*)

```python
import logging
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException, Request
from pydantic_settings import BaseSettings

from src.app.exceptions import AppError
from src.config import settings
from src.infra.llm import get_client
```

### Configuration

**Pydantic Settings** with environment variable support:

```python
class Settings(BaseSettings):
    """Application configuration with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    dashscope_api_key: str = ""
    """Alibaba Dashscope API key for Qwen models."""

    model_name: str = "qwen3.5-flash"
    """Qwen model to use for text generation."""

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() in {"development", "dev", "local", "test"}

settings = Settings()
```

**Patterns**:
- Use docstrings for field descriptions
- Provide sensible defaults for development
- Use properties for computed values
- Load once at module import time

### Async/Await Patterns

**Async generators for streaming**:
```python
async def stream_chat_message(
    *,
    llm_client: Any,
    message: str,
    session_id: Optional[str],
) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
    """Stream response tokens while performing RAG.

    Yields:
        Tuple of (content, metadata) where:
        - content: Token string (may be empty for metadata-only events)
        - metadata: Dict with keys: done (bool), sources (list), pipeline (dict), error (str)
    """
    try:
        async for token in client.a_generate_stream(prompt=message, context=full_context):
            accumulated_response += token
            yield (token, {"done": False})

        yield ("", {"done": True, "sources": sources})
    except Exception as exc:
        logger.error("Error during stream: %s", exc)
        yield ("", {"done": True, "error": "An error occurred"})
        raise
```

## TypeScript/Svelte Code Style

### Type Definitions

**Interface-based types** for all data structures:

```typescript
export interface RetrievedDocument {
	id: string;
	content: string;
	source: string;
	page?: number;
	semantic_score: number;
	keyword_score: number;
	combined_score: number;
	rank: number;
	chunk_quality_score?: number;
	source_type?: string;
	domain?: string;
}

export interface PipelineTrace {
	query: string;
	timing_ms: number;
	retrieval: RetrievalStage;
	context: ContextStage;
	generation: GenerationStage;
}
```

**Naming conventions**:
- Interfaces: `PascalCase`
- Functions/variables: `camelCase`
- Constants: `UPPER_SNAKE_CASE` or `camelCase` for module-level
- Types: `PascalCase`

### Component Patterns

**Svelte components** use TypeScript with strict typing:
```typescript
export let metricValue: number;
export let threshold: number;
export let label: string;

$: isWarning = metricValue > threshold;
```

### Utility Functions

**Pure functions** for formatting and calculations:

```typescript
export function formatScore(score: number): string {
	return (score * 100).toFixed(1);
}

export function formatPercent(value: number, digits = 1): string {
	return `${(value * 100).toFixed(digits)}%`;
}
```

## General Principles

1. **Simplicity over cleverness**: Choose clear, straightforward code
2. **Explicit over implicit**: Make dependencies and expectations clear
3. **Type safety**: Use type hints to catch errors early
4. **Domain-driven design**: Use business terminology in code
5. **Error visibility**: Always log errors with context
6. **Testability**: Write code that's easy to test in isolation
7. **Documentation**: Document the "why", not the "what"
