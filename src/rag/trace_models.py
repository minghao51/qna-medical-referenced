"""Data models for the health screening interpreter chatbot."""

from typing import Any

from pydantic import BaseModel, Field


class ChatSource(BaseModel):
    """Structured citation returned with chat responses."""

    canonical_label: str
    display_label: str
    source_url: str | None = None
    source_type: str = "other"
    source_class: str = "unknown"
    domain: str | None = None
    domain_type: str = "unknown"
    label: str
    source: str
    url: str | None = None
    page: int | None = None
    content_type: str | None = None


class RetrievedDocument(BaseModel):
    """A retrieved document with individual scores."""

    id: str
    content: str
    source: str
    page: int | None = None
    semantic_score: float
    keyword_score: float
    source_prior: float
    source_boost: float | None = None
    combined_score: float
    rank: int
    semantic_rank: int | None = None
    bm25_rank: int | None = None
    fused_rank: int | None = None
    fused_score: float | None = None
    chunk_quality_score: float | None = None
    content_type: str | None = None
    section_path: list[str] = Field(default_factory=list)
    canonical_label: str | None = None
    display_label: str | None = None
    logical_name: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    source_class: str | None = None
    domain: str | None = None
    domain_type: str | None = None


class RetrievalStep(BaseModel):
    """A single sub-step within the retrieval stage."""

    name: str
    timing_ms: int
    skipped: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class RetrievalStage(BaseModel):
    """Metadata about the retrieval stage."""

    query: str
    query_original_length: int | None = None
    query_truncated: bool = False
    top_k: int
    documents: list[RetrievedDocument]
    score_weights: dict
    timing_ms: int
    steps: list[RetrievalStep] = Field(default_factory=list)


class ContextStage(BaseModel):
    """Metadata about the context assembly stage."""

    total_chunks: int
    total_chars: int
    sources: list[str]
    preview: str


class GenerationStage(BaseModel):
    """Metadata about the LLM generation stage."""

    model: str
    timing_ms: int
    tokens_estimate: int | None = None


class PipelineTrace(BaseModel):
    """Complete pipeline trace from query to response."""

    retrieval: RetrievalStage
    context: ContextStage
    generation: GenerationStage
    total_time_ms: int


class ChatResponseWithPipeline(BaseModel):
    """Chat response with optional pipeline trace."""

    response: str
    sources: list[ChatSource]
    pipeline: PipelineTrace | None = None
