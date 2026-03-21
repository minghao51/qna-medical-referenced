# Code Conventions

## Python Code Style

### Formatting
- **Tool**: Ruff (fast Python linter/formatter)
- **Line length**: 100 characters
- **Target version**: Python 3.13
- **Enforced rules**: E, F, I, N, W (ignore E501)
- **Import sorting**: Ruff's `I` rule (isort-compatible)

### Type Hints
- **Required**: All public functions must have type hints
- **Style**: Use `from typing import ...` for compatibility
- **Forward references**: `from __future__ import annotations` at module top
- **Complex types**: Use `|` union syntax (Python 3.10+)
  ```python
  def process(data: str | None) -> dict[str, Any]:
      pass
  ```

### Docstrings
- **Style**: Google-style docstrings preferred
- **Module docstrings**: Describe purpose and key exports
- **Class docstrings**: Describe responsibility and usage
- **Function docstrings**: Args, returns, raises, examples

```python
def stream_chat_message(
    llm_client: QwenClient,
    history_store: ChatHistoryStore,
    message: str,
    session_id: str,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Stream chat responses with RAG retrieval.

    Args:
        llm_client: Qwen LLM client for generation.
        history_store: Chat history storage.
        message: User message to process.
        session_id: Chat session identifier.

    Yields:
        Tuples of (content_chunk, metadata_dict).
    """
```

### Imports
- **Order**: Standard library → Third-party → Local
- **Style**: Absolute imports from `src` package
- **Avoid**: Star imports (`from module import *`)

```python
# Standard library
import logging
from dataclasses import dataclass

# Third-party
from fastapi import APIRouter
from pydantic import BaseModel

# Local
from src.config import settings
from src.app.middleware import APIKeyMiddleware
```

## Error Handling

### Exception Hierarchy
```python
# Base application exception
class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500, code: str = "application_error"):
        self.message = message
        self.status_code = status_code
        self.code = code

# Specific exceptions
class InvalidInputError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=400, code="invalid_input")

class UpstreamServiceError(AppError):
    def __init__(self, message: str = "Upstream service failure"):
        super().__init__(message, status_code=502, code="upstream_service_error")
```

### Error Handling Patterns

**In endpoints**:
```python
try:
    result = await some_operation()
except InvalidInputError as e:
    raise HTTPException(status_code=400, detail=e.message)
except UpstreamServiceError as e:
    logger.error(f"Upstream failure: {e.message}")
    raise
```

**In use cases**:
```python
try:
    document = await load_document(doc_id)
except FileNotFoundError:
    raise ArtifactNotFoundError(f"Document {doc_id} not found")
except PermissionError as e:
    raise StorageError(f"Cannot access document: {e}")
```

**Logging errors**:
```python
logger.error(
    "Retrieval failed",
    extra={"query": query, "error": str(e), "session_id": session_id}
)
```

## Logging

### Structured Logging
```python
from src.app.logging import log_event
import logging

logger = logging.getLogger(__name__)

# Structured event logging
log_event(
    logger,
    logging.INFO,
    "chat_request_received",
    session_id=session_id,
    message_length=len(message),
)

# Standard logging
logger.info("Processing chat request", extra={"session_id": session_id})
```

### Log Levels
- **DEBUG**: Detailed debugging information
- **INFO**: Normal operation (request received, processing complete)
- **WARNING**: Something unexpected but recoverable
- **ERROR**: Error that prevented operation
- **CRITICAL**: Serious error requiring immediate attention

## Async/Await Patterns

### Async Functions
```python
# Always async for I/O operations
async def fetch_document(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text

# Async generators for streaming
async def stream_response() -> AsyncIterator[str]:
    async for chunk in llm_client.generate():
        yield chunk
```

### Async Context Managers
```python
# Always use context managers for resources
async with httpx.AsyncClient() as client:
    await client.post(url, json=data)

# For async file operations
async with aiofiles.open(path, mode="r") as f:
    content = await f.read()
```

## Configuration Patterns

### Settings Access
```python
# Import settings singleton
from src.config import settings

# Access configuration
api_key = settings.dashscope_api_key
model_name = settings.model_name

# Use defaults for optional settings
timeout = settings.request_timeout_seconds
```

### Runtime Configuration
```python
# Dynamic configuration loading
from src.ingestion.indexing.vector_store import (
    get_vector_store_runtime_config,
    set_vector_store_runtime_config,
)

config = get_vector_store_runtime_config()
config.overfetch_multiplier = 4
set_vector_store_runtime_config(config)
```

## Testing Conventions

### Test Structure
```python
# Arrange-Act-Assert pattern
def test_chat_requires_valid_api_key(monkeypatch, tmp_path):
    # Arrange
    client = _build_client(monkeypatch, tmp_path, api_keys="secret-key")

    # Act
    response = client.post("/chat", json={"message": "hello"})

    # Assert
    assert response.status_code == 401
```

