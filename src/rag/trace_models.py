"""Data models for the health screening interpreter chatbot."""

from typing import Optional

from pydantic import BaseModel, Field


class ChatSource(BaseModel):
    """Structured citation returned with chat responses."""

    label: str
    source: str
    url: Optional[str] = None
    page: Optional[int] = None


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
    logical_name: Optional[str] = None
    source_url: Optional[str] = None


class RetrievalStage(BaseModel):
    """Metadata about the retrieval stage."""

    query: str
    top_k: int
    documents: list[RetrievedDocument]
    score_weights: dict
    timing_ms: int


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
