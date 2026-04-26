"""Application configuration loaded from YAML + environment variables.

This module provides a centralized settings object that combines:
- YAML configuration from config/settings.yaml
- Environment variable overrides (with prefix APP__)
- Secrets from .env (via dotenvx)

The YAML config is the source of truth for default values. Environment
variables take precedence for overrides and sensitive values.
"""

import os
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field, model_validator
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
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000"
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
    dashscope_api_key: str = ""
    qwen_base_url: str = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v4"
    embedding_batch_size: int = 10
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemma-4-31b-it"
    litellm_model: str = ""
    judge_model_light: str = "qwen3.5-35b-a3b"
    judge_model_heavy: str = "qwen3.5-flash"
    judge_model_light_litellm: str = "google/gemma-4-31b-it"
    judge_model_heavy_litellm: str = "google/gemma-4-31b-it"
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
    hyde_enabled: bool = False
    hyde_max_length: int = 200
    hype_enabled: bool = False
    hype_sample_rate: float = 0.1
    hype_max_chunks: int = 500
    hype_questions_per_chunk: int = 2


class EnrichmentConfig(BaseModel):
    enable_keyword_extraction: bool = False
    enable_chunk_summaries: bool = False
    keyword_extraction_sample_rate: float = 1.0
    keyword_extraction_max_chunks: int = 500


class RetryConfig(BaseModel):
    max_retries: int = 3
    retry_delay: float = 1.0


class DeepEvalConfig(BaseModel):
    judge_model_light: str = "qwen3.5-35b-a3b"
    judge_model_heavy: str = "qwen3.5-flash"
    judge_model_light_litellm: str = "google/gemma-4-31b-it"
    judge_model_heavy_litellm: str = "google/gemma-4-31b-it"
    deepeval_query_concurrency: int = 2
    deepeval_metric_concurrency: int = 3
    deepeval_metric_timeout_seconds: int = 90
    deepeval_answer_cache_enabled: bool = True
    deepeval_metric_cache_enabled: bool = True
    deepeval_cache_dir: str = "data/evals/cache"
    deepeval_cache_schema_version: int = 2
    deepeval_faithfulness_truths_limit: int = 8


class WandbConfig(BaseModel):
    wandb_api_key: str = ""
    wandb_cache_ttl_seconds: int = 60


