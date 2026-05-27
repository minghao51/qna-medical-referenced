#!/usr/bin/env python3
"""
L0b: Download PDF documents from Singapore government health websites.
Saves PDFs to data/raw directory.
Uses existing manifest from download_web.py for tracking.
"""

import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import yaml

from src.config import DATA_RAW_DIR
from src.ingestion.steps.download_web import _load_manifest as _load_web_manifest
from src.ingestion.steps.download_web import _manifest_indexes as _manifest_indexes_web
from src.ingestion.steps.download_web import _manifest_lock
from src.ingestion.steps.download_web import _save_manifest as _save_web_manifest
from src.ingestion.steps.download_web import normalize_url as normalize_url_web

logger = logging.getLogger(__name__)

MANIFEST_PATH = DATA_RAW_DIR / "download_manifest.json"
SOURCES_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "sources.yaml"


def _load_sources_config() -> dict:
    if not SOURCES_CONFIG_PATH.exists():
        return {}
    with open(SOURCES_CONFIG_PATH, encoding="utf-8") as f:
        return dict(yaml.safe_load(f) or {})


def _get_pdf_sources(group: str) -> list[tuple[str, str]]:
    config = _load_sources_config()
    pdf = config.get("pdf_sources", {})
    entries = pdf.get(group, [])
    return [(e["url"], e["name"]) for e in entries if "url" in e and "name" in e]


def normalize_url(url: str) -> str:
    return normalize_url_web(url)


def get_file_path(url: str, extension: str = "pdf") -> Path:
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]  # nosec B324
    safe_name = re.sub(r"[^\w\-]", "_", url.split("/")[-1][:50])
    if not safe_name or safe_name.endswith("_"):
        safe_name = f"content_{url_hash}"
    if not safe_name.endswith(f".{extension}"):
        safe_name = f"{safe_name}.{extension}"
    return cast(Path, DATA_RAW_DIR / safe_name)


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
    records = manifest.setdefault("records", [])
    records.append(
        {
            "url": url,
            "normalized_url": normalized_url,
            "logical_name": logical_name,
            "filename": file_path.name if file_path else None,
            "content_hash": content_hash,
            "status": status,
            "record_type": "pdf_download",
            "timestamp_utc": datetime.now(UTC).isoformat(),
        }
    )


def _is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return bool(exc.response.status_code >= 500)
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False


async def download_pdf(url: str, timeout: int = 60, max_retries: int = 3) -> bytes | None:
    """Download PDF content from URL with retry for transient errors."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for attempt in range(max_retries):
            try:
                response = await client.get(url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                looks_like_pdf = response.content.startswith(b"%PDF")
                if "pdf" not in content_type.lower() and not looks_like_pdf:
                    logger.warning("Expected PDF but got %s for %s", content_type, url)
                    return None
                return bytes(response.content)
            except httpx.HTTPStatusError as e:
                if _is_transient_error(e) and attempt < max_retries - 1:
                    delay = 2**attempt
                    logger.warning(
                        "Transient HTTP error (attempt %d/%d) for %s, retrying in %ds: %s",
                        attempt + 1,
                        max_retries,
                        url,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.warning("HTTP error downloading %s: %s", url, e)
                return None
            except httpx.RequestError as e:
                if _is_transient_error(e) and attempt < max_retries - 1:
                    delay = 2**attempt
                    logger.warning(
                        "Transient request error (attempt %d/%d) for %s, retrying in %ds: %s",
                        attempt + 1,
                        max_retries,
                        url,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.warning("Request error downloading %s: %s", url, e)
                return None
        return None


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


async def extract_ace_guidelines_pdfs() -> list[Path]:
    """Download ACE-HTA clinical guidelines as PDFs."""
    pdfs = _get_pdf_sources("ace_guidelines")

    downloaded = []
    for url, name in pdfs:
        result = await download_pdf_if_not_exists(url, name)
        if result:
            downloaded.append(result)
    return downloaded


async def extract_healthhub_pdfs() -> list[Path]:
    """Download HealthHub PDFs."""
    pdfs = _get_pdf_sources("healthhub")

    downloaded = []
    for url, name in pdfs:
        result = await download_pdf_if_not_exists(url, name)
        if result:
            downloaded.append(result)
    return downloaded


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
    all_downloaded.extend(await extract_ace_guidelines_pdfs())

    logger.info("[2/2] Downloading HealthHub PDFs...")
    all_downloaded.extend(await extract_healthhub_pdfs())

    logger.info("=" * 60)
    logger.info("Download complete! Total PDFs in data/raw: %d", len(list_downloaded_pdfs()))
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
