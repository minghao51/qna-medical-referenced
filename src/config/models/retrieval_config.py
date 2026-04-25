"""Retrieval configuration."""

from pydantic import BaseModel


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
