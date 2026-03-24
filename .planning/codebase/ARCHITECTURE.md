# Architecture Documentation

## System Overview

This is a medical Q&A chatbot built with a RAG (Retrieval-Augmented Generation) pipeline, designed to help users understand health screening results. The system processes medical reference documents (PDFs, HTML), indexes them for retrieval, and uses LLMs to generate contextually relevant answers.

### Core Technology Stack

- **Backend**: Python 3.13+ with FastAPI
- **LLM**: Alibaba Qwen models via Dashscope API
- **Vector Storage**: Custom ChromaDB-based implementation with hybrid search
- **Frontend**: SvelteKit with TypeScript
- **Evaluation**: DeepEval framework with LLM-as-a-judge
- **Experiment Tracking**: Weights & Biases (W&B)

## Architecture Layers

### 1. Application Layer (`src/app/`)

**Purpose**: HTTP API, routing, middleware, and request handling

**Components**:
- `factory.py`: FastAPI app factory with middleware stack and lifecycle management
- `routes/`: API endpoints
  - `chat.py`: Chat endpoints (streaming and non-streaming)
  - `evaluation.py`: Evaluation and assessment endpoints
  - `history.py`: Chat history management
  - `health.py`: Health check endpoint
- `middleware/`: Request processing middleware
  - `auth.py`: API key authentication
  - `rate_limit.py`: Rate limiting per client
  - `request_id.py`: Request ID tracking for tracing
- `schemas/`: Pydantic models for request/response validation
- `session.py`: Session management for multi-turn conversations

**Middleware Order** (critical for correct operation):
1. CORS (must be first)
2. RateLimit
3. APIKey
4. RequestID (outermost for error tracking)

### 2. Use Case Layer (`src/usecases/`)

**Purpose**: Business logic orchestration - coordinates between infrastructure and RAG components

**Components**:
- `chat.py`: Chat message processing
  - `process_chat_message()`: Non-streaming chat with RAG
  - `stream_chat_message()`: Streaming chat with async generator
  - Manages conversation history and context building
- `pipeline.py`: Offline data pipeline orchestration
  - Coordinates L0-L6 pipeline steps
  - Supports selective re-execution (skip-download, force-rebuild)

**Flow**:
```
User Request → API Route → Use Case → RAG Retrieval → LLM Generation → Response
```

### 3. RAG Layer (`src/rag/`)

**Purpose**: Retrieval-augmented generation core logic

**Components**:
- `runtime.py`: Runtime retrieval system
  - `initialize_runtime_index()`: Lazy vector store initialization
  - `retrieve_context()`: Synchronous retrieval
  - `retrieve_context_with_trace()`: Detailed pipeline trace for debugging
  - `retrieve_context_with_trace_async()`: Async retrieval with HyDE support
  - `configure_runtime_for_experiment()`: Runtime configuration from experiments
  - Query expansion, MMR reranking, result diversification
- `hyde.py`: HyDE (Hypothetical Document Embeddings) query expansion
- `formatting.py`: Context and source formatting for LLM prompts
- `trace_models.py`: Pydantic models for pipeline traces

**Retrieval Pipeline**:
```
Query → Query Expansion (tokenization, acronyms, HyDE, HyPE)
  → Semantic Search (vector similarity)
  → Keyword Search (BM25)
  → Score Fusion (RRF hybrid)
  → MMR Reranking (diversity)
  → Source Diversification
  → Context Building
```

**Search Modes**:
- `rrf_hybrid`: Combined semantic + keyword with Reciprocal Rank Fusion
- `semantic_only`: Vector-only search
- `bm25_only`: Keyword-only search

### 4. Ingestion Layer (`src/ingestion/`)

**Purpose**: Document processing pipeline from raw sources to indexed chunks

**Sub-layers**:

#### Steps (`src/ingestion/steps/`)
**L0 - Data Acquisition**:
- `download_web.py`: Download web content from manifest
- `download_pdfs.py`: Download PDF files from URLs

**L1 - HTML Processing**:
- `convert_html.py`: HTML to Markdown conversion
  - Supports multiple extractors (trafilatura, beautifulsoup, readability-lxml)
  - Page classification (clinical vs non-clinical)

**L2 - PDF Processing**:
- `load_pdfs.py`: PDF text extraction
  - Multiple strategies: pypdf, pdfplumber, pymupdf
  - Table extraction (camelot, heuristic)

**L3 - Chunking**:
- `chunk_text.py`: Document chunking orchestration
- `chunking/`: Chunking strategies and configuration
  - `strategies.py`: Recursive, semantic, fixed-size strategies
  - `core.py`: Chunking quality scoring and validation
  - `helpers.py`: Text splitting utilities
  - `qwen_embedding_wrapper.py`: Semantic chunking with embeddings
  - `chonkie_adapter.py`: Third-party chunker integration

