# External Integrations

## LLM Provider

### Google Gemini

| Aspect | Details |
|--------|---------|
| API | Google Generative AI (google-genai) |
| Primary Model | gemini-2.0-flash (configurable via settings) |
| Embedding Model | gemini-embedding-001 |
| API Key | GEMINI_API_KEY (from .env) |

**Integration Points:**
- `src/llm/client.py` - LLM client for generating responses
- `src/vectorstore/store.py` - Document embeddings generation

## Data Sources

### Lab Reference Ranges
- **Source**: LabQAR Dataset (PhysioNet)
- **File**: `data/raw/LabQAR/reference_ranges.csv`
- **Format**: CSV with test_name, normal_range, unit, category, notes

### Medical PDFs
- **Source**: Local PDF files in `data/raw/*.pdf`
- **Processing**: pypdf for text extraction
- **Current**: Lipid management PDF, pre-diabetes PDF

## Environment Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| GEMINI_API_KEY | - | Google AI API key (required) |
| model_name | gemini-2.0-flash | LLM model |
| embedding_model | gemini-embedding-001 | Embedding model |
| collection_name | medical_docs | Vector store name |
| data_dir | data/raw | PDF directory |
| vector_dir | data/vectors | Embeddings directory |
| rate_limit_per_minute | 60 | Rate limit |

## Local Storage

### Vector Embeddings
- **Storage**: JSON file at `data/vectors/medical_docs.json`
- **Format**: ids, contents, embeddings, metadatas, content_hashes
- **Index**: Keyword-based TF-IDF index for hybrid search

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root endpoint |
| `/health` | GET | Health check |
| `/chat` | POST | Chat with RAG context |

## Middleware

| Middleware | Purpose |
|------------|---------|
| APIKeyMiddleware | Validates X-API-Key header |
| RateLimitMiddleware | 60 requests per minute per IP |
| RequestIDMiddleware | Adds request ID to logs |

## No Current Integrations

- No authentication providers
- No external databases (local JSON)
- No cloud services beyond Google Gemini
