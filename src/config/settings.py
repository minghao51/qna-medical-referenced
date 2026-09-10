"""Application configuration loaded from YAML + environment variables.

This module provides a centralized settings object that combines:
- YAML configuration from config/settings.yaml
- Environment variable overrides (with APP__ prefix and __ nested delimiter)
- Secrets from .env (via dotenvx, using APP__LLM__* keys)

Priority order (first wins):
1. Init args
2. Env vars (APP__LLM__MODEL_NAME)
3. .env file (dotenvx decrypted, APP__* keys)
4. YAML defaults (config/settings.yaml)
"""

import functools
import warnings
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class AppConfig(BaseModel):
    environment: str = "development"
    log_level: str = "INFO"


class ApiConfig(BaseModel):
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://localhost:4173,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:3000,http://127.0.0.1:4173"
    max_message_length: int = 2000
    api_keys: str | None = None
    api_keys_json: str | None = None
    rate_limit_per_minute: int = 60
    anonymous_chat_rate_limit_per_minute: int = 12
    rate_limit_bypass_key_ids: str = ""
    rate_limit_bypass_roles: str = ""
    anonymous_browser_cookie_name: str = "anon_browser_id"
    chat_session_cookie_name: str = "chat_session_id"
    chat_session_cookie_max_age_seconds: int = 2592000
    chat_history_ttl_seconds: int = 2592000
    chat_history_max_messages_per_session: int = 100
    trust_proxy_headers: bool = False


class LLMConfig(BaseModel):
    provider: str = "qwen"
    model_name: str = "qwen3.5-flash"
    dashscope_api_key: SecretStr = SecretStr("")
    qwen_base_url: str = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v4"
    embedding_batch_size: int = 10
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = "google/gemma-4-31b-it"
    litellm_model: str = ""
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model_name: str = "gemma-4-31b-it"
    judge_model_light: str = "qwen3.5-35b-a3b"
    judge_model_heavy: str = "qwen3.5-flash"
    judge_model_light_litellm: str = "google/gemma-4-31b-it"
    judge_model_heavy_litellm: str = "google/gemma-4-31b-it"
    judge_model_light_gemini: str = "gemma-4-31b-it"
    judge_model_heavy_gemini: str = "gemma-4-31b-it"
    judge_temperature: float = 0.0
    judge_max_tokens: int = 1024


class StorageConfig(BaseModel):
    collection_name: str = "medical_docs"
    data_dir: str = "data/raw"
    chroma_persist_directory: str = "data/chroma"
    chroma_server_host: str = ""
    chroma_server_port: int = 8000


class RetrievalConfig(BaseModel):
    retrieval_overfetch_multiplier: int = 4
    max_chunks_per_source_page: int = 2
    max_chunks_per_source: int = 3
    mmr_lambda: float = 0.75
    rrf_search_mode: str = "rrf_hybrid"
    enable_reranking: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_batch_size: int = 16
    reranker_device: str = "cpu"
    rerank_top_k: int | None = None
    rerank_score_threshold: float | None = None
    reranking_mode: str = "cross_encoder"
    medical_expansion_enabled: bool = False
    medical_expansion_provider: str = "noop"


class HyDEConfig(BaseModel):
    """Query-time HyDE settings (hypothetical document expansion).

    The index-time HyPE fields formerly lived here. They moved to
    ``HypeConfig`` (``settings.hype``) in Phase 3 (roadmap P3.6). The old
    ``hyde.hype_*`` keys still load -- ``Settings.model_post_init`` warns
    and migrates them onto ``settings.hype``.
    """

    hyde_enabled: bool = False
    hyde_max_length: int = 200

    # Deprecated load-compat aliases (roadmap P3.6).
    hype_enabled: bool = False
    hype_sample_rate: float = 0.1
    hype_max_chunks: int = 500
    hype_questions_per_chunk: int = 2


class HypeConfig(BaseModel):
    """Index-time HyPE settings (hypothetical questions at ingestion)."""

    enabled: bool = False
    sample_rate: float = 0.1
    max_chunks: int = 500
    questions_per_chunk: int = 2


class EnrichmentConfig(BaseModel):
    enable_keyword_extraction: bool = False
    enable_chunk_summaries: bool = False
    keyword_extraction_sample_rate: float = 1.0
    keyword_extraction_max_chunks: int = 500


