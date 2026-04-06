# External Integrations

**Analysis Date:** 2026-04-06

## APIs & External Services

**LLM Provider:**
- Alibaba Dashscope (Qwen models) - Text generation and embeddings
- SDK/Client: openai (OpenAI-compatible endpoint)
- Auth: DASHSCOPE_API_KEY
- Models: qwen3.5-flash, qwen3.5-plus, qwen-plus, qwen-max, qwen3.5-35b-a3b
- Base URL: https://dashscope-us.aliyuncs.com/compatible-mode/v1

**Experiment Tracking:**
- Weights & Biases (W&B) - Experiment logging and run history
- SDK/Client: wandb
- Auth: WANDB_API_KEY (optional)

**Evaluation:**
- DeepEval - RAG pipeline evaluation (faithfulness, answer correctness)
- LiteLLM - Multi-provider LLM abstraction for evaluation

## Data Storage

**Databases:**
- ChromaDB (embedded) - Vector database for document embeddings
- Connection: Local filesystem (data/chroma)
- Client: chromadb Python SDK
- Collection: medical_docs (configurable via COLLECTION_NAME)

**File Storage:**
- Local filesystem only
- Raw documents: data/raw (HTML, PDF)
- Vector index: data/chroma (persistent ChromaDB)
- Evaluation cache: data/evals/cache
- Chat history: file-backed JSON

**Caching:**
- DeepEval answer/metric cache (local filesystem)
- W&B history cache (in-memory, 60s TTL)

## Authentication & Identity

**Auth Provider:**
- Custom API key authentication
- Implementation: X-API-Key header validation against configured keys (API_KEYS env var)
- Anonymous session support via browser cookies (anon_browser_id, chat_session_id)
- Rate limiting per IP and per anonymous browser session

## Monitoring & Observability

**Error Tracking:**
- Python logging module (structured logging)
- W&B for experiment tracking

**Logs:**
- Standard Python logging with configurable log level
- Request ID middleware for request tracing

## CI/CD & Deployment

**Hosting:**
- Docker Compose (backend + frontend services)
- Backend: uvicorn on port 8000
- Frontend: Vite dev server / Node.js on port 5173

**CI Pipeline:**
- Playwright E2E tests (containerized)
- pytest with markers (live_api, deepeval, e2e_real_apis, slow)

## Environment Configuration

**Required env vars:**
- DASHSCOPE_API_KEY - Alibaba Dashscope API key

**Optional env vars:**
- MODEL_NAME - Qwen model selection
- EMBEDDING_MODEL - Embedding model selection
- API_KEYS - Comma-separated API keys for auth
- RATE_LIMIT_PER_MINUTE - Rate limiting threshold
- WANDB_API_KEY - Weights & Biases key
- VITE_API_URL - Frontend API endpoint
- CORS_ALLOWED_ORIGINS - Allowed CORS origins
- PRODUCTION_PROFILE - RAG profile selection
- HYDE_ENABLED / HYPE_ENABLED - Query expansion features
- ENABLE_RERANKING - Cross-encoder reranking toggle

**Secrets location:**
- .env file (local development)
- Environment variables (production/Docker)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

---

*Integration audit: 2026-04-06*
