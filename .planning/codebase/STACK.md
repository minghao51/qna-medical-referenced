# STACK.md - Languages, Runtime, Frameworks, Dependencies

## Backend

### Language & Runtime
- **Python**: 3.13+
- **Runtime**: Uvicorn (ASGI server)

### Core Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.129.0 | Web framework |
| google-genai | >=1.63.0 | Gemini LLM client |
| pypdf | >=6.7.0 | PDF parsing |
| nltk | >=3.9.2 | Text processing (stemming, stopwords) |
| httpx | >=0.28.1 | Async HTTP client |
| beautifulsoup4 | >=4.13.0 | HTML parsing |
| markdownify | >=0.14.0 | HTML to Markdown |
| pydantic-settings | >=2.6.0 | Configuration management |
| uvicorn | >=0.40.0 | ASGI server |

### Dev Dependencies
- **pytest**: >=8.0.0 - Testing framework
- **ruff**: >=0.8.0 - Linting
- **playwright**: >=1.58.0 - E2E testing

## Frontend

### Language & Framework
- **TypeScript**: ^5.9.3
- **Svelte**: ^5.49.2 (SvelteKit)
- **Vite**: ^7.3.1 (Build tool)

### Frontend Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| @sveltejs/kit | ^2.50.2 | Svelte meta-framework |
| svelte | ^5.49.2 | UI framework |
| @playwright/test | ^1.58.2 | E2E testing |
| typescript | ^5.9.3 | Type safety |

## Infrastructure

### Container Orchestration
- **Docker Compose**: Multi-service deployment (backend, frontend, test)

### External Services
- **Google Gemini API**: LLM generation and embeddings
  - Model: `gemini-2.0-flash` (generation)
  - Embedding: `gemini-embedding-001`

### Data Storage
- **Vector Store**: JSON file-based (`data/vectors/`)
- **Chat History**: JSON file (`data/chat_history.json`)
- **Rate Limiting**: SQLite (`data/rate_limits.db`)

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| GEMINI_API_KEY | Google Gemini API key | Yes |
| API_KEYS | Comma-separated API keys for auth | No |
| MODEL_NAME | LLM model name | No (default: gemini-2.0-flash) |
| EMBEDDING_MODEL | Embedding model | No (default: gemini-embedding-001) |
