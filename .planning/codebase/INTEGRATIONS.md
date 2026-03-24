# External Integrations

## LLM Providers

### Alibaba Dashscope (Qwen Models)
- **SDK**: OpenAI SDK (via OpenAI-compatible endpoint)
- **Base URL**: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- **Region**: Singapore (international)
- **Models**:
  - **qwen3.5-flash**: Default for chat (fast, cost-effective)
  - **qwen3.5-plus**: Higher quality responses
  - **qwen-plus**: General purpose
  - **qwen-max**: Highest quality
  - **text-embedding-v4**: Embeddings (768-dimensional vectors)
  - **qwen3.5-35b-a3b**: Lightweight judge model (3B active params)

- **Purpose**:
  - Text generation for chat responses
  - Embeddings for semantic search
  - LLM-as-a-judge for evaluation metrics

- **Configuration**:
  - API Key: `DASHSCOPE_API_KEY` environment variable
  - Model selection: `MODEL_NAME` environment variable
  - Embedding model: `EMBEDDING_MODEL` environment variable

- **Retry Logic**:
  - Max retries: 3
  - Exponential backoff: 1s, 2s, 4s
  - Applies to both sync and async calls
  - Separate retry logic for streaming responses

- **Usage Locations**:
  - `src/infra/llm/qwen_client.py`: QwenClient class
  - `src/ingestion/indexing/embedding.py`: Embedding generation
  - `src/evals/assessment/answer_eval.py`: Answer quality evaluation
  - `src/evals/metrics/medical.py`: Medical-specific metrics

## Evaluation & Experiment Tracking

### Weights & Biases (wandb)
- **SDK**: `wandb` Python package (>=0.23.0)
- **Purpose**: Experiment tracking, run history, metric logging
- **Features Used**:
  - Querying remote run history
  - Logging evaluation metrics
  - Experiment comparison

- **Configuration**:
  - API Key: `WANDB_API_KEY` environment variable
  - Cache TTL: 60 seconds (in-process)
  - Optional: Application works without W&B if key not provided

- **Usage Locations**:
  - `src/experiments/wandb_tracking.py`: Run logging
  - `src/experiments/wandb_history.py`: Historical run queries
  - `src/experiments/config.py`: Experiment configuration
  - `src/app/routes/evaluation.py`: Evaluation route integration

### DeepEval
- **SDK**: `deepeval` Python package (>=2.0.0)
- **Purpose**: LLM evaluation framework with pre-built metrics
- **Features Used**:
  - Faithfulness metric
  - Answer relevance metric
  - Custom medical-specific metrics
  - LLM-as-a-judge evaluation

- **Configuration**:
  - Query concurrency: 2 (configurable via `DEEPEVAL_QUERY_CONCURRENCY`)
  - Metric concurrency: 3 (configurable via `DEEPEVAL_METRIC_CONCURRENCY`)
  - Metric timeout: 90 seconds (configurable)
  - Answer cache enabled: true (reuses retrieval + generation)
  - Metric cache enabled: true (reuses metric outputs)
  - Cache directory: `data/evals/cache`
  - Cache schema version: 2

- **Usage Locations**:
  - `src/evals/assessment/answer_eval.py`: Answer evaluation orchestration
  - `src/evals/metrics/medical.py`: Custom medical metrics
  - `src/evals/deepeval_models.py`: DeepEval model wrappers
  - `tests/test_eval_deepeval.py`: Integration tests

### LiteLLM
- **SDK**: `litellm` Python package (>=1.0.0)
- **Purpose**: Multi-LLM API integration (evaluation optional dependency)
- **Features Used**:
  - Unified interface for multiple LLM providers
  - Model fallback and comparison

- **Usage Locations**:
  - `src/evals/deepeval_models.py`: Model integration for evaluation

## Data Sources & Ingestion

### Web Scraping & Content Extraction
- **trafilatura** (>=1.12.2):
  - Web content extraction from HTML
  - Text cleaning and normalization
  - Metadata extraction

- **readability-lxml** (>=0.8.0):
  - Article content extraction
  - Boilerplate removal

- **beautifulsoup4** (>=4.13.0):
  - HTML parsing
  - DOM traversal

- **markdownify** (>=0.14.0):
  - HTML to Markdown conversion
  - Preserves document structure

### PDF Processing
- **pypdf** (>=4.0,<6.0):
  - Basic PDF text extraction
  - Metadata reading

- **pdfplumber** (>=0.11.4):
  - Advanced PDF parsing
  - Table detection
  - Precise text positioning

- **PyMuPDF** (>=1.24.0):
  - Fast PDF rendering
  - Image extraction
  - Text extraction with layout info

- **camelot-py** (>=0.12.0, optional):
  - PDF table extraction
  - Table structure analysis

### Natural Language Processing
- **NLTK** (>=3.9.2):
  - Text tokenization
  - Sentence splitting
  - Stopword removal
  - Word tokenization for BM25

- **Chonkie** (optional):
  - Semantic chunking
  - Intelligent text segmentation

## Internal Services & Components

### Vector Storage (File-Based)
- **Implementation**: Custom JSON-based storage
- **Location**: `data/vectors/`
- **Schema**:
  ```json
  {
    "ids": ["chunk_id_1", "chunk_id_2"],
    "contents": ["text content 1", "text content 2"],
    "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
    "metadatas": [{...}, {...}],
    "content_hashes": ["hash1", "hash2"],
    "index_metadata": {...}
  }
  ```

