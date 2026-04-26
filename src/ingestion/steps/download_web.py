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
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from src.config import DATA_RAW_DIR

logger = logging.getLogger(__name__)

DATA_DIR = DATA_RAW_DIR
MANIFEST_PATH = DATA_DIR / "download_manifest.json"


def get_file_path(url: str, extension: str = "html") -> Path:
    """Generate a filename from URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]  # nosec B324
    safe_name = re.sub(r"[^\w\-]", "_", url.split("/")[-1][:50])
    if not safe_name or safe_name.endswith("_"):
        safe_name = f"content_{url_hash}"
    filename = f"{safe_name}_{url_hash}.{extension}"
    return DATA_DIR / filename


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
            logger.debug("Failed to load manifest: %s", e)
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
                return html_file
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


async def download_url(url: str, timeout: int = 30) -> str | None:
    """Download content from URL."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error downloading %s: %s", url, e)
            return None
        except httpx.RequestError as e:
            logger.warning("Request error downloading %s: %s", url, e)
            return None


async def download_binary(url: str, timeout: int = 60) -> bytes | None:
    """Download binary content (PDF) from URL."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error downloading %s: %s", url, e)
            return None
        except httpx.RequestError as e:
            logger.warning("Request error downloading %s: %s", url, e)
            return None


async def _download_and_save_html(url: str, logical_name: str, timeout: int = 30) -> str | None:
    normalized_url = normalize_url(url)
    manifest = _load_manifest()
    by_url, by_hash = _manifest_indexes(manifest)
    prior = by_url.get(normalized_url)
    if prior and prior.get("filename"):
        file_path = DATA_DIR / str(prior["filename"])
        if file_path.exists():
            print(f"Skipping (manifest exists): {logical_name}")
            return None

    print(f"Downloading: {logical_name}")
    content = await download_url(url, timeout)
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

    content_hash_value = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:16]
    duplicate_record = next(iter(by_hash.get(content_hash_value, [])), None)
    if duplicate_record and duplicate_record.get("filename"):
        duplicate_file = DATA_DIR / str(duplicate_record["filename"])
        if duplicate_file.exists():
            print(f"Skipping duplicate content: {logical_name} (same as {duplicate_file.name})")
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
        print(
            f"Skipping duplicate content (filesystem): {logical_name} (same as {existing_file.name})"
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
    print(f"  Saved: {file_path.name}")
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
    guidelines = [
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/",
            "ace_guidelines_index",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/osteoporosis--diagnosis-and-management/",
            "osteoporosis_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/major-depressive-disorder-achieving-and-sustaining-remission/",
            "depression_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/generalised-anxiety-disorder-easing-burden-and-enabling-remission/",
            "anxiety_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/management-of-chronic-coronary-syndrome/",
            "coronary_syndrome_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/promoting-smoking-cessation-and-treating-tobacco-dependence/",
            "smoking_cessation_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/chronic-obstructive-pulmonary-disease-diagnosis-and-management/",
            "copd_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/initiating-basal-insulin-in-type-2-diabetes-mellitus/",
            "diabetes_insulin_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/foot-assessment-in-patients-with-diabetes-mellitus/",
            "diabetes_foot_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/venous-thromboembolism-treating-with-the-appropriate-anticoagulant-and-duration/",
            "vte_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/lipid-management-focus-on-cardiovascular-risk/",
            "lipid_management_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/mild-and-moderate-atopic-dermatitis-acg/",
            "atopic_dermatitis_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/heart-failure-acg/",
            "heart_failure_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/atrial-fibrillation-acg/",
            "atrial_fibrillation_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/chronic-kidney-disease-acg/",
            "ckd_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/asthma-diagnosis-management/",
            "asthma_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/obesity-weight-management-acg/",
            "obesity_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/allergic-rhinitis-acg/",
            "allergic_rhinitis_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/dementia-acg/",
            "dementia_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/bipolar-disorder-acg/",
            "bipolar_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/gord-acg/",
            "gord_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/osteoarthritis-knee-acg/",
            "osteoarthritis_guideline",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/stroke-management-acg/",
            "stroke_guideline",
        ),
    ]

    results = await asyncio.gather(
        *[_download_and_save_html(url, name) for url, name in guidelines]
    )
    return [r for r in results if r]


async def extract_ace_cues() -> list[str]:
    """Extract ACE CUES resources from ace-hta.gov.sg."""
    pages = [
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-cues-overview/",
            "ace_cues_index",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-cues/asthma-management/",
            "ace_cues_asthma",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-cues/inhaler-technique-videos/",
            "ace_cues_inhaler",
        ),
    ]

    results = await asyncio.gather(
        *[_download_and_save_html(url, name) for url, name in pages]
    )
    return [r for r in results if r]


async def extract_ace_drug_guidances() -> list[str]:
    """Extract ACE Drug Guidances from ace-hta.gov.sg."""
    guidances = [
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/semaglutide-obesity/",
            "semaglutide_obesity",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/empagliflozin/",
            "empagliflozin",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/glp1-diabetes/",
            "glp1_diabetes",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/apixaban/",
            "apixaban",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/pcsk9-inhibitors/",
            "pcsk9_inhibitors",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/biologics-asthma/",
            "biologics_asthma",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/trastuzumab-deruxtecan-nsclc/",
            "trastuzumab_deruxtecan",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/ribociclib-breast/",
            "ribociclib_breast",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/inavolisib-breast/",
            "inavolisib_breast",
        ),
        (
            "https://www.ace-hta.gov.sg/healthcare-professionals/ace-technology-guidances/drug-guidance/ustekinumab-biosimilar/",
            "ustekinumab",
        ),
    ]

    results = await asyncio.gather(
        *[_download_and_save_html(url, name) for url, name in guidances]
    )
    return [r for r in results if r]


async def extract_healthhub_content() -> list[str]:
    """Extract HealthHub health conditions and screening info."""
    pages = [
        ("https://www.healthhub.sg/health-conditions/high-cholesterol", "high_cholesterol"),
        ("https://www.healthhub.sg/health-conditions/diabetes", "diabetes"),
        ("https://www.healthhub.sg/health-conditions/hypertension", "hypertension"),
        (
            "https://www.healthhub.sg/well-being-and-lifestyle/personal-care/type-2-screening-tests",
            "health_screening_tests",
        ),
        (
            "https://www.healthhub.sg/programmes/healthiersg-screening/screening-faq",
            "healthier_sg_screening_faq",
        ),
        (
            "https://www.healthhub.sg/well-being-and-lifestyle/mental-wellness/",
            "mental_wellness",
        ),
        (
            "https://www.healthhub.sg/well-being-and-lifestyle/exercise-and-fitness/",
            "exercise_fitness",
        ),
        (
            "https://www.healthhub.sg/well-being-and-lifestyle/food-diet-and-nutrition/",
            "food_nutrition",
        ),
        (
            "https://www.healthhub.sg/well-being-and-lifestyle/active-ageing/",
            "active_ageing",
        ),
        (
            "https://www.healthhub.sg/well-being-and-lifestyle/personal-care/all-you-need-to-know-about-vaccinations/",
            "vaccinations_guide",
        ),
    ]

    results = await asyncio.gather(
        *[_download_and_save_html(url, name) for url, name in pages]
    )
    return [r for r in results if r]


async def extract_hpp_guidelines() -> list[str]:
    """Extract HPP/MOH Professional Guidelines."""
    pages = [
        ("https://hpp.moh.gov.sg/guidelines/", "hpp_guidelines_index"),
        (
            "https://hpp.moh.gov.sg/guidelines/collaborative-prescribing/",
            "collab_prescribing_guideline",
        ),
        (
            "https://hpp.moh.gov.sg/guidelines/infection-prevention-and-control-guidelines-and-standards/",
            "infection_control_guideline",
        ),
        (
            "https://hpp.moh.gov.sg/guidelines/eatwise-sg/",
            "eatwise_sg_guideline",
        ),
        (
            "https://hpp.moh.gov.sg/guidelines/practice-guide-for-tiered-care-model-for-mental-health/",
            "mental_health_tiered_care",
        ),
        (
            "https://hpp.moh.gov.sg/guidelines/medisave-for-chronic-disease-management-programme/",
            "medisave_cdmp_guideline",
        ),
        (
            "https://hpp.moh.gov.sg/guidelines/dental-fee-benchmarks/",
            "dental_fee_benchmarks",
        ),
    ]

    results = await asyncio.gather(
        *[_download_and_save_html(url, name) for url, name in pages]
    )
    return [r for r in results if r]


async def extract_moh_content() -> list[str]:
    """Extract MOH Singapore main page."""
    pages = [
        ("https://www.moh.gov.sg/", "moh_singapore"),
    ]

    results = await asyncio.gather(
        *[_download_and_save_html(url, name) for url, name in pages]
    )
    return [r for r in results if r]


async def extract_international_guidelines() -> list[str]:
    """Extract international medical guidelines (NHS/NICE) with extended timeout."""
    pages = [
        ("https://www.nice.org.uk/guidance/ng28", "nice_diabetes_ng28"),
        ("https://www.nice.org.uk/guidance/cg127", "nice_hypertension"),
        ("https://www.nice.org.uk/guidance/cg181", "nice_lipid"),
        ("https://www.nice.org.uk/guidance/ng236", "nice_heart_failure"),
    ]

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
    print("=" * 60)
    print("L0: Medical Content Downloader")
    print("=" * 60)
    print(f"\nData directory: {DATA_DIR.absolute()}")
    print(f"Existing files: {len(list_downloaded_files())}")
    print()

    all_downloaded = []

    print("\n[1/6] Downloading ACE Clinical Guidelines...")
    all_downloaded.extend(await extract_ace_clinical_guidelines())

    print("\n[2/6] Downloading ACE CUES resources...")
    all_downloaded.extend(await extract_ace_cues())

    print("\n[3/6] Downloading ACE Drug Guidances...")
    all_downloaded.extend(await extract_ace_drug_guidances())

    print("\n[4/6] Downloading HealthHub content...")
    all_downloaded.extend(await extract_healthhub_content())

    print("\n[5/6] Downloading HPP Guidelines...")
    all_downloaded.extend(await extract_hpp_guidelines())

    print("\n[6/6] Downloading International Guidelines (NHS/NICE)...")
    all_downloaded.extend(await extract_international_guidelines())

    print("\n" + "=" * 60)
    print(f"Download complete! Total files in data/raw: {len(list_downloaded_files())}")
    print("=" * 60)


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