### Test Fixtures
```python
# In conftest.py
@pytest.fixture
def mock_llm_client():
    client = Mock()
    client.generate.return_value = "Test response"
    return client

@pytest.fixture
def temp_history_store(tmp_path):
    return FileChatHistoryStore(tmp_path / "history.json")
```

### Test Markers
```python
# Live API tests
@pytest.mark.live_api
def test_qwen_client_actual_call():
    pass

# Slow tests
@pytest.mark.slow
def test_full_ingestion_pipeline():
    pass

# E2E tests
@pytest.mark.e2e_real_apis
def test_backend_e2e_real_apis():
    pass
```

## FastAPI Patterns

### Route Definition
```python
from fastapi import APIRouter, Query, Request
from src.app.schemas import ChatRequest

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(
    request: Request,
    payload: ChatRequest,
    include_pipeline: bool = Query(False),
) -> StreamingResponse:
    """Process chat message with RAG."""
    return StreamingResponse(
        chat_stream_generator(request, payload, include_pipeline)
    )
```

### Dependency Injection
```python
# Use dependencies for shared logic
from fastapi import Depends, Header

async def get_auth_context(x_api_key: str = Header(...)) -> AuthContext:
    validate_api_key(x_api_key)
    return AuthContext(key_id="key-1")

@router.get("/protected")
async def protected_endpoint(auth: AuthContext = Depends(get_auth_context)):
    return {"user": auth.owner}
```

### Middleware
```python
# Middleware order: CORS → RateLimit → APIKey → RequestID
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(RateLimitMiddleware, ...)
app.add_middleware(APIKeyMiddleware, ...)
app.add_middleware(RequestIDMiddleware, ...)
```

## Frontend Conventions (Svelte)

### Component Structure
```svelte
<script lang="ts">
  // Imports first
  import { onMount } from 'svelte';

  // Props interface
  interface Props {
    message: string;
    onSend?: (message: string) => void;
  }

  // Component state
  let { message, onSend }: Props = $props();
  let sending = $state(false);
</script>

<!-- Template -->
<div class="chat-container">
  <p>{message}</p>
  <button onclick={() => onSend?.(message)}>Send</button>
</div>

<!-- Styles -->
<style>
  .chat-container {
    padding: 1rem;
  }
</style>
```

### TypeScript Usage
- **Strict mode**: Enabled in `tsconfig.json`
- **Type safety**: All components typed
- **Interfaces**: For props and events

## Database/File Storage

### File Operations
```python
# Use pathlib for paths
from pathlib import Path

data_dir = Path("data")
data_dir.mkdir(exist_ok=True)

# Context managers for file handling
with open(data_dir / "config.json", "r") as f:
    config = json.load(f)

# Atomic writes
temp_path = path.with_suffix(".tmp")
temp_path.write_text(content)
temp_path.replace(path)
```

### SQLite Operations
```python
# Connection handling
import sqlite3

def get_db_connection(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Always use transactions
with conn:
    conn.execute("INSERT INTO rates (key, count) VALUES (?, ?)", (key, 1))
```

## Security Conventions

### API Key Handling
```python
# Hash keys before storage
def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()

# Compare hashes only
def validate_api_key(presented_key: str, stored_hash: str) -> bool:
    return _hash_secret(presented_key) == stored_hash
```

### Sensitive Data
- **Never log**: API keys, passwords, tokens
- **Use environment variables**: For all secrets
- **Don't commit**: `.env` files
- **Sanitize logs**: Remove sensitive fields

```python
# Bad
logger.info(f"API key: {api_key}")

# Good
logger.info("API key validated successfully")
```

## Performance Conventions

### Caching
```python
# Use functools.lru_cache for pure functions
from functools import lru_cache

@lru_cache(maxsize=128)
def get_embedding_model():
    return load_model()

# Custom caching with expiration
_cached_config = None
_config_timestamp = None

def get_config_with_cache(ttl_seconds: int = 60):
    global _cached_config, _config_timestamp
    now = time.time()
    if _cached_config is None or (now - _config_timestamp) > ttl_seconds:
        _cached_config = load_config()
        _config_timestamp = now
    return _cached_config
```

### Streaming
```python
# Always stream large responses
async def stream_large_response():
    async for chunk in generate_content():
        yield chunk
```

### Connection Pooling
```python
# Reuse HTTP clients
http_client = httpx.AsyncClient(timeout=30.0)

# Clean up on shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await http_client.aclose()
```

## Code Quality

### Code Review Checklist
- [ ] Type hints present and correct
- [ ] Docstrings for public functions
- [ ] Error handling implemented
- [ ] Logging added for important operations
- [ ] Tests cover happy path and error cases
- [ ] No hardcoded secrets
- [ ] Efficient use of async/await
- [ ] Proper resource cleanup (context managers)

### Refactoring Indicators
- **Large files**: >500 lines consider splitting
- **Complex functions**: >50 lines consider breaking down
- **Deep nesting**: >4 levels consider refactoring
- **Repeated code**: Extract to shared utilities
- **God classes**: Too many responsibilities → separate classes
