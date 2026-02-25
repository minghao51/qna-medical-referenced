"""Data models for the health screening interpreter chatbot."""
from typing import Optional

from pydantic import BaseModel


class RetrievedDocument(BaseModel):
    """A retrieved document with individual scores."""
    id: str
    content: str
    source: str
    page: Optional[int] = None
    semantic_score: float
    keyword_score: float
    source_boost: float
    combined_score: float
    rank: int


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
    sources: list[str]
    pipeline: Optional[PipelineTrace] = None
