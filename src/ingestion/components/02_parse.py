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
    from src.ingestion.steps.load_markdown import get_markdown_documents

    return [
        {
            "path": d.get("source", ""),
            "text": d.get("content", ""),
            "source_type": "markdown",
        }
        for d in get_markdown_documents()
    ]


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
