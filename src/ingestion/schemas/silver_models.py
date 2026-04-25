"""Silver layer: validated, cleaned, deduplicated data ready for chunking."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceMetadataSilver(BaseModel):
    source_type: str
    source_class: str
    canonical_label: str
    domain: str | None = None
    domain_type: str | None = None
    logical_name: str | None = None
    source_url: str | None = None


class PageSilver(BaseModel):
    page: int
    content: str
    extractor: str
    char_count: int
    line_count: int
    confidence: str
    ocr_required: bool = False


class ExtractedDocumentSilver(BaseModel):
    id: str
    source: str
    source_type: str
    extracted_text: str
    structured_blocks: list[dict] = Field(default_factory=list)
    pages: list[PageSilver] = Field(default_factory=list)
    metadata: SourceMetadataSilver


class ChunkRecordSilver(BaseModel):
    id: str
    source: str
    source_type: str
    page: int | None = None
    content: str
    content_type: str
    section_path: list[str] = Field(default_factory=list)
    quality_score: float = 1.0
    metadata: dict = Field(default_factory=dict)
