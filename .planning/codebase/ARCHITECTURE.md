# Architecture Analysis - QnA Medical Referenced System

## Overview
This is a full-stack medical QnA system with FastAPI backend and SvelteKit frontend, implementing a RAG (Retrieval-Augmented Generation) architecture for health screening interpretation.

## Architecture Patterns

### 1. **Clean Architecture Pattern**
The backend follows a clean architecture with clear separation of concerns:
- **Domain Layer**: Core business logic in `src/usecases`
- **Application Layer**: Controllers and API handlers in `src/app/routes`
- **Infrastructure Layer**: External services and tools in `src/infra`
- **Presentation Layer**: HTTP API endpoints in `src/app`

### 2. **MVC Pattern**
- **Models**: Domain entities and data structures throughout the codebase
- **Views**: Svelte components in `frontend/src/lib/components`
- **Controllers**: Route handlers in `src/app/routes`

### 3. **Hexagonal Architecture**
- Core business logic is isolated from external dependencies
- Dependency injection container in `src/infra/di`
- External adapters for LLM, storage, and indexing services

### 4. **CQRS-like Pattern**
Separation of read and write operations:
- Query operations for chat and retrieval
- Command operations for ingestion and evaluation
- Event-driven pipeline for evaluation workflows

## Key Components and Layers

### Backend Architecture
```
src/
├── app/                    # Presentation Layer (FastAPI)
│   ├── routes/           # API Controllers
│   ├── middleware/       # Cross-cutting concerns
│   └── schemas/          # Data validation
├── usecases/             # Business Logic Layer
│   ├── chat.py           # Chat interaction logic
│   └── pipeline.py       # Evaluation pipeline
├── rag/                  # Domain Layer (RAG system)
│   ├── hyde.py          # Hypothetical Document Embedding
│   ├── reranker.py      # Re-ranking algorithms
│   └── medical_expansion.py# Medical domain expansion
├── infra/               # Infrastructure Layer
│   ├── di/              # Dependency Injection
│   ├── storage/         # Storage abstractions
│   └── llm/             # LLM provider adapters
├── evals/               # Evaluation System
│   ├── assessment/      # Evaluation orchestrator
│   └── checks/          # Data validation checks
└── ingestion/           # Data Processing Pipeline
    ├── steps/           # Ingestion pipeline steps
    └── indexing/        # Vector indexing
```

### Frontend Architecture (SvelteKit)
```
frontend/src/
├── app.html             # Root HTML template
├── routes/              # File-based routing
│   ├── +layout.svelte  # Root layout
│   ├── +page.svelte    # Home page
│   └── eval/           # Evaluation pages
└── lib/
    ├── components/      # Reusable UI components
    │   ├── markdown/    # Markdown rendering components
    │   └── [various UI components]
    ├── utils/           # Utility functions
    └── styles/          # CSS styles
```

## Data Flow

### 1. **Chat Flow**
```
User Input → FastAPI Route → Use Case → RAG System → LLM → Response
    ↓
Chat History Storage → Retrieval → Context Building → Generation
```

### 2. **Ingestion Flow**
```
Source Documents → Ingestion Pipeline → Chunking → Embedding → Vector Store
    ↓                    ↓                ↓           ↓
  HTML/PDF → Text Extraction → Chunk Split → Vector DB
```

### 3. **Evaluation Flow**
```
Dataset → Evaluation Pipeline → Multiple Checks → Metrics Report
    ↓          ↓                    ↓            ↓
  Queries → RAG System → Quality Assessment → Scorecards
```

## Abstractions and Design Patterns

### 1. **Dependency Injection**
- Container-based DI in `src/infra/di`
- Decouples components from concrete implementations
- Enables testing and swapping of services

### 2. **Strategy Pattern**
- Different chunking strategies in `src/ingestion/steps/chunking/`
- Multiple embedding providers
- Various reranking algorithms

### 3. **Factory Pattern**
- Application factory in `src/app/factory.py`
- Route registration through factory methods
- Middleware configuration in specific order

### 4. **Repository Pattern**
- Storage abstractions in `src/infra/storage/`
- Data access layer implementation
- Enables different storage backends

### 5. **Middleware Pattern**
- Ordered middleware execution:
  1. CORS (must be first)
  2. Rate Limiting
  3. API Key Authentication
  4. Request ID (outermost for error tracking)

## Entry Points

### Backend Entry Points
1. **Main Application**: `src/app/factory.py` - FastAPI application factory
2. **Development Server**: `src/cli/serve.py` - Local development server
3. **Production Server**: `src/cli/serve_production.py` - Production deployment
4. **Ingestion CLI**: `src/cli/ingest.py` - Data ingestion pipeline
5. **Evaluation CLI**: `src/cli/eval_pipeline.py` - Evaluation pipeline

### Frontend Entry Points
1. **SvelteKit App**: `frontend/src/app.html` - Root application template
2. **Routes**: `frontend/src/routes/` - File-based routing
3. **Main Layout**: `frontend/src/routes/+layout.svelte` - Root layout component

## Configuration and Environment

### Backend Configuration
- Environment variables in `.env`
- Settings in `src/config/settings.py`
- Configuration context in `src/config/context.py`
- Path management in `src/config/paths.py`

### Frontend Configuration
- Vite/SvelteKit config in `frontend/svelte.config.js`
- TypeScript definitions in `frontend/src/app.d.ts`
- Build configuration in `frontend/package.json`

## Key Technical Features

### 1. **RAG System**
- Hypothetical Document Embedding (HyDE)
- Medical domain expansion for context
- Re-ranking for improved relevance
- Production profiles for different deployment scenarios

### 2. **Evaluation System**
- Multi-layer evaluation checks (L0-L6)
- Automated assessment pipeline
- Quality metrics and reporting
- Ablation studies support

### 3. **Scalability Features**
- Dependency injection for testability
- Containerized deployment with Docker
- Production profiles for different environments
- Vector store optimization

### 4. **Security and Performance**
- API key authentication
- Rate limiting middleware
- Request ID tracking
- CORS configuration for development
