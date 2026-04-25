"""Hamilton components for data ingestion pipeline.

Bronze layer: raw immutable downloads.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def bronze_data_path(project_root: Path) -> str:
    return str(project_root / "data" / "01_bronze")


def downloads_dir(bronze_data_path: str) -> str:
    return str(Path(bronze_data_path) / "downloads")


def raw_pdfs_dir(downloads_dir: str) -> str:
    return str(Path(downloads_dir) / "pdf")


def raw_html_dir(downloads_dir: str) -> str:
    return str(Path(downloads_dir) / "html")


def raw_markdown_dir(downloads_dir: str) -> str:
    return str(Path(downloads_dir) / "markdown")


def artifacts_dir(bronze_data_path: str) -> str:
    return str(Path(bronze_data_path) / "artifacts")


def download_web_content(
    downloads_dir: str,
    data_path: str = "data/raw",
) -> list[str]:
    from src.ingestion.steps.download_web import main as download_main

    Path(downloads_dir).mkdir(parents=True, exist_ok=True)
    asyncio.run(download_main())
    return [str(f) for f in Path(downloads_dir).glob("*.html")]


def download_pdf_files(
    raw_pdfs_dir: str,
    data_path: str = "data/raw",
) -> list[str]:
    from src.ingestion.steps.download_pdfs import main as download_pdfs_main

    Path(raw_pdfs_dir).mkdir(parents=True, exist_ok=True)
    asyncio.run(download_pdfs_main())
    return [str(f) for f in Path(raw_pdfs_dir).glob("*.pdf")]


def all_web_downloads(raw_html_dir: str) -> list[str]:
    files = list(Path(raw_html_dir).glob("*.html"))
    return [str(f) for f in files]


def all_pdf_downloads(raw_pdfs_dir: str) -> list[str]:
    files = list(Path(raw_pdfs_dir).glob("*.pdf"))
    return [str(f) for f in files]
