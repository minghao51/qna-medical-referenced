# Tech Stack

## Backend (Python)

### Runtime & Framework
- **Python Version**: 3.13
- **Web Framework**: FastAPI
- **Package Manager**: uv

### LLM Providers
- **Primary**: Alibaba Dashscope (Qwen models)
  - qwen3.5-flash
  - qwen3.5-plus
  - qwen3.5-max
- **Backup/Alternative**: Google Gemini API

### Data & Storage
- **Vector Database**: Custom file-based vector store (SQLite-based)
- **Document Processing**:
  - pypdf - PDF parsing
  - pdfplumber - Advanced PDF extraction
  - beautifulsoup4 - HTML parsing
  - trafilatura - Web content extraction

### Testing & Quality
- **Testing Framework**: pytest
- **E2E Testing**: Playwright
- **Linting/Formatting**: ruff
  - Line length: 100 characters
  - Rules: E, F, I, N, W

### Monitoring & Observability
- **Experiment Tracking**: Weights & Biases (wandb)
- **Pipeline Tracing**: Custom trace models for debugging

## Frontend (TypeScript/JavaScript)

### Framework & Tooling
- **Framework**: SvelteKit 2.50.2
- **Build Tool**: Vite 7.3.1
- **Language**: TypeScript (strict mode enabled)
- **Adapter**: Node.js adapter

### Visualization & UI
- **Charting**: Chart.js 4.5.1
- **E2E Testing**: Playwright 1.58.2

## Containerization

### Orchestration
- **Docker Compose**: Multi-service architecture
  - Backend service (FastAPI)
  - Frontend service (SvelteKit)
  - Test service

### Deployment
- Production-ready containerization
- Environment-specific configurations
