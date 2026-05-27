#!/usr/bin/env python3
"""
L0: Download medical content from Singapore government health websites.
Saves content to data/raw directory.
Skips download if target file already exists.
"""

import asyncio
import hashlib
import json
import logging
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse, urlunparse

import httpx
import yaml
from bs4 import BeautifulSoup

from src.config import DATA_RAW_DIR

logger = logging.getLogger(__name__)

DATA_DIR = DATA_RAW_DIR
MANIFEST_PATH = DATA_DIR / "download_manifest.json"
SOURCES_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "sources.yaml"

_manifest_lock = asyncio.Lock()


def _load_sources_config() -> dict[str, Any]:
    if not SOURCES_CONFIG_PATH.exists():
        return {}
    with open(SOURCES_CONFIG_PATH, encoding="utf-8") as f:
        return dict(yaml.safe_load(f) or {})


def _get_web_sources(group: str) -> list[tuple[str, str]]:
    config = _load_sources_config()
    web = config.get("web_sources", {})
    entries = web.get(group, [])
    return [(e["url"], e["name"]) for e in entries if "url" in e and "name" in e]


def get_file_path(url: str, extension: str = "html") -> Path:
    """Generate a filename from URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]  # nosec B324
    safe_name = re.sub(r"[^\w\-]", "_", url.split("/")[-1][:50])
    if not safe_name or safe_name.endswith("_"):
        safe_name = f"content_{url_hash}"
    filename = f"{safe_name}_{url_hash}.{extension}"
    return cast(Path, DATA_DIR / filename)


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    # Drop fragment; retain query for safety since some pages are parameterized.
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def _load_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        try:
            return dict(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))
        except Exception as e:
            logger.error("Failed to load manifest: %s", e)
            backup_path = MANIFEST_PATH.with_suffix(".json.corrupt")
            try:
                shutil.copy2(str(MANIFEST_PATH), str(backup_path))
                logger.error("Corrupt manifest backed up to %s", backup_path)
            except Exception as backup_err:
                logger.error("Failed to back up corrupt manifest: %s", backup_err)
            return {"records": []}
    return {"records": []}


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _manifest_indexes(manifest: dict) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    records = manifest.get("records", [])
    by_url = {str(r.get("normalized_url")): r for r in records if r.get("normalized_url")}
    by_hash: dict[str, list[dict]] = {}
    for r in records:
        ch = r.get("content_hash")
        if not ch:
            continue
        by_hash.setdefault(str(ch), []).append(r)
    return by_url, by_hash


def get_manifest_alias_filenames(manifest: dict | None = None) -> set[str]:
    manifest = manifest or _load_manifest()
    aliases: set[str] = set()
    for record in manifest.get("records", []):
        status = str(record.get("status", ""))
        filename = record.get("filename")
        duplicate_of = record.get("duplicate_of")
        if not filename or not isinstance(filename, str):
            continue
        # Only treat on-disk alias files as ignorable. Download-time alias records point
        # filename at the canonical file (filename == duplicate_of), so they are not aliases on disk.
        if (
            status in {"duplicate_content_alias", "ignored_duplicate_alias"}
            and duplicate_of
            and filename != duplicate_of
        ):
            aliases.add(filename)
    return aliases


def migrate_existing_html_duplicates(
    *,
    archive_aliases: bool = False,
    delete_aliases: bool = False,
    dry_run: bool = True,
    archive_dir_name: str = "_duplicate_html_archive",
) -> dict:
    """
    Build manifest inventory for existing HTML files and mark duplicate aliases by content hash.

    Returns a summary report. If `archive_aliases` is true, duplicate aliases are moved to
    DATA_DIR/<archive_dir_name>. If `delete_aliases` is true, aliases are deleted.
    """
    if archive_aliases and delete_aliases:
        raise ValueError("Choose either archive_aliases or delete_aliases, not both")

    manifest = _load_manifest()
    html_files = sorted(DATA_DIR.glob("*.html"))
    grouped: dict[str, list[Path]] = {}
    for path in html_files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        grouped.setdefault(digest, []).append(path)

    archive_dir = DATA_DIR / archive_dir_name
    inventory_records: list[dict] = []
    alias_count = 0
    canonical_count = 0
    archived = 0
    deleted = 0

    for digest, files in grouped.items():
        files_sorted = sorted(files, key=lambda p: (len(p.name), p.name))
        canonical = files_sorted[0]
        canonical_count += 1
        inventory_records.append(
            {
                "url": None,
                "normalized_url": None,
                "logical_name": canonical.stem,
                "filename": canonical.name,
                "content_hash": digest,
                "status": "inventory_canonical",
                "duplicate_of": None,
                "record_type": "file_inventory",
                "timestamp_utc": datetime.now(UTC).isoformat(),
            }
        )
        for alias in files_sorted[1:]:
            alias_count += 1
            status = "duplicate_content_alias"
            target_name = alias.name
            if archive_aliases:
                status = "archived_duplicate_alias"
                target_name = alias.name
                if not dry_run:
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(alias), str(archive_dir / alias.name))
                    archived += 1
            elif delete_aliases:
                status = "deleted_duplicate_alias"
                if not dry_run:
                    alias.unlink(missing_ok=True)
                    deleted += 1
            else:
                status = "ignored_duplicate_alias"
            inventory_records.append(
                {
                    "url": None,
                    "normalized_url": None,
                    "logical_name": alias.stem,
                    "filename": target_name,
                    "content_hash": digest,
                    "status": status,
                    "duplicate_of": canonical.name,
                    "record_type": "file_inventory",
                    "timestamp_utc": datetime.now(UTC).isoformat(),
                }
            )

    # Replace previous inventory records but retain download records.
    manifest["records"] = [
        r for r in manifest.get("records", []) if r.get("record_type") != "file_inventory"
    ]
    manifest["records"].extend(inventory_records)
    if not dry_run:
        _save_manifest(manifest)

    return {
        "dry_run": dry_run,
        "html_files_scanned": len(html_files),
        "unique_content_hashes": len(grouped),
        "canonical_count": canonical_count,
        "alias_count": alias_count,
        "archived_aliases": archived,
        "deleted_aliases": deleted,
        "archive_dir": str(archive_dir),
    }


def _register_manifest_record(
    *,
    manifest: dict,
    url: str,
    normalized_url: str,
    logical_name: str,
    file_path: Path | None,
    content_hash: str | None,
    status: str,
    duplicate_of: str | None = None,
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
            "duplicate_of": duplicate_of,
            "timestamp_utc": datetime.now(UTC).isoformat(),
        }
    )


def _find_existing_file_by_content_hash(content_hash_value: str) -> Path | None:
    for html_file in DATA_DIR.glob("*.html"):
        try:
            digest = hashlib.sha256(html_file.read_bytes()).hexdigest()[:16]
            if digest == content_hash_value:
                return cast(Path, html_file)
        except Exception as e:
            logger.debug("Failed to hash file %s: %s", html_file.name, e)
            continue
    return None


def get_manifest_record_by_filename(filename: str) -> dict[str, Any] | None:
    """Look up manifest record by filename."""
    manifest = _load_manifest()
    for record in manifest.get("records", []):
        if record.get("filename") == filename:
            return dict(record)
    return None


def get_manifest_record_by_logical_name(logical_name: str) -> dict[str, Any] | None:
    """Look up manifest record by logical_name."""
    manifest = _load_manifest()
    for record in manifest.get("records", []):
        if record.get("logical_name") == logical_name:
            return dict(record)
    return None


def file_exists(url: str, extension: str = "html") -> bool:
    """Check if file already exists for this URL."""
    normalized = normalize_url(url)
    manifest = _load_manifest()
    by_url, _ = _manifest_indexes(manifest)
    if normalized in by_url and by_url[normalized].get("filename"):
        existing = DATA_DIR / str(by_url[normalized]["filename"])
        if existing.exists():
            return True
    file_path = get_file_path(url, extension)
    return file_path.exists()


def _is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return bool(exc.response.status_code >= 500)
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False


async def download_url(url: str, timeout: int = 30, max_retries: int = 3) -> str | None:
    """Download content from URL with retry for transient errors."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(max_retries):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return str(response.text)
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