**L3b - HyPE Generation** (optional):
- `hype.py`: Hypothetical Prompt Embedding generation
  - Generates hypothetical questions for chunks at ingestion time
  - Stored in metadata for zero-cost query expansion at retrieval

**L4 - Reference Data**:
- `load_reference_data.py`: Load medical reference ranges
  - Converts reference data to document chunks
  - Adds structured metadata

**L5 - Indexing**:
- See Indexing Layer below

**L6 - Runtime**:
- Handled by `src/rag/runtime.py`

#### Indexing (`src/ingestion/indexing/`)
- `embedding.py`: Text embedding using Qwen models
- `keyword_index.py`: BM25 keyword search index
- `vector_store.py`: Hybrid vector store with persistence
  - Semantic search (cosine similarity)
  - Keyword search (BM25)
  - Score fusion (RRF)
  - Document deduplication
- `search.py`: Search algorithms (cosine similarity, RRF)
- `persistence.py`: JSON-based persistence for vectors
- `text_utils.py`: Text processing utilities

### 5. Evaluation Layer (`src/evals/`)

**Purpose**: Comprehensive pipeline quality assessment and LLM-as-a-judge evaluation

**Components**:

#### Assessment (`src/evals/assessment/`)
- `orchestrator.py`: End-to-end assessment orchestration
  - Coordinates all evaluation stages
  - Manages caching and artifact storage
  - W&B logging integration
- `answer_eval.py`: L6 answer quality evaluation
  - Uses DeepEval metrics (faithfulness, relevance, medical safety)
  - LLM-as-a-judge with Qwen models
- `retrieval_eval.py`: L5 retrieval quality evaluation
  - NDCG, MRR, precision metrics
  - Ablation studies (semantic vs keyword vs hybrid)
  - Diversity sweep (MMR lambda, overfetch multiplier)
- `l6_contract.py`: L6 evaluation contract and metrics
- `thresholds.py`: Quality threshold evaluation
- `reporting.py`: Summary generation and git provenance

#### Checks (`src/evals/checks/`)
Pipeline quality checks for each stage:
- `l0_download.py`: Download completeness and validation
- `l1_html.py`: HTML-to-Markdown quality assessment
- `l2_pdf.py`: PDF extraction quality checks
- `l3_chunking.py`: Chunk quality and distribution analysis
- `l4_reference.py`: Reference data validation
- `l5_index.py`: Index quality and coverage checks
- `shared.py`: Shared check utilities

#### Metrics (`src/evals/metrics/`)
- `medical.py`: Medical domain-specific metrics
  - Medical accuracy (strict medical error detection)
  - Hallucination detection
  - Reference citation quality

#### Synthetic (`src/evals/synthetic/`)
- `generator.py`: Synthetic test case generation
  - Generates realistic medical questions from reference data

#### Other
- `dataset_builder.py`: Build retrieval evaluation datasets
- `pipeline_assessment.py`: Compatibility facade for assessments
- `artifacts.py`: Artifact storage and run management
- `schemas.py`: Pydantic models for evaluation config/results
- `step_checks.py`: Pipeline step quality checks
- `deepeval_models.py`: DeepEval model wrappers

### 6. Infrastructure Layer (`src/infra/`)

**Purpose**: External service integration and storage

**Components**:

#### LLM (`src/infra/llm/`)
- `qwen_client.py`: Qwen API client
  - Synchronous and asynchronous generation
  - Streaming support
  - Retry logic with exponential backoff
  - OpenAI-compatible API interface

#### Storage (`src/infra/storage/`)
- `interfaces.py`: Storage abstractions (ChatHistoryStore)
- `file_chat_history_store.py`: File-based chat history persistence
  - Session-based history
  - TTL-based cleanup
  - Thread-safe operations

### 7. Configuration Layer (`src/config/`)

**Components**:
- `settings.py`: Pydantic-based configuration management
  - Environment variable loading
  - Type-safe defaults
  - Validation
- `paths.py`: Centralized path management

**Key Configuration Areas**:
- LLM models (generation, embedding, judge models)
- API keys and endpoints
- Storage paths
- Retrieval parameters (HyDE, HyPE, diversity)
- Rate limiting and security
- Evaluation settings (DeepEval, W&B)

### 8. CLI Layer (`src/cli/`)

**Purpose**: Command-line interfaces for development and operations

**Components**:
- `serve.py`: Development server (auto-reload)
- `serve_production.py`: Production server
- `ingest.py`: Ingestion pipeline CLI
- `eval_pipeline.py`: Evaluation pipeline CLI

