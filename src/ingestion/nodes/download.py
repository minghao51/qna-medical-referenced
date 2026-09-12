"""Hamilton components for data ingestion pipeline.

Bronze layer: raw immutable downloads written flat into DATA_RAW_DIR (data/raw).

Each node both performs its download/conversion side effect and returns the
glob of files it is responsible for, so downstream nodes order after the writes.
``skip_download`` suppresses the side effect while keeping the glob, which is
how ``--skip-download`` reuses an existing raw corpus.
"""

from __future__ import annotations

import logging

from src.config import DATA_RAW_DIR
from src.ingestion.steps._utils import run_async

logger = logging.getLogger(__name__)


def download_web_content(skip_download: bool) -> list[str]:
    from src.ingestion.steps.download_web import main as download_main

    if not skip_download:
        run_async(download_main())
    return sorted(str(f) for f in DATA_RAW_DIR.glob("*.html"))


def convert_html_to_markdown(
    download_web_content: list[str],
    force_html_convert: bool,
    skip_download: bool,
) -> list[str]:
    """Convert downloaded HTML to Markdown.

    Takes ``download_web_content`` for ordering only (its value is the pre-
    conversion html glob): the converter globs ``*.html`` itself, but must not
    run until downloads have finished writing them.

    Conversion runs when downloads run (``skip_download=False``) or when
    ``force_html_convert`` explicitly requests re-conversion — the path
    ``run_ingestion(force_html_convert=True)`` uses to re-materialize
    markdown without re-downloading.
    """
    from src.ingestion.steps.convert_html import main as convert_main

    if not skip_download or force_html_convert:
        convert_main(force=force_html_convert)
    return sorted(str(f) for f in DATA_RAW_DIR.glob("*.md"))


def download_pdf_files(skip_download: bool) -> list[str]:
    from src.ingestion.steps.download_pdfs import main as download_pdfs_main

    if not skip_download:
        run_async(download_pdfs_main())
    return sorted(str(f) for f in DATA_RAW_DIR.glob("*.pdf"))