async def download_binary(url: str, timeout: int = 60, max_retries: int = 3) -> bytes | None:
    """Download binary content (PDF) from URL with retry for transient errors."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(max_retries):
            try:
                response = await client.get(url)
                response.raise_for_status()
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


async def _download_and_save_html(url: str, logical_name: str, timeout: int = 30) -> str | None:
    normalized_url = normalize_url(url)
    async with _manifest_lock:
        manifest = _load_manifest()
        by_url, by_hash = _manifest_indexes(manifest)
        prior = by_url.get(normalized_url)
        if prior and prior.get("filename"):
            file_path = DATA_DIR / str(prior["filename"])
            if file_path.exists():
                logger.info("Skipping (manifest exists): %s", logical_name)
                return None

    logger.info("Downloading: %s", logical_name)
    content = await download_url(url, timeout)
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

    content_hash_value = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:16]

    async with _manifest_lock:
        manifest = _load_manifest()
        _, by_hash = _manifest_indexes(manifest)
        duplicate_record = next(iter(by_hash.get(content_hash_value, [])), None)
        if duplicate_record and duplicate_record.get("filename"):
            duplicate_file = DATA_DIR / str(duplicate_record["filename"])
            if duplicate_file.exists():
                logger.info(
                    "Skipping duplicate content: %s (same as %s)", logical_name, duplicate_file.name
                )
                _register_manifest_record(
                    manifest=manifest,
                    url=url,
                    normalized_url=normalized_url,
                    logical_name=logical_name,
                    file_path=duplicate_file,
                    content_hash=content_hash_value,
                    status="duplicate_content_alias",
                    duplicate_of=duplicate_file.name,
                )
                _save_manifest(manifest)
                return None

    existing_file = _find_existing_file_by_content_hash(content_hash_value)
    if existing_file is not None:
        async with _manifest_lock:
            manifest = _load_manifest()
            logger.info(
                "Skipping duplicate content (filesystem): %s (same as %s)",
                logical_name,
                existing_file.name,
            )
            _register_manifest_record(
                manifest=manifest,
                url=url,
                normalized_url=normalized_url,
                logical_name=logical_name,
                file_path=existing_file,
                content_hash=content_hash_value,
                status="duplicate_content_alias",
                duplicate_of=existing_file.name,
            )
            _save_manifest(manifest)
        return None

    file_path = get_file_path(url, "html")
    file_path.write_text(content, encoding="utf-8")
    async with _manifest_lock:
        manifest = _load_manifest()
        _register_manifest_record(
            manifest=manifest,
            url=url,
            normalized_url=normalized_url,
            logical_name=logical_name,
            file_path=file_path,
            content_hash=content_hash_value,
            status="downloaded",
        )
        _save_manifest(manifest)
    logger.info("  Saved: %s", file_path.name)
    return str(file_path)


def clean_html_to_text(html: str) -> str:
    """Extract clean text from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line and len(line) > 2]
    return "\n".join(lines)


