# Coding Conventions

**Analysis Date:** 2026-04-06

## Naming Patterns

**Files:**
- Python: `snake_case.py` (e.g., `test_chunker.py`, `chunk_text.py`, `production_profile.py`)
- TypeScript: `kebab-case.ts` (e.g., `playwright.config.ts`)
- Test files: `test_*.py` (backend), `*.spec.ts` (frontend)

**Functions:**
- Python: `snake_case` (e.g., `chunk_documents`, `configure_logging`, `evaluate_answer_quality_async`)
- TypeScript: `camelCase` (e.g., `pressSequentially`, `toHaveTitle`)

**Variables:**
- Python: `snake_case` (e.g., `chunk_size`, `base_url`, `request_id`)
- TypeScript: `camelCase` (e.g., `sendButton`, `mockGen`)

**Types:**
- Python classes: `PascalCase` (e.g., `Settings`, `TextChunker`, `AppError`, `VectorStore`)
- TypeScript types: `PascalCase` (inferred from Svelte conventions)

## Code Style

**Formatting:**
- Ruff with `line-length = 100`, `target-version = "py313"`
- TypeScript uses tabs for indentation (2-space equivalent via SvelteKit defaults)

**Linting:**
- Ruff: `select = ["E", "F", "I", "N", "W"]`, `ignore = ["E501"]`
  - E: pycodestyle errors
  - F: Pyflakes
  - I: isort (import sorting)
  - N: pep8-naming
  - W: pycodestyle warnings
- mypy: strict mode with `warn_return_any`, `warn_unused_ignores`, `warn_redundant_casts`, `strict_optional`
- Frontend: `svelte-check` for type checking (no ESLint/Prettier configured)

## Import Organization

**Order:**
1. Standard library imports (e.g., `import os`, `from pathlib import Path`)
2. Third-party imports (e.g., `import pytest`, `from fastapi import HTTPException`)
3. Local imports (e.g., `from src.config import settings`)

**Path Aliases:**
- Python: No path aliases; uses `src.` prefix (e.g., `from src.config.settings import Settings`)
- TypeScript: SvelteKit `$lib` alias (handled by framework)

## Error Handling

**Patterns:**
- Custom exception hierarchy with `AppError` as base class (`src/app/exceptions.py:13`)
  - `InvalidInputError` (400)
  - `UpstreamServiceError` (502)
  - `ArtifactNotFoundError` (404)
  - `StorageError` (500)
- `ValueError` for validation errors (e.g., `src/config/settings.py`, `src/experiments/config.py`)
- FastAPI exception handlers for `HTTPException`, `AppError`, and generic `Exception`
- Error responses include `code`, `status_code`, `request_id`, and optional `extra` dict
- `pytest.raises` for testing expected exceptions (e.g., `test_chunker.py:128`)
- Broad `except Exception` with logging used in ingestion/evaluation pipelines
- Optional dependencies handled with `except Exception:  # pragma: no cover`

## Logging

**Framework:** Standard Python `logging` module with `dictConfig`

**Patterns:**
- Module-level loggers: `logger = logging.getLogger(__name__)`
- Centralized configuration via `configure_logging()` in `src/app/logging.py`
- Format: `%(asctime)s %(levelname)s %(name)s %(message)s`
- Structured logging helper: `log_event(logger, level, event, **fields)` outputs JSON
- Levels used: `INFO` (startup, operations), `WARNING` (fallbacks, degraded mode), `ERROR` (failures), `DEBUG` (detailed operations)

## Comments

**When to Comment:**
- Docstrings on modules, classes, and public functions
- Configuration fields have detailed docstrings with environment variable names and defaults
- Section dividers used in test files (e.g., `# Network Failure Tests`)

**JSDoc/TSDoc:**
- Python: Google-style docstrings with `Args:`, `Returns:`, `Raises:` sections
- Heavy inline documentation on `Settings` class attributes

## Function Design

**Size:**
- Small, focused functions (typically <50 lines)
- Pipeline steps as separate modules (e.g., `chunk_text.py`, `convert_html.py`)

**Parameters:**
- Configuration objects passed as dataclasses or Pydantic models
- Keyword arguments for optional parameters

**Return Values:**
- Typed returns where practical (e.g., `list[dict]`, `tuple[list, dict]`)
- `None` for side-effect-only functions

## Module Design

**Exports:**
- `__init__.py` files used for package structure (often empty)
- Singleton pattern for `settings` object (`src/config/settings.py:430`)

**Barrel Files:**
- Minimal barrel files; direct imports preferred
- `src/config/__init__.py` re-exports `settings`

---

*Convention analysis: 2026-04-06*
