# Technology Stack

## Languages

### Python
- **Version**: 3.13
- **Runtime**: CPython (managed via uv)
- **Purpose**: Backend API, RAG pipeline, evaluation, data ingestion

### TypeScript
- **Version**: 5.9.3
- **Purpose**: Frontend type safety and development

### JavaScript
- **Runtime**: Bun 1.2.5 (build), Node.js 20 (runtime)
- **Purpose**: Frontend application

## Backend Frameworks & Libraries

### Web Framework
- **FastAPI** (>=0.129.0): Modern async web framework for REST API
- **Uvicorn** (>=0.40.0): ASGI server for FastAPI

### Configuration & Validation
- **Pydantic Settings** (>=2.6.0): Environment-based configuration management
- **python-dotenv** (>=1.2.1): .env file loading

### LLM & AI
- **OpenAI SDK** (>=1.0.0): Client for Alibaba Qwen models (via OpenAI-compatible API)
- **NLTK** (>=3.9.2): Natural language text processing

### Document Processing
- **pypdf** (>=4.0,<6.0): PDF text extraction
- **pdfplumber** (>=0.11.4): Advanced PDF parsing
- **PyMuPDF** (>=1.24.0): PDF processing library
- **readability-lxml** (>=0.8.0): Web content extraction
- **beautifulsoup4** (>=4.13.0): HTML parsing
- **trafilatura** (>=1.12.2): Web scraping and text extraction
- **markdownify** (>=0.14.0): HTML to Markdown conversion

### HTTP Client
- **httpx** (>=0.28.1): Async HTTP client

### Evaluation & Testing (Optional)
- **DeepEval** (>=2.0.0): LLM evaluation framework
- **LiteLLM** (>=1.0.0): Multi-LLM API integration
- **camelot-py** (>=0.12.0): PDF table extraction
- **chonkie[semantic]** (>=1.0.0): Semantic chunking

### Experiment Tracking
- **wandb** (>=0.23.0): Weights & Biases for experiment logging

### Development Tools
- **pytest** (>=8.0.0): Testing framework
- **pytest-asyncio** (>=0.23.0): Async test support
- **ruff** (>=0.8.0): Linter and formatter
- **mypy** (>=1.19.1): Static type checker

## Frontend Frameworks & Libraries

### Core Framework
- **Svelte** (^5.49.2): Reactive UI framework
- **SvelteKit** (^2.50.2): Full-stack web application framework
- **Vite** (^7.3.1): Build tool and dev server
- **@sveltejs/adapter-node** (^5.5.4): Node.js adapter for production

### UI Components
- **Chart.js** (^4.5.1): Data visualization charts
- **svelte-markdown** (0.4.1): Markdown rendering
- **highlight.js** (11.9.0): Syntax highlighting

### Testing
- **Playwright** (^1.58.2): End-to-end browser testing

### Build Tooling
- **Bun** 1.2.5: Fast JavaScript runtime and package manager (build)
- **Node.js** 20: Production runtime

## Data Storage

### Vector Storage
- **Custom file-based JSON storage** for embeddings and metadata
- Location: `data/vectors/`
- Custom hybrid search: semantic (cosine similarity) + BM25 (keyword) + source prior boosting

### File Storage
- `data/raw/`: Raw downloaded documents (HTML/PDF)
- `data/processed/`: Processed document chunks
- `data/evals/`: Evaluation results and cache

### Search Architecture
- **In-memory BM25 keyword index**: Custom implementation
- **Cosine similarity**: Manual implementation for vector search
- **Reciprocal Rank Fusion (RRF)**: Hybrid search combining semantic + keyword

## Containerization & Deployment

### Docker
- **Backend**: Python 3.13-slim base image
- **Frontend**: Multi-stage build (Bun for build, Node.js 20-alpine for runtime)
- **Orchestration**: Docker Compose for multi-container setup

### Services
- **backend**: FastAPI on port 8000
- **frontend**: SvelteKit/Node.js on port 5173
- **test**: Playwright E2E test runner (profile-based)

## Development Tools

### Python Environment
- **uv**: Python package manager and virtual environment tool
- Commands: `uv sync`, `uv run`, `uv add`

### Frontend Development
- **bun**: Fast package manager and build tool
- Commands: `bun run dev`, `bun run build`, `bun install`

### Code Quality
- **Ruff**: Python linting and formatting (line length: 100, target: Python 3.13)
- **mypy**: Static type checking with relaxed import checking
- **TypeScript**: Frontend type safety

### Testing
- **pytest**: Backend unit and integration tests
- **Playwright**: Frontend E2E tests
- Test markers: `live_api`, `deepeval`, `e2e_real_apis`, `slow`

## Configuration Files

### Backend
- `pyproject.toml`: Python dependencies, project metadata, tool configuration
- `uv.lock`: Locked Python dependency versions
- `Dockerfile`: Multi-stage build for backend
- `.env`: Environment variables (not in git)
- `.env.example`: Template for environment variables

### Frontend
- `package.json`: Node.js dependencies and scripts
- `bun.lock`: Locked frontend dependency versions
- `frontend/Dockerfile`: Multi-stage build for frontend
- `frontend/vite.config.js`: Vite configuration
- `frontend/tsconfig.json`: TypeScript configuration
- `svelte.config.js`: Svelte/SvelteKit configuration

### Infrastructure
- `docker-compose.yml`: Multi-container orchestration
- `frontend/Dockerfile.test`: Playwright test container

## API Endpoints

### Backend (FastAPI)
- Port: 8000
- Health check: `/health`
- Chat: `/api/v1/chat`
- Ingestion: `/api/v1/ingest`
- Evaluation: `/api/v1/eval/*`

### Frontend (SvelteKit)
- Port: 5173
- Base URL: Configurable via `VITE_API_URL`

## Key Architectural Patterns

### Backend
- **Async/await**: Non-blocking I/O for LLM API calls
- **Dependency injection**: Factory functions for vector store and LLM clients
- **Middleware**: Rate limiting, CORS, authentication
- **Separation of concerns**: Routes, use cases, infrastructure layers

### Frontend
- **Component-based**: Svelte components for UI
- **Type-safe**: TypeScript throughout
- **API client**: Centralized HTTP client with error handling
- **Reactive state**: Svelte stores and component state

## Performance & Scaling

### Rate Limiting
- Configurable per-minute limits per client IP
- Separate limits for authenticated vs anonymous users
- Cookie-based session tracking for anonymous users

### Caching
- File-based embedding cache for evaluation
- In-process W&B run cache (TTL: 60s)
- Content-based deduplication for document ingestion

### Resource Limits (Docker)
- Backend: 1 CPU, 1GB RAM (512MB reservation)
- Frontend: 0.5 CPU, 256MB RAM (128MB reservation)
- Test: 2 CPU, 2GB RAM (1GB reservation)
