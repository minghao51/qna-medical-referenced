# External Integrations

## LLM Providers
- **Alibaba Dashscope API** - Primary LLM provider (Qwen models)
  - Client: `src/infra/llm/qwen_client.py`
  - Models: Qwen series for chat and completion

## Experiment Tracking
- **Weights & Biases (W&B)** - Experiment monitoring and logging
  - Integration: `src/experiments/wandb_tracking.py`
  - Configuration: `src/experiments/config.py`
  - Used for: RAG pipeline evaluation, metrics tracking

## Web Services & APIs
- **HTTPX** - Async HTTP client for API calls
  - Used for external service communication

## Document Processing
- **PyPDF** - PDF text extraction
- **PDFPlumber** - Advanced PDF parsing
- **BeautifulSoup4** - HTML parsing
- **Trafilatura** - Web content extraction

## Data Storage
- **File-based Chat History** - `src/infra/storage/file_chat_history_store.py`
  - Session persistence in local filesystem
- **Vector Store** - ChromaDB (implied from RAG architecture)

## Development Tools
- **Docker Compose** - Multi-container orchestration
- **UV** - Python package management and virtualization

## Monitoring & Logging
- **Structured JSON Logging** - Request ID tracking
- **W&B Integration** - Experiment metrics and artifacts

## Authentication
- Environment-based configuration (`.env` files)
- No external auth provider currently implemented