### 9. Experiments Layer (`src/experiments/`)

**Purpose**: Experiment configuration and tracking

**Components**:
- `config.py`: Experiment configuration schemas
- `wandb_tracking.py`: W&B logging integration
- `wandb_history.py`: W&B run history queries

## Data Flow

### Chat Request Flow

```
1. HTTP Request
   ↓ (API Route: /chat)
2. Request Validation (Pydantic schemas)
   ↓ (Middleware: Auth → RateLimit → RequestID)
3. Use Case (process_chat_message)
   ├→ Load conversation history
   ├→ RAG Retrieval (retrieve_context)
   │  ├→ Initialize vector store (lazy)
   │  ├→ Query expansion (tokenization, acronyms, HyDE, HyPE)
   │  ├→ Semantic search (vector similarity)
   │  ├→ Keyword search (BM25)
   │  ├→ Score fusion (RRF)
   │  ├→ MMR reranking
   │  └→ Context building
   ├→ LLM Generation (QwenClient.generate)
   └→ Save to history
4. Response Formatting
   ↓
5. HTTP Response (with sources and optional pipeline trace)
```

### Ingestion Pipeline Flow (L0-L6)

```
L0: Download
  ├→ download_web.py: Fetch HTML from manifest
  └→ download_pdfs.py: Fetch PDFs from URLs

L1: HTML → Markdown
  └→ convert_html.py: Extract text, classify pages

L2: PDF Processing
  └→ load_pdfs.py: Extract text and tables

L3: Chunking
  ├→ chunk_text.py: Split documents into chunks
  ├→ Quality scoring (length, structure, entropy)
  └→ Metadata enrichment

L3b: HyPE Generation (optional)
  └→ hype.py: Generate hypothetical questions

L4: Reference Data
  └→ load_reference_data.py: Load medical ranges

L5: Indexing
  ├→ embedding.py: Generate embeddings
  ├→ keyword_index.py: Build BM25 index
  └→ vector_store.py: Store vectors with metadata

L6: Runtime Initialization
  └→ runtime.py: Load index into memory
```

### Evaluation Flow

```
1. Load Experiment Config
   ↓
2. Configure Runtime (experiment-specific settings)
   ↓
3. Pipeline Quality Checks (L0-L5)
   ├→ Download audit
   ├→ HTML quality assessment
   ├→ PDF extraction quality
   ├→ Chunking quality
   ├→ Reference data validation
   └→ Index quality
   ↓
4. Build Retrieval Dataset
   ↓
5. Retrieval Evaluation (L5)
   ├→ NDCG, MRR, precision
   ├→ Ablation studies
   └→ Diversity sweep
   ↓
6. Answer Quality Evaluation (L6)
   ├→ DeepEval metrics
   │  ├→ Faithfulness
   │  ├→ Relevance
   │  └→ Medical safety
   └→ LLM-as-a-judge reasoning
   ↓
7. Threshold Evaluation
   ↓
8. Generate Summary Report
   ↓
9. Log to W&B (optional)
```

## Key Abstractions and Interfaces

### Vector Store Interface
```python
class VectorStore:
    - add_documents(docs) → stats
    - similarity_search(query, top_k, search_mode) → results
    - similarity_search_with_trace(query, top_k, search_mode) → (results, trace)
    - search_hypothetical_questions(query, limit) → questions
    - clear() → None
```

### LLM Client Interface
```python
class QwenClient:
    - generate(prompt, context) → response
    - a_generate_stream(prompt, context) → AsyncGenerator[str, None]
    - embed(texts) → embeddings
```

### Chat History Store Interface
```python
class ChatHistoryStore:
    - get_history(session_id) → messages[]
    - save_message(session_id, role, content) → None
    - delete_session(session_id) → None
```

### Retrieval Configuration
```python
@dataclass
class RetrievalDiversityConfig:
    overfetch_multiplier: int
    max_chunks_per_source_page: int
    max_chunks_per_source: int
    mmr_lambda: float
    enable_diversification: bool
    search_mode: str  # "rrf_hybrid", "semantic_only", "bm25_only"
    enable_hyde: bool
    hyde_max_length: int
    enable_hype: bool
```

## Component Relationships

### Dependencies
- **Use Cases** depend on: RAG, Infrastructure (LLM, Storage)
- **RAG** depends on: Ingestion (Indexing), Configuration
- **API Routes** depend on: Use Cases, Infrastructure
- **Evaluation** depends on: RAG, Ingestion, Configuration

### Key Design Patterns

