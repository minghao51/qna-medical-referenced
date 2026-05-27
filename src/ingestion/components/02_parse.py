"""Hamilton components for data ingestion pipeline.

Bronze→Silver: parsing raw documents into structured format.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def silver_data_path(project_root: Path) -> str:
    return str(project_root / "data" / "02_silver")


def silver_documents_dir(silver_data_path: str) -> str:
    return str(Path(silver_data_path) / "documents")


def silver_chunks_dir(silver_data_path: str) -> str:
    return str(Path(silver_data_path) / "chunks")


def parse_pdf_document(pdf_path: str) -> dict[str, Any]:
    from src.ingestion.steps.load_pdfs import PDFLoader

    loader = PDFLoader()
    result = loader.load_pdf(pdf_path)
    return {"path": pdf_path, "text": result, "source_type": "pdf"}


def all_pdf_documents(
    all_pdf_downloads: list[str],
) -> list[dict[str, Any]]:
    from src.ingestion.schemas.bronze_models import DownloadedFileBronze

    results = []
    for pdf_path in all_pdf_downloads:
        try:
            result = parse_pdf_document(pdf_path)
            DownloadedFileBronze(
                url=result.get("path", ""),
                local_path=result.get("path", ""),
                file_type="pdf",
                download_status="parsed",
            )
            results.append(result)
        except Exception as e:
            logger.warning("Failed to parse PDF %s: %s", pdf_path, e)
    return results


def all_markdown_documents(
    all_web_downloads: list[str],
) -> list[dict[str, Any]]:
    from src.ingestion.schemas.bronze_models import DownloadedFileBronze
    from src.ingestion.steps.load_markdown import get_markdown_documents

    docs = get_markdown_documents()
    results = []
    for d in docs:
        result = {
            "path": d.get("source", ""),
            "text": d.get("extracted_text", ""),
            "source_type": "markdown",
        }
        try:
            DownloadedFileBronze(
                url=result["path"],
                local_path=result["path"],
                file_type="html",
                download_status="parsed",
            )
        except Exception as e:
            logger.warning("Bronze validation failed for %s: %s", result["path"], e)
        results.append(result)
    return results


def silver_documents_parquet_path(
    silver_documents_dir: str,
    source_type: str,
) -> str:
    return str(Path(silver_documents_dir) / f"{source_type}_documents.parquet")


def write_silver_documents(
    all_pdf_documents: list[dict[str, Any]],
    all_markdown_documents: list[dict[str, Any]],
    silver_documents_dir: str,
) -> dict[str, Any]:
    import polars as pl

    from src.ingestion.schemas.silver_models import ExtractedDocumentSilver, SourceMetadataSilver

    Path(silver_documents_dir).mkdir(parents=True, exist_ok=True)

    pdf_df = pl.DataFrame(all_pdf_documents)
    md_df = pl.DataFrame(all_markdown_documents)

    pdf_path = Path(silver_documents_dir) / "pdf_documents.parquet"
    md_path = Path(silver_documents_dir) / "markdown_documents.parquet"

    if len(pdf_df) > 0:
        pdf_df.write_parquet(pdf_path)
    if len(md_df) > 0:
        md_df.write_parquet(md_path)

    for doc in all_pdf_documents:
        try:
            ExtractedDocumentSilver(
                id=str(Path(doc.get("path", "")).stem),
                source=doc.get("path", ""),
                source_type="pdf",
                extracted_text=doc.get("text", ""),
                metadata=SourceMetadataSilver(
                    source_type="pdf",
                    source_class="document",
                    canonical_label="parsed_pdf",
                ),
            )
        except Exception as e:
            logger.warning("Silver validation failed for PDF %s: %s", doc.get("path"), e)

    for doc in all_markdown_documents:
        try:
            ExtractedDocumentSilver(
                id=str(Path(doc.get("path", "")).stem),
                source=doc.get("path", ""),
                source_type="markdown",
                extracted_text=doc.get("text", ""),
                metadata=SourceMetadataSilver(
                    source_type="markdown",
                    source_class="document",
                    canonical_label="parsed_markdown",
                ),
            )
        except Exception as e:
            logger.warning("Silver validation failed for MD %s: %s", doc.get("path"), e)

    return {
        "pdf_count": len(pdf_df),
        "markdown_count": len(md_df),
        "pdf_path": str(pdf_path),
        "markdown_path": str(md_path),
    }
