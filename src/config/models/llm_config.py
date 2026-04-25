"""Pydantic models for application configuration sections."""

from pydantic import BaseModel


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
    trust_proxy_headers: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def rate_limit_bypass_key_id_set(self) -> set[str]:
        return {v.strip() for v in self.rate_limit_bypass_key_ids.split(",") if v.strip()}

    @property
    def rate_limit_bypass_role_set(self) -> set[str]:
        return {v.strip() for v in self.rate_limit_bypass_roles.split(",") if v.strip()}


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