class ProductionConfig(BaseModel):
    production_profile: str | None = "baseline_cross_encoder"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_prefix="APP__",
        env_nested_delimiter="__",
    )

    _LEGACY_FIELD_MAP: ClassVar[dict[str, tuple[str, str]]] = {
        "app_environment": ("app", "environment"),
        "log_level": ("app", "log_level"),
        "max_message_length": ("api", "max_message_length"),
        "api_keys": ("api", "api_keys"),
        "api_keys_json": ("api", "api_keys_json"),
        "rate_limit_per_minute": ("api", "rate_limit_per_minute"),
        "anonymous_chat_rate_limit_per_minute": ("api", "anonymous_chat_rate_limit_per_minute"),
        "rate_limit_bypass_key_ids": ("api", "rate_limit_bypass_key_ids"),
        "rate_limit_bypass_roles": ("api", "rate_limit_bypass_roles"),
        "anonymous_browser_cookie_name": ("api", "anonymous_browser_cookie_name"),
        "chat_session_cookie_name": ("api", "chat_session_cookie_name"),
        "chat_session_cookie_max_age_seconds": ("api", "chat_session_cookie_max_age_seconds"),
        "chat_history_ttl_seconds": ("api", "chat_history_ttl_seconds"),
        "chat_history_max_messages_per_session": ("api", "chat_history_max_messages_per_session"),
        "trust_proxy_headers": ("api", "trust_proxy_headers"),
        "llm_provider": ("llm", "provider"),
        "model_name": ("llm", "model_name"),
        "dashscope_api_key": ("llm", "dashscope_api_key"),
        "qwen_base_url": ("llm", "qwen_base_url"),
        "embedding_model": ("llm", "embedding_model"),
        "embedding_batch_size": ("llm", "embedding_batch_size"),
        "openrouter_api_key": ("llm", "openrouter_api_key"),
        "openrouter_model": ("llm", "openrouter_model"),
        "litellm_model": ("llm", "litellm_model"),
        "judge_model_light": ("llm", "judge_model_light"),
        "judge_model_heavy": ("llm", "judge_model_heavy"),
        "judge_model_light_litellm": ("llm", "judge_model_light_litellm"),
        "judge_model_heavy_litellm": ("llm", "judge_model_heavy_litellm"),
        "judge_temperature": ("llm", "judge_temperature"),
        "judge_max_tokens": ("llm", "judge_max_tokens"),
        "collection_name": ("storage", "collection_name"),
        "data_dir": ("storage", "data_dir"),
        "chroma_persist_directory": ("storage", "chroma_persist_directory"),
        "chroma_server_host": ("storage", "chroma_server_host"),
        "chroma_server_port": ("storage", "chroma_server_port"),
        "retrieval_overfetch_multiplier": ("retrieval", "retrieval_overfetch_multiplier"),
        "max_chunks_per_source_page": ("retrieval", "max_chunks_per_source_page"),
        "max_chunks_per_source": ("retrieval", "max_chunks_per_source"),
        "mmr_lambda": ("retrieval", "mmr_lambda"),
        "rrf_search_mode": ("retrieval", "rrf_search_mode"),
        "enable_reranking": ("retrieval", "enable_reranking"),
        "reranker_model": ("retrieval", "reranker_model"),
        "reranker_batch_size": ("retrieval", "reranker_batch_size"),
        "reranker_device": ("retrieval", "reranker_device"),
        "rerank_top_k": ("retrieval", "rerank_top_k"),
        "rerank_score_threshold": ("retrieval", "rerank_score_threshold"),
        "reranking_mode": ("retrieval", "reranking_mode"),
        "medical_expansion_enabled": ("retrieval", "medical_expansion_enabled"),
        "medical_expansion_provider": ("retrieval", "medical_expansion_provider"),
        "hyde_enabled": ("hyde", "hyde_enabled"),
        "hyde_max_length": ("hyde", "hyde_max_length"),
        "hype_enabled": ("hyde", "hype_enabled"),
        "hype_sample_rate": ("hyde", "hype_sample_rate"),
        "hype_max_chunks": ("hyde", "hype_max_chunks"),
        "hype_questions_per_chunk": ("hyde", "hype_questions_per_chunk"),
        "enable_keyword_extraction": ("enrichment", "enable_keyword_extraction"),
        "enable_chunk_summaries": ("enrichment", "enable_chunk_summaries"),
        "keyword_extraction_sample_rate": ("enrichment", "keyword_extraction_sample_rate"),
        "keyword_extraction_max_chunks": ("enrichment", "keyword_extraction_max_chunks"),
        "max_retries": ("retry", "max_retries"),
        "retry_delay": ("retry", "retry_delay"),
        "deepeval_query_concurrency": ("deepeval", "deepeval_query_concurrency"),
        "deepeval_metric_concurrency": ("deepeval", "deepeval_metric_concurrency"),
        "deepeval_metric_timeout_seconds": ("deepeval", "deepeval_metric_timeout_seconds"),
        "deepeval_answer_cache_enabled": ("deepeval", "deepeval_answer_cache_enabled"),
        "deepeval_metric_cache_enabled": ("deepeval", "deepeval_metric_cache_enabled"),
        "deepeval_cache_dir": ("deepeval", "deepeval_cache_dir"),
        "deepeval_cache_schema_version": ("deepeval", "deepeval_cache_schema_version"),
        "deepeval_faithfulness_truths_limit": ("deepeval", "deepeval_faithfulness_truths_limit"),
        "wandb_api_key": ("wandb", "wandb_api_key"),
        "wandb_cache_ttl_seconds": ("wandb", "wandb_cache_ttl_seconds"),
        "production_profile": ("production", "production_profile"),
    }

    app: AppConfig = Field(default_factory=AppConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    hyde: HyDEConfig = Field(default_factory=HyDEConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    deepeval: DeepEvalConfig = Field(default_factory=DeepEvalConfig)
    wandb: WandbConfig = Field(default_factory=WandbConfig)
    production: ProductionConfig = Field(default_factory=ProductionConfig)

    @classmethod
    def _coerce_legacy_flat_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        migrated = dict(data)
        for legacy_name, (section_name, field_name) in cls._LEGACY_FIELD_MAP.items():
            if legacy_name not in migrated:
                continue
            value = migrated.pop(legacy_name)
            section_payload = migrated.get(section_name)
            if not isinstance(section_payload, dict):
                section_payload = {}
            section_payload.setdefault(field_name, value)
            migrated[section_name] = section_payload
        return migrated

    def __init__(self, **values):
        super().__init__(**self._coerce_legacy_flat_fields(values))

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_flat_fields(cls, data: object) -> object:
        return cls._coerce_legacy_flat_fields(data)

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


settings = Settings()


if settings.wandb.wandb_api_key and not os.environ.get("WANDB_API_KEY"):
    os.environ["WANDB_API_KEY"] = settings.wandb.wandb_api_key
