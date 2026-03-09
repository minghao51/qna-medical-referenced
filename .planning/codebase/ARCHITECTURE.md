# Architecture

## Design Principles

### Layered Architecture
Clear separation of concerns across layers:
1. **HTTP Layer** (`src/app/`) - FastAPI routes and endpoints
2. **Business Logic** (`src/usecases/`) - Use case orchestration
3. **Domain** (`src/models.py`) - Core domain models
4. **Infrastructure** (`src/infra/`) - External integrations

### Hexagonal Architecture
- Core domain logic surrounded by adapters
- Infrastructure isolated from business rules
- Testable components with clear boundaries

### Pipeline Pattern
Separate flows for runtime and offline processing:
- **Runtime**: Chat requests → RAG pipeline → LLM → Response
- **Offline**: Download → Process → Chunk → Embed → Index → Store

## Core Components

### RAG Pipeline
- **Location**: `src/rag/`
- **Components**:
  - Runtime retrieval and context generation
  - Hybrid search (semantic + keyword)
  - MMR reranking for result diversity
  - Configurable retrieval parameters

### Ingestion Pipeline
- **Location**: `src/ingestion/`
- **Components**:
  - Steps: download, convert, chunk, embed, index
  - Indexing: vector store management
  - Persistence: document and embedding storage

### Evaluation System
- **Location**: `src/evals/`
- **Components**:
  - Pipeline assessment framework
  - Metric calculation (hit rate, NDCG, precision, recall)
  - Artifact management
  - Step-by-step validation

## Data Flow

### Runtime Request Flow
```
HTTP Request
    ↓
FastAPI Route (src/app/routes/)
    ↓
Use Case (src/usecases/)
    ↓
RAG Runtime (src/rag/runtime.py)
    ↓
Vector Store (src/ingestion/indexing/vector_store.py)
    ↓
LLM Client (src/infra/llm/)
    ↓
Response Formatting (src/rag/formatting.py)
    ↓
HTTP Response
```

### Offline Ingestion Flow
```
Source URLs/Files
    ↓
Download (src/ingestion/steps/download_web.py)
    ↓
Convert (src/ingestion/steps/convert_html.py, load_pdfs.py, load_markdown.py)
    ↓
Chunk (src/ingestion/steps/chunk_text.py)
    ↓
Embed (src/ingestion/indexing/embedding.py)
    ↓
Index (src/ingestion/indexing/vector_store.py)
    ↓
Persist (src/ingestion/indexing/persistence.py)
```

## Key Abstractions

### Document Model
- Content, metadata, and embeddings
- Source tracking and provenance
- Chunked representation for retrieval

### Retrieval Configuration
- Top-k result control
- Diversity parameters
- Hybrid search weights
- MMR reranking settings

### Pipeline Trace
- Observability for debugging
- Step-by-step execution tracking
- Performance metrics

## Entry Points

### Backend Services
- **HTTP Server**: `src/cli/serve.py` - FastAPI on port 8000
- **Ingestion CLI**: `src/cli/ingest.py` - Data pipeline runner
- **Evaluation CLI**: `src/cli/eval_pipeline.py` - Quality assessment

### Frontend
- **Main Interface**: `frontend/src/routes/+page.svelte` - Port 5173
- **Build**: SvelteKit with Vite

## Configuration Management

### Centralized Settings
- **Location**: `src/config/settings.py`
- **Framework**: Pydantic BaseSettings
- **Features**:
  - Environment variable loading
  - Type-safe configuration
  - Default values for development

### Path Management
- **Location**: `src/config/paths.py`
- **Purpose**: Centralized path resolution
- **Components**:
  - Data directories
  - Model paths
  - Cache locations

## Factory Pattern

### Application Factory
- **Location**: `src/app/factory.py`
- **Purpose**: Create and configure FastAPI app
- **Responsibilities**:
  - Route registration
  - Middleware setup
  - CORS configuration
  - Dependency injection

## Deployment Architecture

### Containerization
- Docker Compose multi-service setup
- Separate containers for backend and frontend
- Shared volume for data persistence

### Scalability Considerations
- Stateless HTTP layer
- File-based storage (single-instance limitation)
- No connection pooling (potential bottleneck)
