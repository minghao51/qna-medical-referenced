# Dependency Management Guide

## Overview

Dependencies are organized using uv-native `[dependency-groups]`. Base runtime deps are in `[project] dependencies`; everything else is in groups.

## Dependency Groups

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=7.1.0",
    "ruff>=0.15.1",
    "mypy>=1.19.1",
    "playwright>=1.58.0",
    "pre-commit>=3.0.0",
    "bandit>=1.7.0",
]
evaluation = [
    "deepeval>=3.9.0,<4.0.0",
    "langchain<1",
    "langchain-community<1",
    "langchain-core<1",
    "langchain-openai<1",
]
chunkers = ["chonkie[semantic]>=1.0.0"]
extraction = ["camelot-py>=0.12.0"]
reranking = ["sentence-transformers>=3.0.0"]
medical = ["spacy>=3.8.0"]
docs = [
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.25",
    "pymdown-extensions>=10.0",
    "matplotlib>=3.8.0",
    "nbformat>=5.0",
    "ipykernel>=6.0",
    "nbclient>=0.10.4",
]
```

## Installation Commands

| Scenario | Command | What's Included |
|----------|---------|-----------------|
| Production / minimal | `uv sync` | Base runtime deps only |
| Development | `uv sync --dev` | Base + dev tools |
| Full test suite | `uv sync --dev --group evaluation` | Base + dev + evaluation |
| Evaluation tests | `uv sync --group evaluation` | Base + evaluation |
| Chunker work | `uv sync --group chunkers` | Base + chunkers |
| PDF extraction | `uv sync --group extraction` | Base + extraction |
| Reranking | `uv sync --group reranking` | Base + reranking |
| Everything | `uv sync --all-groups` | All groups |

## Test Requirements

| Test Type | Required Group |
|-----------|---------------|
| Unit tests | None (base deps) |
| Async tests | `dev` |
| Evaluation tests | `evaluation` |
| Chunker tests | `chunkers` |
| PDF extraction tests | `extraction` |

## Common Issues

### "ModuleNotFoundError: No module named 'deepeval'"

```bash
uv sync --group evaluation
```

### "async def functions are not natively supported"

```bash
uv sync --dev
```

### Tests fail after `uv sync`

```bash
uv sync --dev --group evaluation
```

## Quick Reference

```bash
# Full development setup
uv sync --dev --group evaluation

# Production setup
uv sync

# Run all tests
uv run pytest

# Run specific test types
uv run pytest tests/test_hyde.py           # Async tests
uv run pytest tests/test_eval_deepeval.py # Evaluation tests
uv run pytest -m "not deepeval"           # Skip evaluation tests
```
