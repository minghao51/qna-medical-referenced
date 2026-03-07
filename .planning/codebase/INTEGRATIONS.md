# INTEGRATIONS.md - External APIs, Databases, Auth

## External APIs

### Alibaba Dashscope API (Qwen)
- **Purpose**: LLM text generation and embeddings
- **Configuration**: `src/config/settings.py`
- **Models Used**:
  - Generation: `qwen3.5-flash`
  - Embeddings: `text-embedding-v4`
- **Implementation**: `src/infra/llm/qwen_client.py`

### Web Content Sources (Download)
The system downloads medical content from Singapore government health websites:
- **ACE Clinical Guidelines** (ace-hta.gov.sg): 11 clinical guidelines
- **HealthHub** (healthhub.sg): 5 public health pages
- **HPP Guidelines** (hpp.moh.gov.sg): 1 guidelines index
- **MOH Singapore** (moh.gov.sg): 1 main portal
- **Implementation**: `src/ingestion/steps/download_web.py`

## Databases & Storage

### Vector Store (JSON-based)
- **Location**: `data/vectors/{collection_name}.json`
- **Purpose**: Semantic search with hybrid (semantic + keyword) retrieval
- **Implementation**: `src/ingestion/indexing/vector_store.py`
- **Features**:
  - TF-IDF keyword indexing
  - Cosine similarity for semantic search
  - Source boosting (PDF: 1.0, CSV: 0.5)

### Chat History (JSON File)
- **Location**: `data/chat_history.json`
- **Purpose**: Session-based conversation history
- **Implementation**: `src/infra/storage/chat_history_store.py`

### Rate Limiting (SQLite)
- **Location**: `data/rate_limits.db`
- **Purpose**: Per-API-key/IP rate limiting
- **Implementation**: `src/app/middleware/rate_limit.py`
- **Default**: 60 requests/minute

### Reference Data (CSV)
- **Location**: `data/raw/LabQAR/reference_ranges.csv`
- **Purpose**: Lab test reference ranges
- **Columns**: test_name, normal_range, unit, category, notes
- **Implementation**: `src/ingestion/steps/load_reference_data.py`

## Authentication

### API Key Middleware
- **Implementation**: `src/app/middleware/auth.py`
- **Header**: `X-API-Key`
- **Config**: `API_KEYS` environment variable (comma-separated)
- **Paths bypassed**: `/`, `/health`, `/docs`, `/openapi.json`

### Rate Limiting
- **Implementation**: `src/app/middleware/rate_limit.py`
- **Default**: 60 requests/minute per key/IP
- **Storage**: SQLite with in-memory caching

## Data Flow

```
User Question → API (auth + rate limit) →
  → RAG Runtime (retrieve context) →
  → Qwen LLM (generate response) →
  → Store in chat history →
  → Return response + sources
```
