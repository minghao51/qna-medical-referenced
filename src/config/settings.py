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

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() in {"development", "dev", "local", "test"}

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()

if settings.wandb_api_key and not os.environ.get("WANDB_API_KEY"):
    os.environ["WANDB_API_KEY"] = settings.wandb_api_key