async def extract_ace_clinical_guidelines() -> list[str]:
    """Extract ACE Clinical Guidelines from ace-hta.gov.sg."""
    guidelines = _get_web_sources("ace_clinical_guidelines")

    results = await asyncio.gather(
        *[_download_and_save_html(url, name) for url, name in guidelines]
    )
    return [r for r in results if r]


async def extract_ace_cues() -> list[str]:
    """Extract ACE CUES resources from ace-hta.gov.sg."""
    pages = _get_web_sources("ace_cues")

    results = await asyncio.gather(*[_download_and_save_html(url, name) for url, name in pages])
    return [r for r in results if r]


async def extract_ace_drug_guidances() -> list[str]:
    """Extract ACE Drug Guidances from ace-hta.gov.sg."""
    guidances = _get_web_sources("ace_drug_guidances")

    results = await asyncio.gather(*[_download_and_save_html(url, name) for url, name in guidances])
    return [r for r in results if r]


async def extract_healthhub_content() -> list[str]:
    """Extract HealthHub health conditions and screening info."""
    pages = _get_web_sources("healthhub")

    results = await asyncio.gather(*[_download_and_save_html(url, name) for url, name in pages])
    return [r for r in results if r]


async def extract_hpp_guidelines() -> list[str]:
    """Extract HPP/MOH Professional Guidelines."""
    pages = _get_web_sources("hpp_guidelines")

    results = await asyncio.gather(*[_download_and_save_html(url, name) for url, name in pages])
    return [r for r in results if r]


