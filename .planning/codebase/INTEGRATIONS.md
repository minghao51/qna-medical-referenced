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
- **Auth:** `DASHSCOPE_API_KEY` env var (or `APP__LLM__DASHSCOPE_API_KEY`)
- **Usage:** RAG answer generation, embedding vectors, HyDE, HyPE, keyword extraction, chunk summarization, LLM-as-judge evaluation

#### LiteLLM / OpenRouter (Secondary)
- **SDK:** `litellm` Python SDK
- **Client:** `src/infra/llm/litellm_client.py` — `LiteLLMClient`
- **Default model:** `google/gemma-4-31b-it` (via OpenRouter)
- **Auth:** `OPENROUTER_API_KEY` env var (or `APP__LLM__OPENROUTER_API_KEY`)
- **Usage:** Alternative LLM provider when `LLM_PROVIDER=litellm`
- **Config:** `LITELLM_MODEL` overrides `OPENROUTER_MODEL` if set; supports any LiteLLM-compatible provider

### Google Gemini (Experimental)
- **Auth:** `GEMINI_API_KEY` env var
- **Model:** `models/gemini-3-flash-preview`
- **Config:** `GEMINI__MODEL` env var
- **Note:** Referenced in `.env.example`; appears experimental/supplementary, not actively used in codebase

## Databases

### ChromaDB (Vector Store)
- **SDK:** `chromadb` Python SDK
- **Store:** `src/ingestion/indexing/chroma_store.py` — `ChromaVectorStore` managing in-memory index with persistent JSON snapshots
- **Persistence:** Local filesystem at `data/chroma/` (configurable via `settings.storage.chroma_persist_directory` or `APP__STORAGE__CHROMA_PERSIST_DIRECTORY`)
- **Collection:** `medical_docs` (configurable via `settings.storage.collection_name` or `APP__STORAGE__COLLECTION_NAME`)
- **Modes:**
  - **Embedded:** Default; uses `chromadb.PersistentClient` for local storage
  - **Client/Server:** Optional; connects via `chromadb.HttpClient` when `CHROMA_SERVER_HOST` is set
- **Features:** Semantic search, BM25 keyword search, Reciprocal Rank Fusion (RRF) hybrid search, MMR diversification
- **Schema:** Documents with metadata (source, page, quality_score, chunk_type, hypothetical_questions, keywords)

### File-Based Storage
- **Chat History:** `src/infra/storage/file_chat_history_store.py` — `FileChatHistoryStore`
- **Location:** Filesystem-backed (anonymous session history with configurable TTL and per-session message truncation)
- **Session:** Cookie-based session management (`chat_session_id` cookie)

### W&B (Weights & Biases) — Experiment Tracking
- **SDK:** `wandb` Python SDK
- **Auth:** `WANDB_API_KEY` env var (or `APP__WANDB__WANDB_API_KEY`)
- **Usage:** Experiment run logging, ablation study tracking, metric history queries
- **Cache:** In-process TTL cache (`settings.wandb.wandb_cache_ttl_seconds`, default 60s)
- **Config:** `wandb/` directory for local run data

## Configuration Sources

The application uses a 3-layer config stack with `config/settings.yaml` as source of truth:

| Source | Example | Priority |
|--------|---------|----------|
| Direct kwargs | `Settings(api=ApiConfig(cors_allowed_origins="..."))` | Highest |
| Env vars (`APP__` prefix) | `APP__LLM__MODEL_NAME=qwen3.5-plus` | High |
| `.env` file | `DASHSCOPE_API_KEY=sk-...` | Medium |
| `config/settings.yaml` | `llm: {model_name: qwen3.5-flash}` | Default |

Legacy flat env var names (e.g., `MODEL_NAME`, `CORS_ALLOWED_ORIGINS`) are supported via `_LEGACY_FIELD_MAP` for backward compatibility.

## Authentication

### API Key Authentication (Custom/Built-in)
- **Implementation:** `src/app/security.py` + `src/app/middleware/auth.py`
- **Mechanism:** `X-API-Key` header validated against configured keys
- **Key Storage:** Env vars `API_KEYS` (comma-separated plaintext) or `API_KEYS_JSON` (JSON array with id, key/hash, owner, role, status) — mapped to `settings.api.api_keys` / `settings.api.api_keys_json`
- **Hashing:** `bcrypt` (preferred, 12 rounds) with legacy SHA256 support (deprecated)
- **Enforcement:** Enforced in production via `validate_security_configuration()`; disabled in development
- **Roles/Permissions:** Key records support `owner`, `role`, `status` fields; bypass via `settings.api.rate_limit_bypass_key_ids` / `settings.api.rate_limit_bypass_roles`

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
| `pydantic` / `pydantic-settings` | `src/config/settings.py`, `src/config/models/` | Configuration management with YAML + env var sources |
| `chart.js`             | Frontend (`package.json`)                | Data visualization in eval dashboards         |
| `mermaid`              | Frontend (`package.json`)                | Diagram rendering                             |
| `highlight.js`         | Frontend (`package.json`)                | Code/syntax highlighting                      |
| `marked` / `svelte-markdown` | Frontend (`package.json`)        | Markdown rendering in chat responses          |
| `playwright`           | Frontend E2E tests                       | Browser automation testing                    |

