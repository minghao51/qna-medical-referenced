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
    dashscope_api_key: str = ""
    """Alibaba Dashscope API key for Qwen models.

    Required for all LLM operations. Obtain from:
    https://dashscope-intl.aliyuncs.com/

    Environment variable: DASHSCOPE_API_KEY
    """

    model_name: str = "qwen3.5-flash"
    """Qwen model to use for text generation.

    Default: "qwen3.5-flash" (fast, cost-effective)
    Alternatives: "qwen3.5-plus", "qwen-plus", "qwen-max"

    Environment variable: MODEL_NAME
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

    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    """Qwen API base URL (OpenAI compatible).

    Default: Singapore region (https://dashscope-intl.aliyuncs.com/compatible-mode/v1)

    Environment variable: QWEN_BASE_URL
    """

    # LLM-as-a-Judge Configuration
    judge_model_light: str = "qwen3.5-35b-a3b"
    """Lightweight model for simple classification tasks (3B active params)."""

    judge_model_heavy: str = "qwen3.5-flash"
    """Heavyweight model for complex Chain-of-Thought reasoning."""

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

    data_dir: str = "data/raw"
    """Directory for raw downloaded documents.

    Default: "data/raw"
    Contains downloaded HTML/PDF files before processing.

    Environment variable: DATA_DIR
    """

    vector_dir: str = "data/vectors"
    """Directory for persistent ChromaDB vector storage.

    Default: "data/vectors"
    Contains the vector index and metadata. Must be preserved between runs.

    Environment variable: VECTOR_DIR
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

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() in {"development", "dev", "local", "test"}

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()

if settings.wandb_api_key and not os.environ.get("WANDB_API_KEY"):
    os.environ["WANDB_API_KEY"] = settings.wandb_api_key
