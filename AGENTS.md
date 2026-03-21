# Agent Instructions for qna-medical-referenced

This file provides guidance for agentic coding agents working in this repository.

## Project Overview

Medical Q&A chatbot with RAG pipeline for health screening interpretation. The application uses FastAPI backend with a SvelteKit frontend, ChromaDB for vector storage, and integrates with Qwen LLM models via Dashscope API.

## Build/Lint/Test Commands

### Backend (Python)
```bash
# Install dependencies
uv sync

# Run development server (port 8000)
uv run python -m src.cli.serve

# Run production server
uv run python -m src.cli.serve_production

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/test_chat_sources.py

# Run a single test function
uv run pytest tests/test_chat_sources.py::test_chat_returns_sources

# Run tests matching a pattern
uv run pytest -k "chat and not slow"

# Skip slow tests
uv run pytest -m "not slow"

# Lint
uv run ruff check .

# Format check
uv run ruff format --check .

# Type check
uv run mypy src/
```

### Frontend (SvelteKit/TypeScript)
```bash
cd frontend

# Install dependencies
npm install

# Run development server (port 5173)
bun run dev

# Type check
npm run check

# Run Playwright tests
npm run test

# Run e2e tests specifically
npm run e2e
```

### Docker
```bash
# Start all services (backend + frontend)
docker-compose up

# Rebuild after code changes
docker-compose up --build

# Stop services
docker-compose down
```

## Code Style Guidelines

### Python (Backend)

**Line Length:** 100 characters (configured in ruff)

**Import Order:**
1. Standard library (`json`, `logging`, `time`)
2. Third-party packages (`fastapi`, `pydantic`, `uvicorn`)
3. Local application imports (`src.app`, `src.config`, `src.usecases`)

```python
import json
import logging
import time
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from src.app.logging import log_event
from src.config import settings
from src.usecases.chat import stream_chat_message
```

**Type Annotations:** Use type hints for all function parameters and return values. Use `Any` when the type is unknown.

**Pydantic Models:** Use for API schemas and settings. Use `Field()` for validation.

```python
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, max_length=128)

    @field_validator("message", mode="before")
    @classmethod
    def sanitize_message(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value
```

**Error Handling:** Use domain-specific exceptions extending `AppError` (defined in `src/app/exceptions.py`):
- `InvalidInputError` (400)
- `UpstreamServiceError` (502)
- `ArtifactNotFoundError` (404)
- `StorageError` (500)

**Async Patterns:** Use `async for` for streaming generators. Use `@asynccontextmanager` for lifespan management.

**Middleware Order (Important):** CORS must be first, then RateLimit, then APIKey, then RequestID outermost.

**Docstrings:** Use Google-style docstrings for modules and public functions:
```python
"""Module purpose and usage.

More details about the module...

Example:
    Usage example here.
"""

def process_chat_message(
    *,
    llm_client: Any,
    message: str,
    session_id: Optional[str],
) -> dict[str, Any]:
    """Process a chat message with RAG.

    Args:
        llm_client: LLM client instance
        message: User's question
        session_id: Session identifier

    Returns:
        Dictionary containing response, sources, and pipeline trace.
    """
```

### SvelteKit/TypeScript (Frontend)

**Naming:** Use PascalCase for components (`ChatMessage.svelte`), camelCase for utilities (`formatDate.ts`).

**Types:** Define interfaces in `src/lib/types.ts`. Use TypeScript strict mode.

**Components:** Use Svelte 5 runes syntax (`$state`, `$derived`, `$props`).

## Architecture Overview

### Backend Structure
```
src/
├── app/              # FastAPI application
│   ├── factory.py    # App creation and middleware setup
│   ├── routes/       # API endpoints (chat, health, history, evaluation)
│   ├── schemas/      # Pydantic request/response models
│   ├── middleware/   # Rate limiting, API key auth, request ID
│   ├── exceptions.py # Domain exceptions and handlers
│   └── session.py    # Chat session management
├── config/           # Settings from environment variables
├── cli/              # CLI entrypoints (serve, ingest, eval_pipeline)
├── usecases/        # Business logic orchestration
├── rag/             # Retrieval and formatting logic
├── infra/           # External service integrations (LLM, storage)
└── experiments/     # Evaluation and tracking (W&B, DeepEval)
```

### Frontend Structure
```
frontend/src/
├── routes/          # SvelteKit pages (+page.svelte)
├── lib/
│   ├── components/  # Reusable UI components
│   ├── utils/      # Helper functions
│   └── types.ts    # TypeScript interfaces
└── app.html         # HTML template
```

### Key API Endpoints
- `POST /chat` - Streaming RAG chat endpoint
- `GET /health` - Health check
- `GET /history/{session_id}` - Retrieve chat history
- `POST /evaluation/run` - Trigger evaluation pipeline

### Environment Variables
Set in `.env` file or environment:
- `DASHSCOPE_API_KEY` - Qwen API key (required)
- `MODEL_NAME` - Qwen model (default: qwen3.5-flash)
- `WANDB_API_KEY` - Weights & Biases (optional)
- `RATE_LIMIT_PER_MINUTE` - Rate limit (default: 60)

## Development Workflow

1. **Before making changes:** Read relevant existing code files to understand patterns
2. **Keep changes small:** Each change should impact minimal code
3. **Check CLAUDE.md:** Contains project-specific guidance
4. **Run verification:** After changes, run lint, type check, and tests

## Testing Markers
- `live_api` - Requires live Qwen API access (`RUN_LIVE_QWEN_TESTS=1`)
- `deepeval` - DeepEval integration tests (slow)
- `e2e_real_apis` - Real API E2E tests (`ENABLE_REAL_API_TESTS=1`)
- `slow` - Slow tests (skip with `-m "not slow"`)
