# External Integrations

## LLM Providers

### Primary
- **Alibaba Qwen (DashScope)** - Main inference provider
  - Accessed via OpenAI-compatible SDK
  - Configured via `QWEN_API_KEY` and `QWEN_BASE_URL`

### Secondary
- **Google Gemini** - Alternative/fallback LLM
  - Routed through LiteLLM proxy
  - Configured via `GEMINI_API_KEY`

## Vector Database

- **ChromaDB** - Local vector store
  - Persistent storage on filesystem
  - Embeddings stored in `.chroma` directory
  - No external hosting required

## Document Sources

- **Local file system** - PDF/HTML document storage
- **Web scraping** - HTTP-based content fetching via trafilatura/readability

## Experiment Tracking

- **Weights & Biases (wandb)**
  - Run tracking and logging
  - Configured via `WANDB_API_KEY`
  - Project: medical RAG evaluation

## Authentication

- **API Key-based** - Custom implementation
  - Simple shared secret validation
  - Configured via `SHARED_API_KEY`
  - Disabled by default in development

## External Services (None)

Notable: This system is intentionally self-contained with minimal external dependencies:
- No cloud database (uses ChromaDB on disk)
- no auth provider (custom API key)
- No message queue (async in-process)
- No external logging (stdout/file-based)

## File Storage

- **Local filesystem** - All document storage
- **Data directory**: `data/` for input documents
- **Processed content**: Embedded directly in vector store

## Web Scraping

- **trafilatura** - Main content extractor
- **readability-lxml** - Fallback HTML cleaner
- **BeautifulSoup4** - HTML parsing utilities
