# External Integrations

## LLM Providers

### Alibaba Dashscope (Primary)
- **Purpose**: Qwen model access for chat and embeddings
- **Models**: qwen3.5-flash (default), configurable
- **Authentication**: API key via `DASHSCOPE_API_KEY`
- **Usage**:
  - Chat completions in `/chat` endpoint
  - Query expansion in RAG pipeline
  - HyDE (Hypothetical Document Embeddings) generation
- **Client**: Custom `QwenClient` in `src/infra/llm/qwen_client.py`
- **Error Handling**: Retry logic and timeout configuration

### OpenAI SDK (Compatibility Layer)
- **Purpose**: Standardized LLM interface
- **Usage**: Wraps Dashscope API for OpenAI-compatible calls
- **Benefits**: Simplifies switching between LLM providers

## Evaluation & Experimentation

### Weights & Biases (WandB)
- **Purpose**: Experiment tracking and metrics logging
- **Usage**:
  - RAG evaluation metrics
  - Pipeline performance tracking
  - Benchmark results visualization
- **Key Files**:
  - `src/experiments/wandb_tracking.py` - Tracking utilities
  - `src/experiments/wandb_history.py` - Run history management
- **Configuration**: Project and run settings in experiment configs

### DeepEval
- **Purpose**: RAG evaluation framework
- **Metrics**:
  - Answer relevance
  - Faithfulness
  - Context precision/recall
- **Usage**:
  - Automated evaluation pipelines
  - Synthetic test case generation
  - Comparative analysis
- **Key Files**:
  - `src/evals/assessment/answer_eval.py` - Answer evaluation
  - `src/evals/deepeval_models.py` - DeepEval integrations
  - `tests/test_*.py` - Evaluation test suites

## Data Sources

### Medical Reference Documents
- **Types**: PDFs, HTML web pages
- **Processing Pipeline**:
  1. Download (PDF/web content)
  2. Convert to Markdown
  3. Chunk text (structured/semantic)
  4. Generate embeddings
  5. Store in vector database
- **Key Steps**:
  - `src/ingestion/steps/download_pdfs.py` - PDF acquisition
  - `src/ingestion/steps/download_web.py` - Web scraping
  - `src/ingestion/steps/convert_html.py` - HTML→Markdown conversion
  - `src/ingestion/steps/chunk_text.py` - Text chunking

### Vector Storage
- **Implementation**: Custom vector store in `src/ingestion/indexing/vector_store.py`
- **Embeddings**: Generated via Qwen models
- **Retrieval**: Hybrid search (dense + sparse)
- **Configuration**: Runtime settings in `src/rag/runtime.py`

## Authentication & Security

### API Key Authentication
- **Implementation**: Custom middleware in `src/app/middleware/auth.py`
- **Storage**: Hashed keys using SHA256
- **Configuration**:
  - `API_KEYS` environment variable (JSON array)
  - `api_keys_json` setting for complex configurations
- **Features**:
  - Key validation
  - Role-based access (owner, role fields)
  - Status management (active, disabled, revoked)

### Rate Limiting
- **Implementation**: Custom middleware in `src/app/middleware/rate_limit.py`
- **Storage**: SQLite database (`rate_limits.db`)
- **Configuration**:
  - `RATE_LIMIT_PER_MINUTE` - Authenticated requests
  - `anonymous_chat_rate_limit_per_minute` - Anonymous requests
- **Headers**: `X-API-Key`, `X-Anonymous-Browser-ID`

## CORS Configuration

### Allowed Origins
- **Development**: http://localhost:5173, http://localhost:5174, http://localhost:3000
- **Localhost**: http://127.0.0.1:5173, http://127.0.0.1:5174, http://127.0.0.1:3000
- **Configuration**: `CORS_ALLOWED_ORIGINS` environment variable

### Middleware Order
1. CORS (must be first)
2. RateLimit
3. APIKey
4. RequestID

## Storage & Persistence

### Chat History
- **Implementation**: `FileChatHistoryStore` in `src/infra/storage/file_chat_history_store.py`
- **Storage**: JSON file-based storage
- **Session Management**: Cookies (`chat_session_id`, `anonymous_browser_id`)

### Configuration
- **Loader**: Pydantic Settings with `.env` file support
- **Validation**: Type-safe configuration on import
- **Hot Reload**: Supported for API keys via `APIKeyConfig.reload()`

## HTTP Clients

### Async HTTP Operations
- **Library**: httpx 0.28+
- **Usage**:
  - Web scraping in ingestion pipeline
  - External API calls (Dashscope)
  - Health checks
- **Features**: Async/await support, timeout handling

## Web Scraping

### Trafilatura Integration
- **Purpose**: Main web content extraction
- **Features**:
  - Article content extraction
  - Boilerplate removal
  - Metadata extraction
- **Fallback**: BeautifulSoup4 for complex HTML parsing

### Markdown Conversion
- **Library**: markdownify
- **Purpose**: Convert HTML to Markdown for RAG indexing
- **Configuration**: Extraction mode settings

## Monitoring & Observability

### Structured Logging
- **Framework**: Python standard `logging` module
- **Format**: JSON-structured logs via `src/app/logging.py`
- **Configuration**: `LOG_LEVEL` environment variable

### Request Tracing
- **Request ID**: Automatic generation via middleware
- **Headers**: `X-Request-ID` added to responses
- **Purpose**: Distributed tracing and debugging
