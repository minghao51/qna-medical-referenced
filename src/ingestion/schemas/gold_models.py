"""Gold layer: enriched features and processed data ready for embedding."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EnrichedChunkGold(BaseModel):
    id: str
    source: str
    source_type: str
    page: int | None = None
    content: str
    content_type: str
    section_path: list[str] = Field(default_factory=list)
    quality_score: float = 1.0
    hypothetical_questions: list[str] = Field(default_factory=list)
    extracted_keywords: list[str] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict = Field(default_factory=dict)


class EmbeddingRecordGold(BaseModel):
    id: str
    chunk_id: str
    embedding: list[float]
    model_name: str
    dimension: int
    created_at: str


class ReferenceDataGold(BaseModel):
    id: str
    source: str
    content: str
    content_type: str
    metadata: dict = Field(default_factory=dict)
