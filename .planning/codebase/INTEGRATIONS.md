# External Integrations

## LLM APIs

### Alibaba Dashscope (Primary)
- **Purpose**: Main LLM provider for chat and embeddings
- **Models**:
  - qwen3.5-flash - Fast responses
  - qwen3.5-plus - Balanced performance
  - qwen3.5-max - Highest quality
  - text-embedding-v4 - Embeddings
- **Configuration**: Environment variable `DASHSCOPE_API_KEY`
- **Error Handling**: Retry logic with exponential backoff

### Google Gemini (Backup)
- **Purpose**: Alternative LLM provider
- **Configuration**: Available but not primary
- **Usage**: Fallback option for redundancy

## Experiment Tracking

### Weights & Biases (wandb)
- **Purpose**: Track evaluation experiments and metrics
- **Features**:
  - Pipeline assessment logging
  - Metric tracking (hit rate, NDCG, precision, recall)
  - Artifact management
- **Configuration**: Optional, enabled via environment

## Data Storage

### File-Based Persistence
- **Documents**: Local file system storage
- **Vectors**: Custom SQLite-based vector store
- **Chat History**: File-based persistence
- **Location**: `data/` directory

## Internal Services

### Vector Store
- **Implementation**: Custom (not ChromaDB)
- **Capabilities**:
  - Semantic search
  - Keyword search
  - Hybrid search
  - MMR reranking for diversity

## Web Scraping (Offline)

### Document Sources
- **PDF Processing**: pypdf, pdfplumber
- **HTML Parsing**: beautifulsoup4
- **Content Extraction**: trafilatura
- **Usage**: Ingestion pipeline for knowledge base

## API Configuration

### Authentication
- API keys managed via environment variables
- No hardcoded secrets in codebase
- Comma-separated string format for multiple keys

### Rate Limiting
- **Current**: No rate limiting implemented
- **Note**: Potential concern for production use
