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

import httpx

from src.config import DATA_RAW_DIR
from src.ingestion.steps.download_web import _load_manifest as _load_web_manifest
from src.ingestion.steps.download_web import _manifest_indexes as _manifest_indexes_web
from src.ingestion.steps.download_web import _save_manifest as _save_web_manifest
from src.ingestion.steps.download_web import normalize_url as normalize_url_web

logger = logging.getLogger(__name__)

MANIFEST_PATH = DATA_RAW_DIR / "download_manifest.json"


def normalize_url(url: str) -> str:
    return normalize_url_web(url)


def get_file_path(url: str, extension: str = "pdf") -> Path:
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]  # nosec B324
    safe_name = re.sub(r"[^\w\-]", "_", url.split("/")[-1][:50])
    if not safe_name or safe_name.endswith("_"):
        safe_name = f"content_{url_hash}"
    if not safe_name.endswith(f".{extension}"):
        safe_name = f"{safe_name}.{extension}"
    return DATA_RAW_DIR / safe_name


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


async def download_pdf(url: str, timeout: int = 60) -> bytes | None:
    """Download PDF content from URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            looks_like_pdf = response.content.startswith(b"%PDF")
            if "pdf" not in content_type.lower() and not looks_like_pdf:
                logger.warning("Expected PDF but got %s for %s", content_type, url)
                return None
            return response.content
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error downloading %s: %s", url, e)
            return None
        except httpx.RequestError as e:
            logger.warning("Request error downloading %s: %s", url, e)
            return None


async def download_pdf_if_not_exists(url: str, logical_name: str) -> Path | None:
    """Download PDF if it doesn't already exist."""
    normalized_url = normalize_url(url)
    manifest = _load_manifest()
    by_url, _ = _manifest_indexes(manifest)
    prior = by_url.get(normalized_url)
    if prior and prior.get("filename"):
        prior_path = DATA_RAW_DIR / str(prior["filename"])
        if prior_path.exists():
            print(f"Skipping (manifest exists): {logical_name}")
            return None

    file_path = get_file_path(url, "pdf")
    if file_path.exists():
        print(f"Skipping (file exists): {file_path.name}")
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

    print(f"Downloading: {logical_name}")
    content = await download_pdf(url)
    if not content:
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
    print(f"  Saved: {file_path.name}")
    return file_path


async def extract_ace_guidelines_pdfs() -> list[Path]:
    """Download ACE-HTA clinical guidelines as PDFs."""
    pdfs = [
        (
            "https://isomer-user-content.by.gov.sg/68/f6d8c12c-8f8f-45ac-9d3a-65a7de2d03d0/promoting-smoking-cessation-and-treating-tobacco-dependence-(feb-2025).pdf",
            "ace_smoking_cessation_2025",
        ),
        (
            "https://isomer-user-content.by.gov.sg/68/9f17c634-63fc-4ac4-80ea-76333821e03c/chronic-obstructive-pulmonary-disease-diagnosis-and-management-(dec-2024).pdf",
            "ace_copd_2024",
        ),
        (
            "https://www.diabetes.org.sg/wp-content/uploads/2025/06/initiating-basal-insulin-in-type-2-diabetes-mellitus-nov-2024.pdf",
            "ace_diabetes_insulin_2024",
        ),
        (
            "https://isomer-user-content.by.gov.sg/68/28e76ffa-36bf-4eaf-93fd-3d656f27a598/triple-therapy-inhalers-for-treating-asthma-or-chronic-obstructive-pulmonary-disease-(17-feb-2025).pdf",
            "ace_triple_therapy_inhalers_2025",
        ),
        (
            "https://isomer-user-content.by.gov.sg/68/6b7c42ca-5e21-4913-b9ed-6ed0d313e1f4/guidance_pneumococcal_conjugate_vaccines_prevention_of_pneumococcal_disease_adults_(10_feb_2025).pdf",
            "ace_pcv20_vaccine_2025",
        ),
        (
            "https://isomer-user-content.by.gov.sg/68/4c5a6e2b-1c9a-4f3e-9b2d-8e7f6a0c3b5d/mild-and-moderate-atopic-dermatitis-acg-(feb-2026).pdf",
            "ace_atopic_dermatitis_2026",
        ),
        (
            "https://isomer-user-content.by.gov.sg/68/7d8b3c4e-2f6a-4b8d-9e1c-5f0a7d9e3b2c/osteoporosis-diagnosis-and-management-acg-(aug-2025).pdf",
            "ace_osteoporosis_2025",
        ),
    ]

    downloaded = []
    for url, name in pdfs:
        result = await download_pdf_if_not_exists(url, name)
        if result:
            downloaded.append(result)
    return downloaded


async def extract_healthhub_pdfs() -> list[Path]:
    """Download HealthHub PDFs."""
    pdfs = [
        (
            "https://ch-api.healthhub.sg/api/public/content/98f52be9ace040148af419218c9966f8",
            "healthhub_child_health_checklist",
        ),
        (
            "https://ch-api.healthhub.sg/api/public/content/241f1578608d41258bb67f02edc678f0",
            "healthhub_nutrient_guidelines",
        ),
        (
            "https://ch-api.healthhub.sg/api/public/content/dcd8a51e125b4faf90b467013eae7e73",
            "healthhub_healthy365_faq",
        ),
        (
            "https://ch-api.healthhub.sg/api/public/content/recommended-dietary-allowances",
            "healthhub_rda",
        ),
        (
            "https://ch-api.healthhub.sg/api/public/content/childhood-immunisation-schedule",
            "healthhub_immunisation_schedule",
        ),
        (
            "https://ch-api.healthhub.sg/api/public/content/mindsg-mental-health",
            "healthhub_mindsg",
        ),
    ]

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
    print("=" * 60)
    print("L0b: PDF Downloader - SG Health Websites")
    print("=" * 60)
    print(f"\nData directory: {DATA_RAW_DIR.absolute()}")
    print(f"Existing PDFs: {len(list_downloaded_pdfs())}")
    print()

    all_downloaded = []

    print("\n[1/2] Downloading ACE-HTA Clinical Guidelines PDFs...")
    all_downloaded.extend(await extract_ace_guidelines_pdfs())

    print("\n[2/2] Downloading HealthHub PDFs...")
    all_downloaded.extend(await extract_healthhub_pdfs())

    print("\n" + "=" * 60)
    print(f"Download complete! Total PDFs in data/raw: {len(list_downloaded_pdfs())}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
