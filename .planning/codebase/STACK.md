# Tech Stack

## Languages & Runtimes
- **Backend**: Python 3.13 with UV package manager
- **Frontend**: TypeScript with Svelte 5 framework
- **Runtime**: FastAPI (backend) + Vite (frontend)

## Core Frameworks
- **Backend**: FastAPI, Pydantic, Uvicorn ASGI server
- **Frontend**: SvelteKit 2.50.2, Vite build tool, TypeScript strict mode
- **Testing**: Playwright (E2E), Pytest (unit), DeepEval (LLM evaluation)

## Key Dependencies

### Backend (pyproject.toml)
- **LLM Integration**: OpenAI client, Qwen/Dashscope (Alibaba), LiteLLM
- **Document Processing**: PyPDF, PDFPlumber, BeautifulSoup4, Trafilatura
- **Web Framework**: FastAPI, Starlette
- **Data/Storage**: Pydantic settings
- **Development**: Ruff (linter/formatter), pytest

### Frontend (frontend/package.json)
- **UI Framework**: SvelteKit 2.50.2
- **Build Tool**: Vite
- **Language**: TypeScript (strict mode)
- **Visualization**: Chart.js, Highlight.js
- **Testing**: Playwright for E2E testing

## Configuration Files
- `/Users/minghao/Desktop/personal/qna_medical_referenced/pyproject.toml` - Python dependencies and tool config
- `/Users/minghao/Desktop/personal/qna_medical_referenced/frontend/package.json` - Frontend dependencies
- `/Users/minghao/Desktop/personal/qna_medical_referenced/frontend/tsconfig.json` - TypeScript config
- `/Users/minghao/Desktop/personal/qna_medical_referenced/docker-compose.yml` - Container orchestration
- `/Users/minghao/Desktop/personal/qna_medical_referenced/.env.example` - Environment template

## Architecture Pattern
- **RAG System**: Retrieval-Augmented Generation for medical Q&A
- **REST API**: Separate frontend/backend architecture
- **Containerization**: Docker with multi-stage builds
- **Async Processing**: Event-driven async operations
