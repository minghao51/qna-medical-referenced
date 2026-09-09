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
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from src.config import DATA_RAW_DIR
from src.ingestion.steps._utils import (
    download_with_retry,
    load_sources_config,
    register_manifest_record,
    url_file_path,
)

logger = logging.getLogger(__name__)

DATA_DIR = DATA_RAW_DIR
MANIFEST_PATH = DATA_DIR / "download_manifest.json"

_manifest_lock = asyncio.Lock()

# Manifest cache: avoids re-reading + re-parsing the JSON on every lookup.
# Invalidated by (path, mtime_ns, size) stamp and refreshed on _save_manifest.
_manifest_cache: dict[str, Any] | None = None
_manifest_cache_stamp: tuple[str, int, int] | None = None

# Content-hash index of on-disk HTML files: hash[:16] -> Path.
# Built once per run instead of re-hashing every file per downloaded URL.
_content_hash_index: dict[str, Path] | None = None
_content_hash_index_dir: str | None = None


def _get_web_sources(group: str) -> list[tuple[str, str]]:
    config = load_sources_config()
    web = config.get("web_sources", {})
    entries = web.get(group, [])
    return [(e["url"], e["name"]) for e in entries if "url" in e and "name" in e]


def get_file_path(url: str, extension: str = "html") -> Path:
    """Generate a filename from URL."""
    return url_file_path(url, DATA_DIR, extension)


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    # Drop fragment; retain query for safety since some pages are parameterized.
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def _manifest_stamp() -> tuple[str, int, int] | None:
    try:
        stat = MANIFEST_PATH.stat()
    except OSError:
        return None
    return (str(MANIFEST_PATH), stat.st_mtime_ns, stat.st_size)


def _load_manifest() -> dict[str, Any]:
    """Load the manifest JSON, cached and invalidated on mtime/size change."""
    global _manifest_cache, _manifest_cache_stamp
    if MANIFEST_PATH.exists():
        try:
            stamp = _manifest_stamp()
            if _manifest_cache is not None and stamp is not None and stamp == _manifest_cache_stamp:
                return _manifest_cache
            manifest = dict(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))
            _manifest_cache = manifest
            _manifest_cache_stamp = stamp
            return manifest
        except Exception as e:
            logger.error("Failed to load manifest: %s", e)
            backup_path = MANIFEST_PATH.with_suffix(".json.corrupt")
            try:
                shutil.copy2(str(MANIFEST_PATH), str(backup_path))
                logger.error("Corrupt manifest backed up to %s", backup_path)
            except Exception as backup_err:
                logger.error("Failed to back up corrupt manifest: %s", backup_err)
            _manifest_cache = None
            _manifest_cache_stamp = None
            return {"records": []}
    _manifest_cache = None
    _manifest_cache_stamp = None
    return {"records": []}


def _save_manifest(manifest: dict) -> None:
    """Atomically overwrite the manifest (temp file + os.replace) so a crash
    mid-write can never leave a truncated/corrupt manifest behind."""
    global _manifest_cache, _manifest_cache_stamp
    tmp_path = MANIFEST_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, MANIFEST_PATH)
    # Write-through: keep the cache in sync so subsequent reads skip re-parsing.
    _manifest_cache = manifest
    _manifest_cache_stamp = _manifest_stamp()


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


def _invalidate_content_hash_index() -> None:
    global _content_hash_index
    _content_hash_index = None


def _build_content_hash_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for html_file in sorted(DATA_DIR.glob("*.html")):
        try:
            digest = hashlib.sha256(html_file.read_bytes()).hexdigest()[:16]
        except Exception as e:
            logger.debug("Failed to hash file %s: %s", html_file.name, e)
            continue
        index.setdefault(digest, html_file)
    return index


def _get_content_hash_index() -> dict[str, Path]:
    global _content_hash_index, _content_hash_index_dir
    if _content_hash_index is None or _content_hash_index_dir != str(DATA_DIR):
        _content_hash_index = _build_content_hash_index()
        _content_hash_index_dir = str(DATA_DIR)
    return _content_hash_index


def _index_downloaded_file(digest: str, path: Path) -> None:
    """Record a freshly written HTML file in the content-hash index (no rescan)."""
    _get_content_hash_index().setdefault(digest, path)


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
    manifest = {
        "records": [
            r
            for r in _load_manifest().get("records", [])
            if r.get("record_type") != "file_inventory"
        ]
    }
    manifest["records"].extend(inventory_records)
    if not dry_run:
        _save_manifest(manifest)
        _invalidate_content_hash_index()

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


def _find_existing_file_by_content_hash(content_hash_value: str) -> Path | None:
    existing = _get_content_hash_index().get(content_hash_value)
    if existing is not None and existing.exists():
        return existing
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


async def download_url(url: str, timeout: int = 30, max_retries: int = 3) -> str | None:
    """Download text content from URL with retry for transient errors."""
    response = await download_with_retry(url, timeout=timeout, max_retries=max_retries)
    if response is None:
        return None
    return str(response.text)


async def _download_and_save_html(url: str, logical_name: str, timeout: int = 30) -> str | None:
    normalized_url = normalize_url(url)
    async with _manifest_lock:
        manifest = _load_manifest()
        by_url, _ = _manifest_indexes(manifest)
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
            register_manifest_record(
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

    # Hold the manifest lock from the duplicate checks through the file write so a
    # concurrent download of identical content cannot slip in between (TOCTOU).
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
                register_manifest_record(
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
            logger.info(
                "Skipping duplicate content (filesystem): %s (same as %s)",
                logical_name,
                existing_file.name,
            )
            register_manifest_record(
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
        _index_downloaded_file(content_hash_value, file_path)
        register_manifest_record(
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


async def download_group(sources_group: str, *, timeout: int = 30) -> list[str]:
    """Download all configured web pages for one sources.yaml group concurrently."""
    pages = _get_web_sources(sources_group)

    results = await asyncio.gather(
        *[_download_and_save_html(url, name, timeout=timeout) for url, name in pages]
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

    _invalidate_content_hash_index()

    all_downloaded = []

    logger.info("[1/6] Downloading ACE Clinical Guidelines...")
    all_downloaded.extend(await download_group("ace_clinical_guidelines"))

    logger.info("[2/6] Downloading ACE CUES resources...")
    all_downloaded.extend(await download_group("ace_cues"))

    logger.info("[3/6] Downloading ACE Drug Guidances...")
    all_downloaded.extend(await download_group("ace_drug_guidances"))

    logger.info("[4/6] Downloading HealthHub content...")
    all_downloaded.extend(await download_group("healthhub"))

    logger.info("[5/6] Downloading HPP Guidelines...")
    all_downloaded.extend(await download_group("hpp_guidelines"))

    logger.info("[6/6] Downloading International Guidelines (NHS/NICE)...")
    all_downloaded.extend(await download_group("international_guidelines", timeout=60))

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