class IngestionConfig(BaseModel):
    structured_chunking_enabled: bool = True
    auto_select_strategy: bool = False
    pdf_extractor_strategy: str = "pypdf_pdfplumber"
    pdf_table_extractor: str = "heuristic"
    index_only_classified_pages: bool = True
    html_extractor_strategy: str = "trafilatura_bs"
    html_extractor_mode: str = "auto"
    page_classification_enabled: bool = True


class RetryConfig(BaseModel):
    max_retries: int = 3
    retry_delay: float = 1.0


class DeepEvalConfig(BaseModel):
    deepeval_query_concurrency: int = 2
    deepeval_metric_concurrency: int = 3
    deepeval_metric_timeout_seconds: int = 90
    deepeval_answer_cache_enabled: bool = True
    deepeval_metric_cache_enabled: bool = True
    deepeval_cache_dir: str = "data/evals/cache"
    deepeval_cache_schema_version: int = 2
    deepeval_faithfulness_truths_limit: int = 8


class WandbConfig(BaseModel):
    wandb_api_key: SecretStr = SecretStr("")
    wandb_cache_ttl_seconds: int = 60


class ProductionConfig(BaseModel):
    production_profile: str | None = "baseline_cross_encoder"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_prefix="APP__",
        env_nested_delimiter="__",
    )

    app: AppConfig = Field(default_factory=AppConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    hyde: HyDEConfig = Field(default_factory=HyDEConfig)
    hype: HypeConfig = Field(default_factory=HypeConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    deepeval: DeepEvalConfig = Field(default_factory=DeepEvalConfig)
    wandb: WandbConfig = Field(default_factory=WandbConfig)
    production: ProductionConfig = Field(default_factory=ProductionConfig)

    # Mapping of deprecated hyde.hype_* fields -> settings.hype fields (P3.6).
    _HYPE_MIGRATION: ClassVar[dict[str, str]] = {
        "hype_enabled": "enabled",
        "hype_sample_rate": "sample_rate",
        "hype_max_chunks": "max_chunks",
        "hype_questions_per_chunk": "questions_per_chunk",
    }

    def model_post_init(self, __context: Any) -> None:
        deprecated_set = [
            old for old in self._HYPE_MIGRATION if old in self.hyde.model_fields_set
        ]
        if deprecated_set:
            warnings.warn(
                "settings.hyde.hype_* moved to settings.hype.* "
                "(e.g. settings.hype.sample_rate; yaml key 'hype:'); the old "
                "keys are deprecated and will be removed after Phase 3",
                DeprecationWarning,
                stacklevel=2,
            )
            # "Explicitly set" cannot be read off model_fields_set: the
            # shipped settings.yaml defines the whole hype: block, which
            # marks every field as set. Migrate only onto fields still
            # holding their HypeConfig defaults (i.e. not customized via
            # the new keys).
            defaults = HypeConfig()
            updates: dict[str, Any] = {}
            for old in deprecated_set:
                new = self._HYPE_MIGRATION[old]
                if getattr(self.hype, new) == getattr(defaults, new):
                    updates[new] = getattr(self.hyde, old)
            if updates:
                self.hype = self.hype.model_copy(update=updates)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=CONFIG_DIR / "settings.yaml"),
        )

    @property
    def is_development(self) -> bool:
        return self.app.environment.strip().lower() in {"development", "dev", "local", "test"}

    @property
    def vector_dir(self) -> str:
        return self.storage.chroma_persist_directory

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api.cors_allowed_origins.split(",") if o.strip()]

    @property
    def dashscope_api_key_value(self) -> str:
        return self.llm.dashscope_api_key.get_secret_value()

    @property
    def openrouter_api_key_value(self) -> str:
        return self.llm.openrouter_api_key.get_secret_value()

    @property
    def wandb_api_key_value(self) -> str:
        return self.wandb.wandb_api_key.get_secret_value()


@functools.lru_cache(maxsize=1)
def _get_settings() -> Settings:
    return Settings()


class _SettingsProxy:
    def __getattr__(self, name):
        return getattr(_get_settings(), name)

    def __repr__(self):
        return repr(_get_settings())


settings = _SettingsProxy()
