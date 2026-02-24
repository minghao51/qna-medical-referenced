# INTEGRATIONS.md - External APIs, Databases, Auth

## External APIs

### Google Gemini API
- **Purpose**: LLM text generation and embeddings
- **Configuration**: `src/config/settings.py`
- **Models Used**:
  - Generation: `gemini-2.0-flash`
  - Embeddings: `gemini-embedding-001`
- **Implementation**: `src/llm/client.py`

### Web Content Sources (Download)
The system downloads medical content from Singapore government health websites:
- **ACE Clinical Guidelines** (ace-hta.gov.sg): 11 clinical guidelines
- **HealthHub** (healthhub.sg): 5 public health pages
- **HPP Guidelines** (hpp.moh.gov.sg): 1 guidelines index
- **MOH Singapore** (moh.gov.sg): 1 main portal
- **Implementation**: `src/pipeline/L0_download.py`

## Databases & Storage

### Vector Store (JSON-based)
- **Location**: `data/vectors/{collection_name}.json`
- **Purpose**: Semantic search with hybrid (semantic + keyword) retrieval
- **Implementation**: `src/pipeline/L5_vector_store.py`
- **Features**:
  - TF-IDF keyword indexing
  - Cosine similarity for semantic search
  - Source boosting (PDF: 1.0, CSV: 0.5)

### Chat History (JSON File)
- **Location**: `data/chat_history.json`
- **Purpose**: Session-based conversation history
- **Implementation**: `src/storage/chat_store.py`

### Rate Limiting (SQLite)
- **Location**: `data/rate_limits.db`
- **Purpose**: Per-API-key/IP rate limiting
- **Implementation**: `src/middleware/rate_limit.py`
- **Default**: 60 requests/minute

### Reference Data (CSV)
- **Location**: `data/raw/LabQAR/reference_ranges.csv`
- **Purpose**: Lab test reference ranges
- **Columns**: test_name, normal_range, unit, category, notes
- **Implementation**: `src/pipeline/L4_reference_loader.py`

## Authentication

### API Key Middleware
- **Implementation**: `src/middleware/auth.py`
- **Header**: `X-API-Key`
- **Config**: `API_KEYS` environment variable (comma-separated)
- **Paths bypassed**: `/`, `/health`, `/docs`, `/openapi.json`

### Rate Limiting
- **Implementation**: `src/middleware/rate_limit.py`
- **Default**: 60 requests/minute per key/IP
- **Storage**: SQLite with in-memory caching

## Data Flow

```
User Question → API (auth + rate limit) → 
  → RAG Pipeline (retrieve context) → 
  → Gemini LLM (generate response) → 
  → Store in chat history → 
  → Return response + sources
```
