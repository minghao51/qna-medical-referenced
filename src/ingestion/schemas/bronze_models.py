"""Bronze layer: raw immutable source data before any processing."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PageMetadata(BaseModel):
    page: int
    selected_extractor: str | None = None
    primary_char_count: int = 0
    fallback_char_count: int = 0


class RawPDFSource(BaseModel):
    page_count: int
    size_bytes: int
    pdf_extractor_strategy: str
    pdf_table_extractor: str


class StructuredBlockData(BaseModel):
    id: str
    block_type: str
    text: str
    section_path: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class SourceArtifactBronze(BaseModel):
    source_id: str
    source_path: str
    source_type: str
    raw_source: dict = Field(default_factory=dict)
    extracted_text: str = ""
    structured_blocks: list[StructuredBlockData] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class DownloadedFileBronze(BaseModel):
    url: str
    local_path: str
    file_type: str
    size_bytes: int = 0
    download_status: str = "pending"
    error_message: str | None = None
