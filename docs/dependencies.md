# Dependency Management Guide

## Overview

This project uses TWO different dependency systems in `pyproject.toml`:

1. **`[dependency-groups]`** (New style, installed by default)
2. **`[project.optional-dependencies]`** (Old style, requires `--extra` flags)

## Dependency Structure

### 1. `[dependency-groups]` - Installed with `uv sync`

```toml
[dependency-groups]
dev = [
    "mypy>=1.19.1",
    "playwright>=1.58.0",
    "pytest>=9.0.2",
    "pytest-asyncio>=0.23.0",  # ✅ Auto-installed
    "ruff>=0.15.1",
]
```

These are installed automatically with `uv sync`.

### 2. `[project.optional-dependencies]` - Requires `--extra` flags

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0.0", "ruff>=0.8.0"]
evaluation = ["deepeval>=2.0.0", "litellm>=1.0.0"]  # ❌ Manual install
chunkers = ["chonkie[semantic]>=1.0.0"]           # ❌ Manual install
extraction = ["camelot-py>=0.12.0"]               # ❌ Manual install
test = [
    "qna-medical-referenced[dev,evaluation]",
    "pytest-asyncio>=0.23.0",
]
```

These require explicit installation with `--extra` flags.

## Installation Commands

### For Development (Recommended)

```bash
# Install ALL dependencies including test dependencies
uv sync --extra test
```

This installs:
- All base dependencies
- All dev dependencies
- All evaluation dependencies (deepeval, litellm)
- pytest-asyncio for async tests

### For Production

```bash
# Install only runtime dependencies
uv sync
```

This installs:
- All base dependencies
- `[dependency-groups]` (includes mypy, playwright, pytest, ruff)
- BUT NOT evaluation or chunker dependencies

### Install Specific Extras

```bash
# Install only evaluation dependencies
uv sync --extra evaluation

# Install only chunker dependencies
uv sync --extra chunkers

# Install all optional dependencies
uv sync --all
```

## Test Requirements

To run the full test suite, you need:

```bash
uv sync --extra test
uv run pytest
```

### What Tests Need Which Dependencies

| Test Type | Required Dependencies | Installation |
|-----------|----------------------|--------------|
| Unit tests | Base dependencies | `uv sync` |
| Async tests | pytest-asyncio | `uv sync --extra test` |
| Evaluation tests | deepeval, litellm | `uv sync --extra evaluation` |
| Chunker tests | chonkie | `uv sync --extra chunkers` |
| PDF extraction tests | camelot-py | `uv sync --extra extraction` |

## Why Two Systems?

The project is in transition:
- **Old style**: `[project.optional-dependencies]` (standard Python)
- **New style**: `[dependency-groups]` (uv-specific, more powerful)

The `test` extra was created to bridge both systems and provide a single command for developers.

## Common Issues

### Issue: "ModuleNotFoundError: No module named 'deepeval'"

**Solution:**
```bash
uv sync --extra evaluation
```

### Issue: "async def functions are not natively supported"

**Solution:**
```bash
uv sync --extra test
```

### Issue: Tests fail after `uv sync`

**Solution:**
```bash
# Make sure you're installing test dependencies
uv sync --extra test
```

## Quick Reference

```bash
# Full development setup
uv sync --extra test

# Production setup
uv sync

# Run all tests
uv run pytest

# Run specific test types
uv run pytest tests/test_hyde.py           # Async tests
uv run pytest tests/test_eval_deepeval.py # Evaluation tests
uv run pytest -m "not deepeval"           # Skip evaluation tests
```
