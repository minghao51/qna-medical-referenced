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
    """Rich per-file PDF document (same assembly as ``PDFLoader.load_all_pdfs``).

    Roadmap P3.2: the DAG carries the full document shape (``id``, ``pages``,
    ``structured_blocks``, ``metadata``) through the silver parquet so the
    delegated runtime build indexes exactly what the rag-side builder did.
    """
    from src.ingestion.steps.load_pdfs import PDFLoader

    return PDFLoader().load_pdf_document(Path(pdf_path))


def all_pdf_documents(
    download_pdf_files: list[str],
) -> list[dict[str, Any]]:
    results = []
    for pdf_path in download_pdf_files:
        try:
            results.append(parse_pdf_document(pdf_path))
        except Exception as e:
            logger.warning("Failed to parse PDF %s: %s", pdf_path, e)
    return results


def all_markdown_documents(
    convert_html_to_markdown: list[str],
) -> list[dict[str, Any]]:
    """Markdown documents, passed through with their full rich shape.

    Roadmap P3.2 passthrough: ``id``/``metadata``/``structured_blocks``/
    ``source_type`` flow into the silver parquet so the chunker sees the
    same documents the deleted rag-side builder chunked.
    """
    from src.ingestion.steps.load_markdown import get_markdown_documents

    return get_markdown_documents()


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

    Path(silver_documents_dir).mkdir(parents=True, exist_ok=True)

    pdf_df = pl.DataFrame(all_pdf_documents)
    md_df = pl.DataFrame(all_markdown_documents)

    pdf_path = Path(silver_documents_dir) / "pdf_documents.parquet"
    md_path = Path(silver_documents_dir) / "markdown_documents.parquet"

    if len(pdf_df) > 0:
        pdf_df.write_parquet(pdf_path)
    if len(md_df) > 0:
        md_df.write_parquet(md_path)

    return {
        "pdf_count": len(pdf_df),
        "markdown_count": len(md_df),
        "pdf_path": str(pdf_path),
        "markdown_path": str(md_path),
    }
