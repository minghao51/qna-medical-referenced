# Tech Stack

## Languages & Versions

| Language   | Version | Notes                          |
|------------|---------|--------------------------------|
| Python     | 3.12    | Backend (`requires-python = ">=3.12,<3.13"`) |
| TypeScript | 5.9+    | Frontend (SvelteKit)           |
| Svelte     | 5.49+   | Frontend framework (runes API) |
| SQL/HTML/CSS | —    | Via SvelteKit components       |

## Runtime / Platform

- **Backend:** Python 3.12 on `python:3.12-slim` Docker image
- **Frontend:** Bun 1.3.9 runtime (`oven/bun:1.3.9-alpine` Docker image), Node adapter for SvelteKit SSR
- **Containerization:** Multi-stage Docker builds (builder + runtime)
- **Orchestration:** Docker Compose (backend, frontend, test services)
- **Package Manager (Python):** [uv](https://docs.astral.sh/uv/) with `uv.lock` (frozen)
- **Package Manager (Frontend):** Bun (`bun.lock`)

## Frameworks

### Backend
- **FastAPI** `>=0.129.0` — ASGI web framework with OpenAPI docs
- **Uvicorn** `>=0.40.0` — ASGI server (production entrypoint via `src.cli.serve_production`)
- **Pydantic Settings** `>=2.6.0` — Environment/config management via `BaseSettings`

### Frontend
- **SvelteKit 2** (`@sveltejs/kit ^2.50.2`) — Full-stack Svelte framework
- **Svelte 5** (`^5.49.2`) — UI framework with runes reactivity model
- **Vite 7** (`^7.3.1`) — Build tool and dev server
- **@sveltejs/adapter-node** `^5.5.4` — Production Node.js adapter

## Key Dependencies

### Backend (from `pyproject.toml`)

| Package                  | Version Constraint    | Purpose                                      |
|--------------------------|-----------------------|----------------------------------------------|
| `fastapi`                | `>=0.129.0`           | ASGI web framework                           |
| `uvicorn`                | `>=0.40.0`            | ASGI server                                  |
| `openai`                 | `>=1.0.0`             | OpenAI-compatible API client (Qwen/Dashscope)|
| `litellm`                | `>=1.0.0`             | Multi-provider LLM gateway (OpenRouter, etc.)|
| `chromadb`               | `>=0.4.0`             | Vector database for RAG embeddings           |
| `wandb`                  | `>=0.23.0`            | Experiment tracking (Weights & Biases)       |
| `bcrypt`                 | `>=4.0.0`             | API key hashing                              |
| `httpx`                  | `>=0.28.1`            | Async HTTP client (downloading PDFs/web)     |
| `nltk`                   | `>=3.9.2`             | NLP: tokenization, stopwords, stemming       |
| `pydantic-settings`      | `>=2.6.0`             | Config from env vars                         |
| `python-dotenv`          | `>=1.2.1`             | `.env` file loading                          |
| `pypdf`                  | `>=4.0,<6.0`          | PDF text extraction                          |
| `pdfplumber`             | `>=0.11.4`            | PDF table/text extraction                    |
| `pymupdf`                | `>=1.24.0`            | PDF rendering and extraction                 |
| `beautifulsoup4`         | `>=4.13.0`            | HTML parsing                                 |
| `readability-lxml`       | `>=0.8.0`             | Article content extraction from HTML         |
| `markdownify`            | `>=0.14.0`            | HTML to Markdown conversion                  |
| `trafilatura`            | `>=1.12.2`            | Web content extraction                       |

### Optional Backend Dependencies

| Group         | Packages                                           | Purpose                                |
|---------------|----------------------------------------------------|----------------------------------------|
| `dev`         | `pytest`, `ruff`, `mypy`, `playwright`, `pytest-asyncio` | Development tooling              |
| `evaluation`  | `deepeval`, `langchain`, `langchain-community`, `langchain-core`, `langchain-openai` | LLM evaluation framework |
| `chunkers`    | `chonkie[semantic]`                                | Semantic chunking                       |
| `extraction`  | `camelot-py`                                       | PDF table extraction                    |
| `reranking`   | `sentence-transformers`                            | Cross-encoder reranking (`BAAI/bge-reranker-base`) |
| `medical`     | `spacy`                                            | NER / medical entity detection          |
| `test`        | `dev + evaluation + pytest-asyncio`                | Full test suite                         |

### Frontend (from `package.json`)

| Package              | Version     | Purpose                            |
|----------------------|-------------|------------------------------------|
| `svelte`             | `^5.49.2`   | UI framework                       |
| `@sveltejs/kit`      | `^2.50.2`   | SvelteKit framework                |
| `@sveltejs/adapter-node` | `^5.5.4` | Node.js production adapter      |
| `vite`               | `^7.3.1`    | Build tool                         |
| `typescript`         | `^5.9.3`    | Type checking                      |
| `chart.js`           | `^4.5.1`    | Data visualization charts          |
| `marked`             | `4`         | Markdown rendering                 |
| `highlight.js`       | `11.9.0`    | Syntax highlighting                |
| `mermaid`            | `^11.14.0`  | Diagram rendering                  |
| `svelte-markdown`    | `0.4.1`     | Markdown component for Svelte      |
| `@playwright/test`   | `^1.58.2`   | E2E browser testing                |

## Build Tools & Config

### Backend Build
- **Package manager:** uv (Astral)
- **Lock file:** `uv.lock` (frozen resolution)
- **Docker:** Multi-stage `Dockerfile` (builder: `python:3.12-slim` + gcc/g++, runtime: `python:3.12-slim`)
- **Docker Compose:** 3 services (backend, frontend, test), resource limits (1 CPU/1GB backend, 0.5 CPU/256MB frontend)
- **Entrypoint:** `python -m src.cli.serve_production` (production), `uvicorn` dev server for development

### Frontend Build
- **Build tool:** Vite 7 with `@sveltejs/vite-plugin-svelte`
- **Docker:** Multi-stage `Dockerfile` (builder: `oven/bun:1.3.9-alpine`, runtime: `oven/bun:1.3.9-alpine`)
- **Adapter:** `@sveltejs/adapter-node` (SSR-capable Node server)
- **Build output:** `build/` directory, served via `bun run start`

## Development Tooling

### Linting & Formatting
| Tool     | Config Location     | Settings                                         |
|----------|---------------------|--------------------------------------------------|
| **Ruff** | `[tool.ruff]` in `pyproject.toml` | `line-length = 100`, `target-version = "py312"`, rules: `E, F, I, N, W` (ignores `E501`) |
| **mypy** | `[tool.mypy]` in `pyproject.toml` | `python_version = "3.12"`, `strict_optional`, `ignore_missing_imports = true` |
| **svelte-check** | `npm run check` | TypeScript and Svelte type checking via `svelte-check` |

### Testing
| Layer      | Runner       | Config                    | Scope                                    |
|------------|--------------|---------------------------|------------------------------------------|
| Backend    | pytest       | `[tool.pytest.ini_options]` | 431+ tests, markers: `live_api`, `deepeval`, `e2e_real_apis`, `slow` |
| Frontend   | Playwright   | `playwright.config.ts`    | Chromium, E2E tests in `frontend/tests/` |
| Docker E2E | Playwright   | `Dockerfile.test`         | Full stack E2E via docker-compose `test` profile |

### CI/CD (GitHub Actions)
- **`ci.yml`**: 3 parallel jobs — backend (ruff + pytest), frontend (check + build), docker (build both images)
- **`docs-consistency.yml`**: Runs `scripts/check_docs_consistency.sh` for doc integrity

### Environment Management
- **dotenvx** for encrypted env var management
- **`.env.example`** as template with documented variables
- **`python-dotenv`** + **`pydantic-settings`** for runtime config loading
