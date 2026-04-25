"""Ingestion schemas for medallion layer validation.

Bronze -> Silver -> Gold -> Platinum
"""

from src.ingestion.schemas.bronze_models import (
    DownloadedFileBronze,
    PageMetadata,
    RawPDFSource,
    SourceArtifactBronze,
    StructuredBlockData,
)
from src.ingestion.schemas.gold_models import (
    EmbeddingRecordGold,
    EnrichedChunkGold,
    ReferenceDataGold,
)
from src.ingestion.schemas.silver_models import (
    ChunkRecordSilver,
    ExtractedDocumentSilver,
    PageSilver,
    SourceMetadataSilver,
)

__all__ = [
    "ChunkRecordSilver",
    "DownloadedFileBronze",
    "EmbeddingRecordGold",
    "EnrichedChunkGold",
    "ExtractedDocumentSilver",
    "PageMetadata",
    "PageSilver",
    "RawPDFSource",
    "ReferenceDataGold",
    "SourceArtifactBronze",
    "SourceMetadataSilver",
    "StructuredBlockData",
]
