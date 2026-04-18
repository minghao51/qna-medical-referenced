"""L0 download quality checks."""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from src.config import DATA_RAW_DIR
from src.ingestion.steps.download_web import _load_manifest, get_manifest_alias_filenames

logger = logging.getLogger(__name__)


def audit_l0_download(data_raw_dir: Path | None = None) -> dict[str, Any]:
    data_dir = Path(data_raw_dir or DATA_RAW_DIR)
    html_files = sorted(data_dir.glob("*.html"))
    records: list[dict[str, Any]] = []
    duplicate_hashes: Counter[str] = Counter()
    small_count = 0
    parse_failures = 0

    for html_path in html_files:
        raw = html_path.read_text(encoding="utf-8", errors="ignore")
        size_bytes = html_path.stat().st_size
        text_chars = 0
        parse_ok = True
        try:
            soup = BeautifulSoup(raw, "html.parser")
            text_chars = len(soup.get_text(" ", strip=True))
        except Exception as e:
            logger.debug("Failed to parse HTML file %s: %s", html_path, e)
            parse_ok = False
            parse_failures += 1
        content_hash = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()
        duplicate_hashes[content_hash] += 1
        if size_bytes < 2048:
            small_count += 1
        records.append(
            {
                "file": html_path.name,
                "size_bytes": size_bytes,
                "parse_ok": parse_ok,
                "visible_text_chars": text_chars,
                "has_html_tag": "<html" in raw.lower(),
                "has_body_tag": "<body" in raw.lower(),
            }
        )

    duplicate_files = sum(count - 1 for count in duplicate_hashes.values() if count > 1)
    manifest = _load_manifest()
    alias_filenames = get_manifest_alias_filenames(manifest)
    alias_files_on_disk = [r for r in records if str(r.get("file")) in alias_filenames]
    alias_duplicate_count = len(alias_files_on_disk)
    true_duplicate_files = max(0, duplicate_files - alias_duplicate_count)
    aggregate = {
        "html_file_count": len(html_files),
        "small_file_rate": (small_count / len(html_files)) if html_files else 0.0,
        "duplicate_file_rate": (duplicate_files / len(html_files)) if html_files else 0.0,
        "duplicate_alias_file_rate": (alias_duplicate_count / len(html_files))
        if html_files
        else 0.0,
        "true_duplicate_file_rate": (true_duplicate_files / len(html_files)) if html_files else 0.0,
        "html_parse_success_rate": ((len(html_files) - parse_failures) / len(html_files))
        if html_files
        else 0.0,
        "manifest_inventory_record_count": sum(
            1 for r in manifest.get("records", []) if r.get("record_type") == "file_inventory"
        ),
    }
    findings = []
    if aggregate["small_file_rate"] > 0.2:
        findings.append(
            {"severity": "warning", "message": "High small HTML file rate", "stage": "L0"}
        )
    return {"aggregate": aggregate, "records": records, "findings": findings}
