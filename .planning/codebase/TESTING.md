# TESTING.md - Framework, Structure

## Testing Overview

| Type | Framework | Location |
|------|-----------|----------|
| Backend Unit Tests | pytest | `tests/` |
| Frontend E2E | Playwright | `frontend/tests/` |

## Backend Testing (pytest)

### Configuration
```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

### Test Files
- `tests/test_chunker.py` - Text chunking
- `tests/test_embedding.py` - Embedding functionality
- `tests/test_keyword_index.py` - TF-IDF index
- `tests/test_pdf_loader.py` - PDF loading
- `tests/test_retrieval.py` - RAG retrieval
- `tests/test_settings.py` - Configuration
- `tests/conftest.py` - Shared fixtures

### Running Backend Tests
```bash
uv run pytest
```

### Example Test Structure
```python
# tests/test_chunker.py
import pytest
from src.pipeline.L3_chunker import chunk_documents

def test_chunk_text():
    documents = [{"id": "doc1", "source": "test.pdf", "content": "..."}]
    chunks = chunk_documents(documents)
    assert len(chunks) > 0
```

## Frontend Testing (Playwright)

### Configuration
```typescript
// playwright.config.ts (implicit in docker-compose)
- Browser: Chromium
- Base URL: http://localhost:5173
- Headless: true (CI mode)
```

### Test Files
- `frontend/tests/chat.spec.ts` - Chat functionality
- `frontend/tests/pipeline.spec.ts` - Pipeline panel display

### Running Frontend Tests
```bash
# Via docker-compose
docker-compose up test

# Or locally
cd frontend && bunx playwright test
```

### Example Test
```typescript
// frontend/tests/chat.spec.ts
import { test, expect } from '@playwright/test';

test('chat sends message', async ({ page }) => {
  await page.goto('/');
  await page.fill('textarea', 'What is LDL?');
  await page.click('button:has-text("Send")');
  await expect(page.locator('.message.assistant')).toBeVisible();
});
```

## Test Fixtures

### Backend Fixtures (`tests/conftest.py`)
- Shared test data
- Mock configurations
- Helper functions

### Golden Files (`tests/fixtures/`)
- `golden_queries.json` - Test query/response pairs

## Docker Compose Testing

```bash
# Run full test suite
docker-compose up test

# Services started
# - backend: http://localhost:8001
# - frontend: http://localhost:5174
# - test: runs Playwright tests
```

## Coverage Areas

### Backend
- [x] PDF loading
- [x] Text chunking
- [x] Keyword indexing
- [x] Vector search
- [x] Settings validation

### Frontend
- [x] Chat message display
- [x] Pipeline trace panel
- [x] Error handling

## Linting

```bash
# Python linting
uv run ruff check .

# Type checking
cd frontend && bun run check
```
