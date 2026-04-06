# Technology Stack

**Analysis Date:** 2026-04-06

## Languages

**Primary:**
- Python 3.13+ - Backend API, RAG pipeline, ingestion, evaluation
- TypeScript 5.9 - Frontend web application

**Secondary:**
- HTML/CSS - Svelte templates

## Runtime

**Environment:**
- Python 3.13+ (CPython)
- Node.js (via @sveltejs/adapter-node)

**Package Managers:**
- uv - Python dependency management (uv.lock present)
- Bun - Frontend dependency management (bun.lock present)

## Frameworks

**Core:**
- FastAPI 0.129+ - Backend REST API framework
- SvelteKit 2.50+ - Frontend full-stack framework
- Svelte 5.49+ - Frontend UI components
- Vite 7.3+ - Frontend build tool

**Testing:**
- pytest 8.0+ / 9.0+ - Python unit/integration tests
- Playwright 1.58+ - Frontend E2E tests
- DeepEval 2.0+ - RAG evaluation framework

**Build/Dev:**
- Ruff 0.8+ / 0.15+ - Python linting and formatting
- mypy 1.19+ - Python static type checking
- svelte-check 4.3+ - Svelte type checking

## Key Dependencies

**Critical:**
- openai 1.0+ - LLM client (used with Alibaba Dashscope/Qwen)
- chromadb 0.4+ - Vector database for document embeddings
- pydantic-settings 2.6+ - Environment-based configuration
- uvicorn 0.40+ - ASGI server for FastAPI

**LLM & AI:**
- sentence-transformers 3.0+ (optional) - Cross-encoder reranking
- chonkie 1.0+ (optional) - Semantic chunking
- nltk 3.9+ - Text processing utilities

**Document Processing:**
- pypdf 4.0-5.x - PDF parsing
- pdfplumber 0.11+ - PDF text extraction
- pymupdf 1.24+ - PDF rendering and extraction
- trafilatura 1.12+ - Web content extraction
- readability-lxml 0.8+ - HTML readability extraction
- beautifulsoup4 4.13+ - HTML parsing
- markdownify 0.14+ - HTML to Markdown conversion

**Experiment Tracking:**
- wandb 0.23+ - Weights & Biases experiment logging

**Frontend:**
- chart.js 4.5+ - Data visualization
- highlight.js 11.9 - Syntax highlighting
- svelte-markdown 0.4 - Markdown rendering

## Configuration

**Environment:**
- .env file via python-dotenv and pydantic-settings
- VITE_API_URL for frontend API connection
- DASHSCOPE_API_KEY required for LLM operations

**Build:**
- pyproject.toml - Python project config, ruff, mypy, pytest
- tsconfig.json - TypeScript compiler options
- docker-compose.yml - Multi-service orchestration
- Dockerfile (backend + frontend)

## Platform Requirements

**Development:**
- Python 3.13+
- Bun (or npm as fallback)
- Docker (optional, for containerized dev)

**Production:**
- Docker containers (backend + frontend)
- Backend: 1 CPU, 1GB RAM minimum
- Frontend: 0.5 CPU, 256MB RAM minimum
- Persistent storage for ChromaDB (data/chroma) and raw data (data/raw)

---

*Stack analysis: 2026-04-06*