- **Features**:
  - Content deduplication via SHA256 hashing
  - Metadata enrichment (source, domain, quality scores)
  - Hypothetical questions storage (HyPE)
  - Keyword index (BM25)

### Search Architecture
- **Semantic Search**:
  - Cosine similarity on Qwen embeddings
  - 768-dimensional vectors
  - Configurable model selection

- **Keyword Search (BM25)**:
  - Custom in-memory implementation
  - Term frequency tracking
  - Inverse document frequency

- **Hybrid Search**:
  - Reciprocal Rank Fusion (RRF)
  - Configurable weights: semantic (0.6), keyword (0.2), source boost (0.2)
  - Source prior boosting based on domain authority

### Evaluation Pipeline
- **Answer Generation**:
  - Qwen models via OpenAI SDK
  - Streaming and non-streaming modes
  - Context-aware generation with retrieved documents

- **Metrics**:
  - Faithfulness: Checks if answer is supported by context
  - Answer Relevance: Measures response relevance to question
  - Custom Medical Metrics: Domain-specific quality checks

- **Caching Strategy**:
  - Answer cache: Reuses retrieval + generation outputs
  - Metric cache: Reuses metric computations
  - File-based persistence in `data/evals/cache/`

## Authentication & Security

### API Key Authentication
- **Implementation**: Custom middleware
- **Configuration**:
  - `API_KEYS`: Comma-separated list of valid keys
  - `API_KEYS_JSON`: JSON array of key records with metadata

- **Features**:
  - Optional (can be disabled for development)
  - Per-key metadata (owner, role, status)
  - X-API-Key header validation

### Rate Limiting
- **Implementation**: In-memory rate limiter
- **Strategy**: Per-IP request counting
- **Configuration**:
  - General: `RATE_LIMIT_PER_MINUTE` (default: 60)
  - Anonymous chat: `ANONYMOUS_CHAT_RATE_LIMIT_PER_MINUTE` (default: 12)

- **Session Tracking**:
  - Browser fingerprinting via cookies
  - Server-issued session IDs
  - 30-day cookie lifetime
  - 30-day chat history TTL

### CORS Configuration
- **Allowed Origins**: Configurable via `CORS_ALLOWED_ORIGINS`
- **Default Origins**:
  - http://localhost:5173
  - http://localhost:5174
  - http://localhost:3000
  - http://127.0.0.1:5173
  - http://127.0.0.1:5174
  - http://127.0.0.1:3000

## Webhooks & External Callbacks

### Current Implementation
- **No external webhooks**: Application does not send webhooks to external services
- **No inbound webhooks**: No endpoints configured to receive webhooks

### Future Potential
- Evaluation results could be posted back to external systems
- Ingestion pipeline could trigger webhooks on completion
- W&B integration could be extended for real-time streaming

## Third-Party SDKs Summary

| Service | SDK/Package | Purpose | Required |
|---------|-------------|---------|----------|
| Alibaba Qwen | OpenAI SDK (>=1.0.0) | LLM & embeddings | Yes |
| Weights & Biases | wandb (>=0.23.0) | Experiment tracking | Optional |
| DeepEval | deepeval (>=2.0.0) | Evaluation framework | Optional |
| LiteLLM | litellm (>=1.0.0) | Multi-LLM interface | Optional |
| NLTK | nltk (>=3.9.2) | Text processing | Yes |
| Trafilatura | trafilatura (>=1.12.2) | Web scraping | Yes |
| PDF Processing | pypdf, pdfplumber, PyMuPDF | PDF extraction | Yes |

## API Rate Limits & Quotas

### Alibaba Dashscope
- **Rate Limits**: Configurable via retry logic (3 retries with exponential backoff)
- **No hard-coded limits**: Relies on API provider's default quotas
- **Retry Strategy**: 1s, 2s, 4s delays between attempts

### Weights & Biases
- **Cache TTL**: 60 seconds for in-process caching
- **No explicit rate limiting**: Relies on W&B SDK defaults

### Internal Rate Limiting
- **Per-IP limits**: Configurable via environment variables
- **In-memory storage**: Limits reset on container restart
- **Separate quotas**: Authenticated vs anonymous users

## Data Flow

### Chat Request Flow
1. User submits question via frontend
2. Frontend sends POST to `/api/v1/chat`
3. Backend validates API key (if enabled)
4. Rate limiter checks request count
5. Query is embedded using Qwen embedding model
6. Vector store performs hybrid search (semantic + keyword)
7. Retrieved context is passed to Qwen LLM
8. Response is streamed back to frontend
9. Frontend displays response with source citations

### Evaluation Flow
1. Evaluation dataset is loaded (JSON or generated)
2. For each query:
   a. Retrieve documents (cached if enabled)
   b. Generate answer (cached if enabled)
   c. Compute metrics (cached if enabled)
3. Metrics are aggregated
4. Results are logged to W&B (if configured)
5. Results are returned via API or saved to file

### Ingestion Flow
1. Documents are fetched from URLs or uploaded
2. Content is extracted (HTML/PDF parsing)
3. Text is cleaned and chunked
4. Chunks are embedded using Qwen embedding model
5. Embeddings and metadata are stored in JSON file
6. Keyword index is rebuilt
7. Statistics are logged
