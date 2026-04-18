"""Application configuration management.

This module loads and validates configuration from environment variables
and .env file using Pydantic BaseSettings. Configuration is automatically
validated on import, ensuring type safety and providing defaults for
development convenience.

Example:
    From anywhere in the application:
        from src.config import settings
        api_key = settings.dashscope_api_key
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration with environment variable support.

    Configuration is loaded from .env file or environment variables.
    Defaults are provided for development convenience. For production,
    ensure sensitive values are set via environment variables.

    Attributes:
        model_config: Pydantic settings configuration dict
    """

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    environment: str = "development"
    """Runtime environment name.

    Supported values: development, test, staging, production.
    """

    log_level: str = "INFO"
    """Application log level."""

    cors_allowed_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:3000"
    """Comma-separated allowed CORS origins."""

    # LLM Configuration
    llm_provider: str = "qwen"
    """LLM provider to use for text generation.

    Default: "qwen" (direct Dashscope/OpenAI-compatible endpoint)
    Alternatives: "litellm" (LiteLLM with OpenRouter or any supported provider)

    Environment variable: LLM_PROVIDER
    """

    dashscope_api_key: str = ""
    """Alibaba Dashscope API key for Qwen models.

    Required when llm_provider="qwen". Obtain from:
    https://dashscope-us.aliyuncs.com/

    Environment variable: DASHSCOPE_API_KEY
    """

    model_name: str = "qwen3.5-flash"
    """Qwen model to use for text generation (when llm_provider="qwen").

    Default: "qwen3.5-flash" (fast, cost-effective)
    Alternatives: "qwen3.5-plus", "qwen-plus", "qwen-max"

    Environment variable: MODEL_NAME
    """

    # LiteLLM / OpenRouter Configuration
    openrouter_api_key: str = ""
    """OpenRouter API key for LiteLLM provider.

    Required when llm_provider="litellm". Obtain from:
    https://openrouter.ai/settings/keys

    Environment variable: OPENROUTER_API_KEY
    """

    openrouter_model: str = "google/gemma-4-31b-it"
    """Default model for LiteLLM/OpenRouter text generation.

    Default: "google/gemma-4-31b-it"
    See available models at: https://openrouter.ai/models

    Environment variable: OPENROUTER_MODEL
    """

    litellm_model: str = ""
    """Generic LiteLLM model string (takes precedence over openrouter_model if set).

    Format follows LiteLLM conventions, e.g. "openrouter/google/gemma-4-31b-it"
    When empty, falls back to openrouter_model with openrouter/ prefix.

    Environment variable: LITELLM_MODEL
    """

    embedding_model: str = "text-embedding-v4"
    """Qwen embedding model for vector search.

    Default: "text-embedding-v4" (2048-dimensional vectors)

    Environment variable: EMBEDDING_MODEL
    """

    embedding_batch_size: int = 10
    """Default batch size for embedding generation.

    Default: 10

    Environment variable: EMBEDDING_BATCH_SIZE
    """

    qwen_base_url: str = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    """Qwen API base URL (OpenAI compatible).

    Default: US (Virginia) region (https://dashscope-us.aliyuncs.com/compatible-mode/v1)

    Environment variable: QWEN_BASE_URL
    """

    # LLM-as-a-Judge Configuration
    judge_model_light: str = "qwen3.5-35b-a3b"
    """Lightweight model for simple classification tasks (3B active params)."""

    judge_model_heavy: str = "qwen3.5-flash"
    """Heavyweight model for complex Chain-of-Thought reasoning."""

    judge_model_light_litellm: str = "google/gemma-4-31b-it"
    """LiteLLM model for lightweight judge tasks (when llm_provider="litellm")."""

    judge_model_heavy_litellm: str = "google/gemma-4-31b-it"
    """LiteLLM model for heavyweight judge tasks (when llm_provider="litellm")."""

    judge_temperature: float = 0.0
    """Temperature for judge models (0 = deterministic, repeatable)."""

    deepeval_query_concurrency: int = 2
    """Maximum number of queries to evaluate concurrently in DeepEval answer evaluation."""

    deepeval_metric_concurrency: int = 3
    """Maximum number of DeepEval metrics to execute concurrently per query."""

    deepeval_metric_timeout_seconds: int = 90
    """Maximum time to wait for a single DeepEval metric before marking it as errored."""

    deepeval_answer_cache_enabled: bool = True
    """Reuse cached retrieval + answer generation outputs across evaluation runs."""

    deepeval_metric_cache_enabled: bool = True
    """Reuse cached metric outputs for unchanged query/context/answer triples."""

    deepeval_cache_dir: str = "data/evals/cache"
    """Directory for DeepEval retrieval/generation cache files."""

    deepeval_cache_schema_version: int = 2
    """Schema version for DeepEval cache payloads."""

    deepeval_faithfulness_truths_limit: int = 8
    """Limit extracted truths for faithfulness to reduce prompt size and latency."""

    judge_max_tokens: int = 1024
    """Maximum completion tokens for LLM-as-a-judge responses."""

    wandb_api_key: str = ""
    """Weights & Biases API key.

    Optional. Used for logging runs and querying remote run history.

    Environment variable: WANDB_API_KEY
    """

    wandb_cache_ttl_seconds: int = 60
    """In-process TTL for W&B history/run-detail cache.

    Default: 60 seconds.

    Environment variable: WANDB_CACHE_TTL_SECONDS
    """

    # Storage Configuration
    collection_name: str = "medical_docs"
    """ChromaDB collection name for vector storage.

    Default: "medical_docs"
    Used to isolate different document sets in the same vector database.

    Environment variable: COLLECTION_NAME
    """

    production_profile: str | None = "baseline_cross_encoder"
    """Production profile to apply at startup.

    When set, loads the optimal configuration from the ablation study
    and applies it before building the vector index.

    Supported values: pymupdf_semantic_hybrid, baseline, baseline_cross_encoder
    Default: baseline_cross_encoder

    Environment variable: PRODUCTION_PROFILE
    """

    data_dir: str = "data/raw"
    """Directory for raw downloaded documents.

    Default: "data/raw"
    Contains downloaded HTML/PDF files before processing.

    Environment variable: DATA_DIR
    """

    chroma_persist_directory: str = "data/chroma"
    """Directory for persistent ChromaDB storage.

    Default: "data/chroma"
    Contains the ChromaDB persistent database files. Must be preserved between runs.

    Environment variable: CHROMA_PERSIST_DIRECTORY
    """

    chroma_server_host: str = ""
    """ChromaDB server host for HTTP client mode.

    Default: "" (use embedded PersistentClient)
    When set (e.g. "localhost"), connects to a ChromaDB server via HttpClient
    instead of using the embedded PersistentClient.

    Environment variable: CHROMA_SERVER_HOST
    """

    chroma_server_port: int = 8000
    """ChromaDB server port for HTTP client mode.

    Default: 8000
    Only used when chroma_server_host is set.

    Environment variable: CHROMA_SERVER_PORT
    """

    retrieval_overfetch_multiplier: int = 4
    """Multiplier used to overfetch retrieval candidates before reranking."""

    max_chunks_per_source_page: int = 2
    """Maximum retrieved chunks allowed from the same source page."""

    max_chunks_per_source: int = 3
    """Maximum retrieved chunks allowed from the same source document."""

    mmr_lambda: float = 0.75
    """MMR relevance/diversity tradeoff used during retrieval diversification."""

    rrf_search_mode: str = "rrf_hybrid"
    """Default retrieval search mode.

    Supported values: rrf_hybrid, semantic_only, bm25_only.
    """

    # Chat Configuration
    max_message_length: int = 2000
    """Maximum message length in characters.

    Default: 2000 (roughly 500 tokens, safe for most models)
    Increase for complex queries, decrease for faster responses.
    Messages exceeding this length will be truncated.

    Environment variable: MAX_MESSAGE_LENGTH
    """

    # API Configuration
    api_keys: Optional[str] = None
    """Comma-separated list of valid API keys for client authentication.

    Default: None (authentication disabled)
    Format: "key1,key2,key3"
    When set, clients must provide X-API-Key header matching one of these values.

    Environment variable: API_KEYS
    """

    api_keys_json: Optional[str] = None
    """Optional JSON array of API key records.

    Each item may contain: id, key or hash, owner, role, status.
    """

    rate_limit_per_minute: int = 60
    """Maximum number of requests allowed per minute per client.

    Default: 60 (1 per second)
    Applied based on client IP address. Set to 0 to disable rate limiting.

    Environment variable: RATE_LIMIT_PER_MINUTE
    """

    anonymous_chat_rate_limit_per_minute: int = 12
    """Maximum anonymous `/chat` requests allowed per minute per browser + IP pair.

    Default: 12
    This tighter quota applies only when API key authentication is disabled or
    a request is otherwise unauthenticated.

    Environment variable: ANONYMOUS_CHAT_RATE_LIMIT_PER_MINUTE
    """

    rate_limit_bypass_key_ids: str = ""
    """Comma-separated authenticated key IDs exempt from application rate limiting.

    Default: "" (no bypass)
    Use this for trusted internal/admin callers that should bypass request quotas.

    Environment variable: RATE_LIMIT_BYPASS_KEY_IDS
    """

    rate_limit_bypass_roles: str = ""
    """Comma-separated API key roles exempt from application rate limiting.

    Default: "" (no bypass)
    Roles are sourced from API key records in `API_KEYS_JSON`.

    Environment variable: RATE_LIMIT_BYPASS_ROLES
    """

    anonymous_browser_cookie_name: str = "anon_browser_id"
    """Cookie name used to persist an anonymous browser identifier.

    Environment variable: ANONYMOUS_BROWSER_COOKIE_NAME
    """

    chat_session_cookie_name: str = "chat_session_id"
    """Cookie name used for the server-issued anonymous chat session.

    Environment variable: CHAT_SESSION_COOKIE_NAME
    """

    chat_session_cookie_max_age_seconds: int = 60 * 60 * 24 * 30
    """Lifetime of the anonymous chat session cookie in seconds.

    Default: 30 days

    Environment variable: CHAT_SESSION_COOKIE_MAX_AGE_SECONDS
    """

    chat_history_ttl_seconds: int = 60 * 60 * 24 * 30
    """Retention window for file-backed anonymous chat history in seconds.

    Default: 30 days

    Environment variable: CHAT_HISTORY_TTL_SECONDS
    """

    trust_proxy_headers: bool = False
    """Whether to trust forwarding headers for client IP resolution.

    Default: False
    Enable this only when the app is behind a trusted reverse proxy/load balancer
    that correctly sets `X-Forwarded-For` or `X-Real-IP`.

    Environment variable: TRUST_PROXY_HEADERS
    """

    # Retry Configuration
    max_retries: int = 3
    """Maximum number of retry attempts for failed LLM API calls.

    Default: 3
    Uses exponential backoff strategy. Set to 0 to disable retries.

    Environment variable: MAX_RETRIES
    """

    retry_delay: float = 1.0
    """Initial retry delay in seconds before exponential backoff.

    Default: 1.0
    Actual delay = retry_delay * (2 ^ attempt_number)
    Example: 1.0s, 2.0s, 4.0s for max_retries=3

    Environment variable: RETRY_DELAY
    """

    # HyDE Configuration
    hyde_enabled: bool = False
    """Enable HyDE (Hypothetical Document Embeddings) query expansion.

    Default: False
    When enabled, generates hypothetical answers to improve retrieval quality.

    Environment variable: HYDE_ENABLED
    """

    hyde_max_length: int = 200
    """Maximum word count for HyDE hypothetical answers.

    Default: 200
    Range: 50-500

    Environment variable: HYDE_MAX_LENGTH
    """

    hype_enabled: bool = False
    """Enable HyPE (Hypothetical Prompt Embedding) at ingestion time.

    Generates hypothetical questions for a sample of chunks, stored in metadata
    for zero-LLM-cost query expansion at retrieval time.

    Default: False
    Environment variable: HYPE_ENABLED
    """

    hype_sample_rate: float = 0.1
    """Fraction of chunks to sample for HyPE generation (0.0-1.0).

    Weighted by quality_score — higher quality chunks have higher selection probability.

    Default: 0.1 (10%%)
    Environment variable: HYPE_SAMPLE_RATE
    """

    hype_max_chunks: int = 500
    """Maximum number of chunks to generate HyPE questions for per ingestion.

    Default: 500
    Environment variable: HYPE_MAX_CHUNKS
    """

    hype_questions_per_chunk: int = 2
    """Number of hypothetical questions to generate per chunk (1-2).

    Default: 2
    Environment variable: HYPE_QUESTIONS_PER_CHUNK
    """

    # LLM Keyword Extraction & Chunk Summarization
    enable_keyword_extraction: bool = False
    """Enable LLM-based medical entity keyword extraction at ingestion time.

    Default: False
    When enabled, extracts 5-10 medical entities (conditions, drugs, procedures,
    specialties) from each chunk and stores them in metadata for BM25 indexing
    and query-time keyword boosting.

    Environment variable: ENABLE_KEYWORD_EXTRACTION
    """

    enable_chunk_summaries: bool = False
    """Enable LLM-based chunk summarization at ingestion time.

    Default: False
    When enabled, generates a 1-2 sentence summary for each chunk and prepends
    it to the chunk content before embedding, improving semantic match for
    overview queries.

    Environment variable: ENABLE_CHUNK_SUMMARIES
    """

    keyword_extraction_sample_rate: float = 1.0
    """Fraction of chunks to process for keyword extraction (0.0-1.0).

    Weighted by quality_score — higher quality chunks are prioritized.

    Default: 1.0 (process all chunks)
    Environment variable: KEYWORD_EXTRACTION_SAMPLE_RATE
    """

    keyword_extraction_max_chunks: int = 500
    """Maximum number of chunks to process for keyword extraction per ingestion.

    Default: 500
    Environment variable: KEYWORD_EXTRACTION_MAX_CHUNKS
    """

    # Retrieval Configuration
    medical_expansion_enabled: bool = False
    """Enable provider-backed medical query expansion during retrieval.

    Default: False
    This seam is independent of HyDE/HyPE and is safe to leave disabled until
    a real ontology-backed provider is configured.

    Environment variable: MEDICAL_EXPANSION_ENABLED
    """

    medical_expansion_provider: str = "noop"
    """Medical expansion provider name.

    Default: "noop"
    Supported values currently: noop

    Environment variable: MEDICAL_EXPANSION_PROVIDER
    """

    # Reranking Configuration
    reranker_model: str = "BAAI/bge-reranker-base"
    """Cross-encoder model for reranking retrieval results.

    Default: "BAAI/bge-reranker-base"
    Alternatives: "BAAI/bge-reranker-large", "cross-encoder/ms-marco-MiniLM-L-6-v2"

    Environment variable: RERANKER_MODEL
    """

    reranker_batch_size: int = 16
    """Batch size for cross-encoder inference.

    Default: 16
    Range: 8-32. Larger batches are faster but use more memory.

    Environment variable: RERANKER_BATCH_SIZE
    """

    reranker_device: str = "cpu"
    """Device for cross-encoder model inference.

    Default: "cpu"
    Options: "cpu", "cuda"

    Environment variable: RERANKER_DEVICE
    """

    enable_reranking: bool = False
    """Enable cross-encoder reranking during retrieval.

    Default: False
    When enabled, reranks top-k candidates from the hybrid retriever.

    Environment variable: ENABLE_RERANKING
    """

    rerank_top_k: int | None = None
    """Number of candidates to fetch before reranking (None = auto).

    Default: None (automatically set to top_k * overfetch_multiplier)
    Set explicitly to override the automatic calculation.

    Environment variable: RERANK_TOP_K
    """

    rerank_score_threshold: float | None = None
    """Optional minimum cross-encoder score required after reranking.

    Default: None (no threshold)
    When set, candidates scoring below the threshold are dropped before
    diversification and context assembly.

    Environment variable: RERANK_SCORE_THRESHOLD
    """

    reranking_mode: str = "cross_encoder"
    """Reranking strategy to use.

    Options: cross_encoder, mmr, both
    - cross_encoder: Use cross-encoder reranking only
    - mmr: Use MMR diversification only (current default behavior)
    - both: Apply cross-encoder first, then MMR diversification

    Default: cross_encoder

    Environment variable: RERANKING_MODE
    """

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() in {"development", "dev", "local", "test"}

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def rate_limit_bypass_key_id_set(self) -> set[str]:
        return {value.strip() for value in self.rate_limit_bypass_key_ids.split(",") if value.strip()}

    @property
    def rate_limit_bypass_role_set(self) -> set[str]:
        return {value.strip() for value in self.rate_limit_bypass_roles.split(",") if value.strip()}

    @property
    def vector_dir(self) -> str:
        """Backward-compatible alias for the persisted vector storage path."""
        return self.chroma_persist_directory


settings = Settings()

if settings.wandb_api_key and not os.environ.get("WANDB_API_KEY"):
    os.environ["WANDB_API_KEY"] = settings.wandb_api_key
