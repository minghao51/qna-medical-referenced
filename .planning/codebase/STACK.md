# Tech Stack

## Languages & Runtime

### Backend
- **Python 3.13+** - Core runtime requirement
- **TypeScript** - Type checking support via mypy

### Frontend
- **JavaScript/TypeScript** - SvelteKit application
- **Svelte 5** - UI framework
- **Node.js** - Frontend build runtime

## Backend Frameworks & Libraries

### Web Framework
- **FastAPI 0.129+** - Async web framework for API endpoints
- **Uvicorn 0.40+** - ASGI server
- **Pydantic Settings 2.6+** - Configuration management

### Data Processing
- **pypdf 6.7+** - PDF text extraction
- **pdfplumber 0.11+** - Advanced PDF parsing
- **BeautifulSoup4 4.13+** - HTML parsing
- **trafilatura 1.12+** - Web content extraction
- **markdownify 0.14+** - HTML to Markdown conversion
- **nltk 3.9+** - Natural language processing

### LLM & AI
- **OpenAI 1.0+** - LLM API client (used for Qwen/Dashscope)
- **litellm 1.0+** - Multi-model LLM interface

### Evaluation & Experimentation
- **DeepEval 2.0+** - RAG evaluation framework
- **WandB 0.23+** - Experiment tracking and logging

### HTTP & Networking
- **httpx 0.28+** - Async HTTP client
- **python-dotenv 1.2+** - Environment variable loading

## Frontend Frameworks & Libraries

### Core Framework
- **SvelteKit 2.50+** - Full-stack web framework
- **Vite 7.3+** - Build tool and dev server
- **Svelte 5.49+** - Reactive UI library

### UI & Visualization
- **Chart.js 4.5+** - Data visualization
- **highlight.js 11.9+** - Syntax highlighting
- **svelte-markdown 0.4+** - Markdown rendering

### Testing
- **Playwright 1.58+** - E2E browser testing
- **@sveltejs/adapter-node 5.5+** - Node.js server adapter

## Development Tools

### Python Tooling
- **uv** - Python package manager (project requirement)
- **ruff 0.15+** - Fast Python linter and formatter
- **mypy 1.19+** - Static type checker
- **pytest 9.0+** - Testing framework

### Code Quality Configuration
- **Line length**: 100 characters
- **Target Python version**: 3.13
- **Ruff rules**: E, F, I, N, W (ignore E501)

## Build & Deployment

### Containerization
- **Docker** - Multi-stage builds for backend/frontend
- **docker-compose** - Local development orchestration

### Backend Build
- **Base image**: python:3.13-slim
- **Runtime target**: Optimized production image
- **Development**: Hot-reload via volume mounts

### Frontend Build
- **Adapter**: SvelteKit Node.js adapter
- **Build output**: Optimized static assets
- **Dev server**: Vite HMR (port 5173)

## Package Management

### Backend
- **pyproject.toml** - Python project configuration
- **uv sync** - Dependency installation
- **Optional dependency groups**: dev, evaluation

### Frontend
- **package.json** - Node dependencies
- **bun** - Preferred package manager (lockfile present)
- **npm** - Alternative package manager

## Environment & Configuration

### Required Environment Variables
- `DASHSCOPE_API_KEY` - Alibaba Dashscope API key for Qwen models
- `MODEL_NAME` - LLM model identifier (default: qwen3.5-flash)

### Optional Configuration
- `RATE_LIMIT_PER_MINUTE` - Rate limiting (0 = disabled)
- `CORS_ALLOWED_ORIGINS` - Comma-separated allowed origins
- `LOG_LEVEL` - Application logging level
- `API_KEYS` - Authentication configuration