1. **Factory Pattern**: `src/app/factory.py` - FastAPI app creation
2. **Repository Pattern**: Vector store and history storage abstractions
3. **Strategy Pattern**: Chunking strategies, search modes
4. **Middleware Chain**: Request processing pipeline
5. **Facade Pattern**: `src/evals/pipeline_assessment.py` - Simplified assessment API
6. **Lazy Initialization**: Vector store loaded on first request
7. **Dependency Injection**: LLM client and history store passed to use cases

## Entry Points

### CLI Entry Points
- `uv run python -m src.cli.serve` - Development server
- `uv run python -m src.cli.ingest` - Run ingestion pipeline
- `uv run python -m src.cli.eval_pipeline` - Run evaluation

### API Entry Points
- `GET /health` - Health check
- `POST /chat` - Chat endpoint (non-streaming)
- `POST /chat/stream` - Chat endpoint (streaming)
- `GET /history/{session_id}` - Get chat history
- `DELETE /history/{session_id}` - Clear session
- `POST /evaluation/run` - Run evaluation
- `GET /evaluation/status/{run_id}` - Get evaluation status

### Module Entry Points
- `src.usecases.pipeline:main()` - Pipeline orchestration
- `src.rag.runtime:initialize_runtime_index()` - Runtime initialization
- `src.evals.pipeline_assessment:run_assessment()` - Evaluation orchestration

## Frontend Architecture

### Technology Stack
- **Framework**: SvelteKit (Vite-based)
- **Language**: TypeScript
- **Styling**: CSS (component-scoped)
- **Charts**: Chart.js
- **Markdown**: Svelte Markdown with custom renderers

### Key Frontend Components

#### Routes (`frontend/src/routes/`)
- `+page.svelte`: Main dashboard with pipeline visualization
- `+layout.svelte`: App shell with navigation
- `docs/pipeline/+page.svelte`: Pipeline documentation
- `eval/+page.svelte`: Evaluation dashboard

#### Components (`frontend/src/lib/components/`)
- **AppShell**: Main application layout
- **PipelineFlowDiagram**: Visual pipeline representation
- **MetricBar/MetricChart**: Metric visualization
- **QualityTab/RetrievalTab/IngestionTab/TrendingTab**: Evaluation tabs
- **DocumentInspector**: Document detail view
- **DrillDownModal**: Detailed metric drill-down
- **MarkdownRenderer**: Custom markdown rendering with syntax highlighting

#### Utilities (`frontend/src/lib/utils/`)
- `types.ts`: TypeScript type definitions
- `health-score.ts`: Health score calculation
- `eval.ts`: Evaluation data processing
- `format.ts`: Formatting utilities
- `export.ts`: Data export utilities

### Frontend-Backend Communication
- REST API for chat and evaluation
- Server-Sent Events (SSE) for streaming responses
- CORS-enabled for development

## Testing Strategy

### Test Categories

1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Multi-component interaction
3. **E2E Tests**: Full pipeline with real APIs (marked with `e2e_real_apis`)
4. **DeepEval Tests**: LLM-as-a-judge evaluation (marked with `deepeval`)

### Test Organization
- `tests/`: All backend tests
- `frontend/tests/`: Frontend Playwright tests

### Key Test Files
- `test_chat_multi_turn.py`: Multi-turn conversation testing
- `test_chat_sources.py`: Source attribution testing
- `test_retrieval.py`: Retrieval quality testing
- `test_hyde.py`: HyDE query expansion testing
- `test_eval_*.py`: Evaluation framework testing
- `test_pipeline_assessment_smoke.py`: End-to-end pipeline testing

## Security Considerations

### Authentication
- API key validation via `X-API-Key` header
- Anonymous session tracking for unauthenticated users

### Rate Limiting
- Per-IP rate limiting (configurable)
- Stricter limits for anonymous chat requests

### Input Validation
- Pydantic schema validation for all inputs
- Message length limits
- SQL injection prevention (no SQL used)

### CORS
- Configurable allowed origins
- Credentials support for authenticated requests

## Performance Optimizations

### Vector Store
- Lazy initialization (loads on first request)
- Persistent JSON storage (no re-embedding on restart)
- Batch embedding with configurable batch size

### Retrieval
- Query expansion with caching
- Overfetch + diversification (retrieves more, returns diverse subset)
- MMR reranking for result diversity

### LLM
- Streaming responses for better UX
- Retry logic with exponential backoff
- Connection pooling

### Evaluation
- DeepEval result caching (retrieval + generation)
- Metric result caching
- Concurrent query evaluation (configurable)

## Deployment Considerations

### Environment Variables
See `src/config/settings.py` for complete list

### Docker Support
- Docker Compose for local development
- Backend and frontend services
- Volume mounting for data persistence

### Production Readiness
- Health check endpoint
- Request logging
- Error handling with proper status codes
- Graceful degradation (e.g., if W&B logging fails)
