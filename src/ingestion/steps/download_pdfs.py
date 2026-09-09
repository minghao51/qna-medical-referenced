#!/usr/bin/env python3
"""
L0b: Download PDF documents from Singapore government health websites.
Saves PDFs to data/raw directory.
Uses existing manifest from download_web.py for tracking.
"""

import asyncio
import hashlib
import logging
from pathlib import Path

from src.config import DATA_RAW_DIR
from src.ingestion.steps._utils import (
    download_with_retry,
    load_sources_config,
    register_manifest_record,
    url_file_path,
)
from src.ingestion.steps.download_web import _load_manifest as _load_web_manifest
from src.ingestion.steps.download_web import _manifest_indexes as _manifest_indexes_web
from src.ingestion.steps.download_web import _manifest_lock
from src.ingestion.steps.download_web import _save_manifest as _save_web_manifest
from src.ingestion.steps.download_web import normalize_url as normalize_url_web

logger = logging.getLogger(__name__)

# Small bound so concurrent PDF downloads do not hammer the source hosts.
_PDF_DOWNLOAD_CONCURRENCY = 4

_PDF_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _get_pdf_sources(group: str) -> list[tuple[str, str]]:
    config = load_sources_config()
    pdf = config.get("pdf_sources", {})
    entries = pdf.get(group, [])
    return [(e["url"], e["name"]) for e in entries if "url" in e and "name" in e]


def normalize_url(url: str) -> str:
    return normalize_url_web(url)


def get_file_path(url: str, extension: str = "pdf") -> Path:
    return url_file_path(url, DATA_RAW_DIR, extension, include_hash_suffix=False)


def _load_manifest() -> dict:
    return _load_web_manifest()


def _save_manifest(manifest: dict) -> None:
    _save_web_manifest(manifest)


def _manifest_indexes(manifest: dict) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    return _manifest_indexes_web(manifest)


def _register_manifest_record(
    *,
    manifest: dict,
    url: str,
    normalized_url: str,
    logical_name: str,
    file_path: Path | None,
    content_hash: str | None,
    status: str,
) -> None:
    register_manifest_record(
        manifest=manifest,
        url=url,
        normalized_url=normalized_url,
        logical_name=logical_name,
        file_path=file_path,
        content_hash=content_hash,
        status=status,
        extra_fields={"record_type": "pdf_download"},
    )


async def download_pdf(url: str, timeout: int = 60, max_retries: int = 3) -> bytes | None:
    """Download PDF content from URL with retry for transient errors."""
    response = await download_with_retry(
        url, timeout=timeout, max_retries=max_retries, headers=_PDF_REQUEST_HEADERS
    )
    if response is None:
        return None
    content_type = response.headers.get("content-type", "")
    looks_like_pdf = response.content.startswith(b"%PDF")
    if "pdf" not in content_type.lower() and not looks_like_pdf:
        logger.warning("Expected PDF but got %s for %s", content_type, url)
        return None
    return bytes(response.content)


async def download_pdf_if_not_exists(url: str, logical_name: str) -> Path | None:
    """Download PDF if it doesn't already exist."""
    normalized_url = normalize_url(url)
    async with _manifest_lock:
        manifest = _load_manifest()
        by_url, _ = _manifest_indexes(manifest)
        prior = by_url.get(normalized_url)
        if prior and prior.get("filename"):
            prior_path = DATA_RAW_DIR / str(prior["filename"])
            if prior_path.exists():
                logger.info("Skipping (manifest exists): %s", logical_name)
                return None

    file_path = get_file_path(url, "pdf")
    if file_path.exists():
        async with _manifest_lock:
            manifest = _load_manifest()
            logger.info("Skipping (file exists): %s", file_path.name)
            _register_manifest_record(
                manifest=manifest,
                url=url,
                normalized_url=normalized_url,
                logical_name=logical_name,
                file_path=file_path,
                content_hash=None,
                status="file_exists",
            )
            _save_manifest(manifest)
        return None

    logger.info("Downloading: %s", logical_name)
    content = await download_pdf(url)
    if not content:
        async with _manifest_lock:
            manifest = _load_manifest()
            _register_manifest_record(
                manifest=manifest,
                url=url,
                normalized_url=normalized_url,
                logical_name=logical_name,
                file_path=None,
                content_hash=None,
                status="download_failed",
            )
            _save_manifest(manifest)
        return None

    content_hash = hashlib.sha256(content).hexdigest()[:16]
    file_path.write_bytes(content)

    async with _manifest_lock:
        manifest = _load_manifest()
        _register_manifest_record(
            manifest=manifest,
            url=url,
            normalized_url=normalized_url,
            logical_name=logical_name,
            file_path=file_path,
            content_hash=content_hash,
            status="downloaded",
        )
        _save_manifest(manifest)
    logger.info("  Saved: %s", file_path.name)
    return file_path


async def download_pdfs_group(sources_group: str) -> list[Path]:
    """Download all configured PDFs for one sources.yaml group concurrently."""
    pdfs = _get_pdf_sources(sources_group)
    semaphore = asyncio.Semaphore(_PDF_DOWNLOAD_CONCURRENCY)

    async def _download_one(url: str, name: str) -> Path | None:
        async with semaphore:
            return await download_pdf_if_not_exists(url, name)

    results = await asyncio.gather(*[_download_one(url, name) for url, name in pdfs])
    return [r for r in results if r]


def list_downloaded_pdfs() -> list[str]:
    """List all downloaded PDF files in data/raw."""
    if not DATA_RAW_DIR.exists():
        return []
    return [str(f) for f in DATA_RAW_DIR.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]


async def main():
    """Main function to download all PDFs."""
    logger.info("=" * 60)
    logger.info("L0b: PDF Downloader - SG Health Websites")
    logger.info("=" * 60)
    logger.info("Data directory: %s", DATA_RAW_DIR.absolute())
    logger.info("Existing PDFs: %d", len(list_downloaded_pdfs()))

    all_downloaded = []

    logger.info("[1/2] Downloading ACE-HTA Clinical Guidelines PDFs...")
    all_downloaded.extend(await download_pdfs_group("ace_guidelines"))

    logger.info("[2/2] Downloading HealthHub PDFs...")
    all_downloaded.extend(await download_pdfs_group("healthhub"))

    logger.info("=" * 60)
    logger.info("Download complete! Total PDFs in data/raw: %d", len(list_downloaded_pdfs()))
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
