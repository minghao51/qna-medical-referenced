# Integrations

## External APIs and Services

### LLM Providers

#### Alibaba Dashscope / Qwen (Primary)
- **SDK:** `openai` Python SDK (OpenAI-compatible API)
- **Client:** `src/infra/llm/qwen_client.py` — `QwenClient` using `openai.AsyncOpenAI` and `openai.OpenAI`
- **Base URL:** `https://dashscope-us.aliyuncs.com/compatible-mode/v1` (US region) or `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` (international)
- **Models:**
  - Chat: `qwen3.5-flash` (default), `qwen3.5-plus`, `qwen-plus`, `qwen-max`, `qwen3.5-27b`
  - Embedding: `text-embedding-v4` (2048 dimensions)
  - Judge (light): `qwen3.5-35b-a3b`
  - Judge (heavy): `qwen3.5-flash`
- **Auth:** `DASHSCOPE_API_KEY` env var
- **Usage:** RAG answer generation, embedding vectors, HyDE, HyPE, keyword extraction, chunk summarization, LLM-as-judge evaluation

#### LiteLLM / OpenRouter (Secondary)
- **SDK:** `litellm` Python SDK
- **Client:** `src/infra/llm/litellm_client.py` — `LiteLLMClient`
- **Default model:** `google/gemma-4-31b-it` (via OpenRouter)
- **Auth:** `OPENROUTER_API_KEY` env var
- **Usage:** Alternative LLM provider when `LLM_PROVIDER=litellm`
- **Config:** `LITELLM_MODEL` overrides `OPENROUTER_MODEL` if set; supports any LiteLLM-compatible provider

### Google Gemini (Experimental)
- **Auth:** `GEMINI_API_KEY` env var
- **Model:** `models/gemini-3-flash-preview`
- **Config:** `GEMINI__MODEL` env var
- **Note:** Referenced in `.env.example`; appears experimental/supplementary

## Databases

### ChromaDB (Vector Store)
- **SDK:** `chromadb` Python SDK
- **Store:** `src/ingestion/indexing/chroma_store.py` — `ChromaStore` managing in-memory index with persistent JSON snapshots
- **Persistence:** Local filesystem at `data/chroma/` (configurable via `CHROMA_PERSIST_DIRECTORY`)
- **Collection:** `medical_docs` (configurable via `COLLECTION_NAME`)
- **Modes:**
  - **Embedded:** Default; uses `chromadb.PersistentClient` for local storage
  - **Client/Server:** Optional; connects via `chromadb.HttpClient` when `CHROMA_SERVER_HOST` is set
- **Features:** Semantic search, BM25 keyword search, Reciprocal Rank Fusion (RRF) hybrid search, MMR diversification
- **Schema:** Documents with metadata (source, page, quality_score, chunk_type, hypothetical_questions, keywords)

### File-Based Storage
- **Chat History:** `src/infra/storage/file_chat_history_store.py` — `FileChatHistoryStore`
- **Location:** Filesystem-backed (anonymous session history with 30-day TTL)
- **Session:** Cookie-based session management (`chat_session_id` cookie)

### W&B (Weights & Biases) — Experiment Tracking
- **SDK:** `wandb` Python SDK
- **Auth:** `WANDB_API_KEY` env var
- **Usage:** Experiment run logging, ablation study tracking, metric history queries
- **Cache:** In-process TTL cache (`WANDB_CACHE_TTL_SECONDS`, default 60s)
- **Config:** `wandb/` directory for local run data

## Authentication Providers

### API Key Authentication (Custom/Built-in)
- **Implementation:** `src/app/security.py` + `src/app/middleware/auth.py`
- **Mechanism:** `X-API-Key` header validated against configured keys
- **Key Storage:** Env vars `API_KEYS` (comma-separated plaintext) or `API_KEYS_JSON` (JSON array with id, key/hash, owner, role, status)
- **Hashing:** `bcrypt` (preferred, 12 rounds) with legacy SHA256 support (deprecated)
- **Enforcement:** Enforced in production via `validate_security_configuration()`; disabled in development
- **Roles/Permissions:** Key records support `owner`, `role`, `status` fields; bypass via `RATE_LIMIT_BYPASS_KEY_IDS` / `RATE_LIMIT_BYPASS_ROLES`

## Webhooks

No external webhook integrations detected. The application is a standalone API server that does not register or expose webhooks.

## Third-Party SDKs

