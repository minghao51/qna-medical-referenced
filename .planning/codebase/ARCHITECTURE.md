# Architecture

## Design Pattern
**Clean Architecture with Hexagonal Design Principles**

The application follows a layered architecture with clear separation of concerns:
- **Domain Layer**: Core business logic and entities
- **Application Layer**: Use cases and orchestration
- **Infrastructure Layer**: External services and integrations
- **Interface Layer**: API routes and CLI commands

## Entry Points

### Backend
- **API Server**: `src/app/factory.py` - FastAPI application factory
- **CLI Commands**:
  - `src/cli/serve.py` - Start development server
  - `src/cli/ingest.py` - Document ingestion pipeline
  - `src/cli/eval_pipeline.py` - Evaluation pipeline

### Frontend
- **Chat Interface**: `frontend/src/routes/+page.svelte`
- **Evaluation Dashboard**: `frontend/src/routes/eval/+page.svelte`

## Key Patterns

### Factory Pattern
- Application factory in `src/app/factory.py`
- LLM client factory for provider abstraction

### Dependency Injection
- Throughout the application for testability
- Pydantic settings for configuration injection

### Repository Pattern
- Data access abstraction in `src/infra/`
- Chat history store interface

### Pipeline Pattern
- Document ingestion: `src/ingestion/`
- RAG processing: `src/rag/runtime.py`

### Strategy Pattern
- Chunking strategies: `src/ingestion/chunkers.py`
- Search modes: diversification strategies

## Data Flow

```
User Request
    ↓
Routes (src/app/routes/)
    ↓
Use Cases (src/usecases/)
    ↓
Domain (src/rag/, src/evals/)
    ↓
Infrastructure (src/infra/)
    ↓
External Services (LLM, Storage)
```

## Critical Abstractions

### RAG Runtime
- **File**: `src/rag/runtime.py`
- **Purpose**: Retrieval with diversification
- **Key Methods**: Search, chunk, rank, synthesize

### LLM Client
- **File**: `src/infra/llm/qwen_client.py`
- **Purpose**: Qwen API interface
- **Abstraction**: Provider-agnostic LLM interface

### Chat History
- **File**: `src/infra/storage/file_chat_history_store.py`
- **Purpose**: Session persistence
- **Storage**: Filesystem-based

### Evaluation Orchestrator
- **File**: `src/evals/assessment/orchestrator.py`
- **Purpose**: Quality assessment pipeline
- **Integration**: DeepEval for LLM evaluation

## API Surface
- **Health**: `GET /health`
- **Chat**: `POST /api/chat` - Chat completions
- **History**: `GET/POST /api/history` - Chat session management
- **Evaluation**: `POST /api/evaluate` - Quality assessment

## Architecture Strengths
- Clear layer separation
- Comprehensive dependency injection
- Modular pipeline design
- Extensive monitoring and evaluation
