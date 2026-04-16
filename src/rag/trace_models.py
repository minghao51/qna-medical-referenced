"""Data models for the health screening interpreter chatbot."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatSource(BaseModel):
    """Structured citation returned with chat responses."""

    canonical_label: str
    display_label: str
    source_url: Optional[str] = None
    source_type: str = "other"
    source_class: str = "unknown"
    domain: Optional[str] = None
    domain_type: str = "unknown"
    label: str
    source: str
    url: Optional[str] = None
    page: Optional[int] = None
    content_type: Optional[str] = None


class RetrievedDocument(BaseModel):
    """A retrieved document with individual scores."""

    id: str
    content: str
    source: str
    page: Optional[int] = None
    semantic_score: float
    keyword_score: float
    source_prior: float
    source_boost: Optional[float] = None
    combined_score: float
    rank: int
    semantic_rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    fused_rank: Optional[int] = None
    fused_score: Optional[float] = None
    chunk_quality_score: Optional[float] = None
    content_type: Optional[str] = None
    section_path: list[str] = Field(default_factory=list)
    canonical_label: Optional[str] = None
    display_label: Optional[str] = None
    logical_name: Optional[str] = None
    source_url: Optional[str] = None
    source_type: Optional[str] = None
    source_class: Optional[str] = None
    domain: Optional[str] = None
    domain_type: Optional[str] = None


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
    tokens_estimate: Optional[int] = None


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
    pipeline: Optional[PipelineTrace] = None