| SDK                    | Import Location                          | Purpose                                      |
|------------------------|------------------------------------------|----------------------------------------------|
| `openai`               | `src/infra/llm/qwen_client.py`, `src/ingestion/indexing/embedding.py`, `src/evals/deepeval_models.py` | LLM client for Qwen/Dashscope (OpenAI-compatible) |
| `litellm`              | `src/infra/llm/litellm_client.py`, `src/evals/deepeval_models.py` | Multi-provider LLM gateway                   |
| `chromadb`             | `src/ingestion/indexing/chroma_store.py`, `src/ingestion/indexing/migrate.py` | Vector database                              |
| `wandb`                | Experiment scripts, evaluation pipeline  | Experiment tracking                           |
| `bcrypt`               | `src/app/security.py`                    | API key hashing                               |
| `httpx`                | `src/ingestion/steps/download_web.py`, `src/ingestion/steps/download_pdfs.py` | Async HTTP client for document downloading |
| `nltk`                 | `src/ingestion/indexing/text_utils.py`   | Tokenization, stopwords, Snowball stemming    |
| `deepeval`             | `src/evals/assessment/answer_eval.py`, `src/evals/metrics/medical.py`, `src/evals/synthetic/generator.py`, `src/app/routes/evaluation.py` | LLM evaluation metrics (faithfulness, answer relevancy, GEval) |
| `sentence-transformers`| `src/rag/reranker.py`                    | Cross-encoder reranking (`BAAI/bge-reranker-base`) |
| `chonkie`              | `src/ingestion/steps/chunking/chonkie_adapter.py` | Semantic chunking (optional)                 |
| `spacy`                | Optional (`medical` dep group)           | Medical entity detection / NER               |
| `langchain` / `langchain-openai` | `src/evals/` (evaluation group)  | DeepEval integration / synthetic data generation |
| `chart.js`             | Frontend (`package.json`)                | Data visualization in eval dashboards         |
| `mermaid`              | Frontend (`package.json`)                | Diagram rendering                             |
| `highlight.js`         | Frontend (`package.json`)                | Code/syntax highlighting                      |
| `marked` / `svelte-markdown` | Frontend (`package.json`)        | Markdown rendering in chat responses          |
| `playwright`           | Frontend E2E tests                       | Browser automation testing                    |

## Environment Variables Referencing External Services

| Variable                        | Service              | Required | Default                                          |
|---------------------------------|----------------------|----------|--------------------------------------------------|
| `DASHSCOPE_API_KEY`             | Alibaba Dashscope    | Yes      | —                                                |
| `MODEL_NAME`                    | Dashscope/Qwen       | No       | `qwen3.5-flash`                                  |
| `QWEN_BASE_URL`                 | Dashscope API        | No       | `https://dashscope-us.aliyuncs.com/compatible-mode/v1` |
| `EMBEDDING_MODEL`               | Dashscope Embeddings | No       | `text-embedding-v4`                              |
| `LLM_PROVIDER`                  | LLM routing          | No       | `qwen`                                           |
| `OPENROUTER_API_KEY`            | OpenRouter           | No       | —                                                |
| `OPENROUTER_MODEL`              | OpenRouter/LiteLLM   | No       | `google/gemma-4-31b-it`                          |
| `LITELLM_MODEL`                 | LiteLLM              | No       | —                                                |
| `WANDB_API_KEY`                 | Weights & Biases     | No       | —                                                |
| `WANDB_CACHE_TTL_SECONDS`       | W&B                  | No       | `60`                                             |
| `GEMINI_API_KEY`                | Google Gemini        | No       | —                                                |
| `GEMINI__MODEL`                 | Google Gemini        | No       | `models/gemini-3-flash-preview`                  |
| `API_KEYS`                      | App Auth             | No       | — (empty, auth disabled)                         |
| `API_KEYS_JSON`                 | App Auth             | No       | —                                                |
| `RATE_LIMIT_PER_MINUTE`         | Rate Limiting        | No       | `60`                                             |
| `ANONYMOUS_CHAT_RATE_LIMIT_PER_MINUTE` | Rate Limiting | No   | `12`                                             |
| `RATE_LIMIT_BYPASS_KEY_IDS`     | Rate Limiting        | No       | —                                                |
| `RATE_LIMIT_BYPASS_ROLES`       | Rate Limiting        | No       | —                                                |
| `COLLECTION_NAME`               | ChromaDB             | No       | `medical_docs`                                   |
| `CHROMA_PERSIST_DIRECTORY`      | ChromaDB             | No       | `data/chroma`                                    |
| `CHROMA_SERVER_HOST`            | ChromaDB (server)    | No       | — (embedded mode)                                |
| `CHROMA_SERVER_PORT`            | ChromaDB (server)    | No       | `8000`                                           |
| `VITE_API_URL`                  | Frontend → Backend   | No       | `http://localhost:8000`                          |
| `CORS_ALLOWED_ORIGINS`          | CORS                 | No       | `http://localhost:5173,...`                      |
| `TRUST_PROXY_HEADERS`           | Proxy                | No       | `false`                                          |
| `PRODUCTION_PROFILE`            | RAG Config           | No       | `baseline_cross_encoder`                         |