async def extract_moh_content() -> list[str]:
    """Extract MOH Singapore main page."""
    pages = _get_web_sources("moh")

    results = await asyncio.gather(*[_download_and_save_html(url, name) for url, name in pages])
    return [r for r in results if r]


async def extract_international_guidelines() -> list[str]:
    """Extract international medical guidelines (NHS/NICE) with extended timeout."""
    pages = _get_web_sources("international_guidelines")

    results = await asyncio.gather(
        *[_download_and_save_html(url, name, timeout=60) for url, name in pages]
    )
    return [r for r in results if r]


def list_downloaded_files() -> list[str]:
    """List all downloaded files in data/raw."""
    if not DATA_DIR.exists():
        return []
    return [str(f) for f in DATA_DIR.iterdir() if f.is_file()]


async def main():
    """Main function to download all content."""
    logger.info("=" * 60)
    logger.info("L0: Medical Content Downloader")
    logger.info("=" * 60)
    logger.info("Data directory: %s", DATA_DIR.absolute())
    logger.info("Existing files: %d", len(list_downloaded_files()))

    all_downloaded = []

    logger.info("[1/6] Downloading ACE Clinical Guidelines...")
    all_downloaded.extend(await extract_ace_clinical_guidelines())

    logger.info("[2/6] Downloading ACE CUES resources...")
    all_downloaded.extend(await extract_ace_cues())

    logger.info("[3/6] Downloading ACE Drug Guidances...")
    all_downloaded.extend(await extract_ace_drug_guidances())

    logger.info("[4/6] Downloading HealthHub content...")
    all_downloaded.extend(await extract_healthhub_content())

    logger.info("[5/6] Downloading HPP Guidelines...")
    all_downloaded.extend(await extract_hpp_guidelines())

    logger.info("[6/6] Downloading International Guidelines (NHS/NICE)...")
    all_downloaded.extend(await extract_international_guidelines())

    logger.info("=" * 60)
    logger.info("Download complete! Total files in data/raw: %d", len(list_downloaded_files()))
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download source HTML pages and manage duplicate aliases"
    )
    parser.add_argument(
        "--cleanup-duplicates",
        action="store_true",
        help="Backfill manifest inventory for existing HTML duplicates",
    )
    parser.add_argument(
        "--archive-aliases",
        action="store_true",
        help="Archive duplicate alias HTML files (used with --cleanup-duplicates)",
    )
    parser.add_argument(
        "--delete-aliases",
        action="store_true",
        help="Delete duplicate alias HTML files (used with --cleanup-duplicates)",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry-run)")
    args = parser.parse_args()

    if args.cleanup_duplicates:
        summary = migrate_existing_html_duplicates(
            archive_aliases=args.archive_aliases,
            delete_aliases=args.delete_aliases,
            dry_run=not args.apply,
        )
        print(json.dumps(summary, indent=2))
    else:
        asyncio.run(main())