## Environment Variables

### Primary (APP__-prefixed, nested)

| Variable                        | Config Path                          | Required | Default                                          |
|---------------------------------|--------------------------------------|----------|--------------------------------------------------|
| `APP__APP__ENVIRONMENT`         | `settings.app.environment`           | No       | `development`                                    |
| `APP__API__CORS_ALLOWED_ORIGINS`| `settings.api.cors_allowed_origins`  | No       | `http://localhost:5173,...`                      |
| `APP__API__RATE_LIMIT_PER_MINUTE`| `settings.api.rate_limit_per_minute`| No       | `60`                                             |
| `APP__LLM__DASHSCOPE_API_KEY`   | `settings.llm.dashscope_api_key`     | Yes*     | —                                                |
| `APP__LLM__MODEL_NAME`          | `settings.llm.model_name`            | No       | `qwen3.5-flash`                                  |
| `APP__LLM__QWEN_BASE_URL`       | `settings.llm.qwen_base_url`         | No       | `https://dashscope-us.aliyuncs.com/compatible-mode/v1` |
| `APP__LLM__EMBEDDING_MODEL`     | `settings.llm.embedding_model`       | No       | `text-embedding-v4`                              |
| `APP__LLM__PROVIDER`            | `settings.llm.provider`              | No       | `qwen`                                           |
| `APP__LLM__OPENROUTER_API_KEY`  | `settings.llm.openrouter_api_key`    | No       | —                                                |
| `APP__STORAGE__COLLECTION_NAME` | `settings.storage.collection_name`   | No       | `medical_docs`                                   |
| `APP__STORAGE__CHROMA_PERSIST_DIRECTORY` | `settings.storage.chroma_persist_directory` | No | `data/chroma`                       |
| `APP__WANDB__WANDB_API_KEY`     | `settings.wandb.wandb_api_key`       | No       | —                                                |

### Legacy (flat, backward-compatible — mapped via `_LEGACY_FIELD_MAP`)

| Variable                        | Maps To                               | Required | Default                                          |
|---------------------------------|---------------------------------------|----------|--------------------------------------------------|
| `DASHSCOPE_API_KEY`             | `settings.llm.dashscope_api_key`      | Yes*     | —                                                |
| `MODEL_NAME`                    | `settings.llm.model_name`             | No       | `qwen3.5-flash`                                  |
| `QWEN_BASE_URL`                 | `settings.llm.qwen_base_url`          | No       | `https://dashscope-us.aliyuncs.com/compatible-mode/v1` |
| `EMBEDDING_MODEL`               | `settings.llm.embedding_model`        | No       | `text-embedding-v4`                              |
| `LLM_PROVIDER`                  | `settings.llm.provider`               | No       | `qwen`                                           |
| `OPENROUTER_API_KEY`            | `settings.llm.openrouter_api_key`     | No       | —                                                |
| `OPENROUTER_MODEL`              | `settings.llm.openrouter_model`       | No       | `google/gemma-4-31b-it`                          |
| `LITELLM_MODEL`                 | `settings.llm.litellm_model`          | No       | —                                                |
| `WANDB_API_KEY`                 | `settings.wandb.wandb_api_key`        | No       | —                                                |
| `GEMINI_API_KEY`                | — (no model)                          | No       | —                                                |
| `GEMINI__MODEL`                 | — (no model)                          | No       | `models/gemini-3-flash-preview`                  |
| `API_KEYS`                      | `settings.api.api_keys`               | No       | — (empty, auth disabled)                         |
| `API_KEYS_JSON`                 | `settings.api.api_keys_json`          | No       | —                                                |
| `RATE_LIMIT_PER_MINUTE`         | `settings.api.rate_limit_per_minute`  | No       | `60`                                             |
| `ANONYMOUS_CHAT_RATE_LIMIT_PER_MINUTE` | `settings.api.anonymous_chat_rate_limit_per_minute` | No | `12`                             |
| `COLLECTION_NAME`               | `settings.storage.collection_name`    | No       | `medical_docs`                                   |
| `CHROMA_PERSIST_DIRECTORY`      | `settings.storage.chroma_persist_directory` | No  | `data/chroma`                                    |
| `CHROMA_SERVER_HOST`            | `settings.storage.chroma_server_host` | No       | — (embedded mode)                                |
| `CHROMA_SERVER_PORT`            | `settings.storage.chroma_server_port` | No       | `8000`                                           |
| `CORS_ALLOWED_ORIGINS`          | `settings.api.cors_allowed_origins`   | No       | `http://localhost:5173,...`                      |
| `TRUST_PROXY_HEADERS`           | `settings.api.trust_proxy_headers`    | No       | `false`                                          |
| `PRODUCTION_PROFILE`            | `settings.production.production_profile` | No    | `baseline_cross_encoder`                         |
