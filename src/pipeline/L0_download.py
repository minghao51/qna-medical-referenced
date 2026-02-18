#!/usr/bin/env python3
"""
L0: Download medical content from Singapore government health websites.
Saves content to data/raw directory.
Skips download if target file already exists.
"""

import asyncio
import hashlib
import re
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup

DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_file_path(url: str, extension: str = "html") -> Path:
    """Generate a filename from URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    safe_name = re.sub(r'[^\w\-]', '_', url.split('/')[-1][:50])
    if not safe_name or safe_name.endswith('_'):
        safe_name = f"content_{url_hash}"
    filename = f"{safe_name}_{url_hash}.{extension}"
    return DATA_DIR / filename


def file_exists(url: str, extension: str = "html") -> bool:
    """Check if file already exists for this URL."""
    file_path = get_file_path(url, extension)
    return file_path.exists()


async def download_url(url: str, timeout: int = 30) -> Optional[str]:
    """Download content from URL."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return None


async def download_binary(url: str, timeout: int = 60) -> Optional[bytes]:
    """Download binary content (PDF) from URL."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return None


def clean_html_to_text(html: str) -> str:
    """Extract clean text from HTML."""
    soup = BeautifulSoup(html, 'html.parser')

    for script in soup(['script', 'style', 'nav', 'footer', 'header']):
        script.decompose()

    text = soup.get_text(separator='\n')
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line and len(line) > 2]
    return '\n'.join(lines)


async def extract_ace_clinical_guidelines() -> list[str]:
    """Extract ACE Clinical Guidelines from ace-hta.gov.sg."""
    guidelines = [
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/", "ace_guidelines_index"),
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/osteoporosis--diagnosis-and-management/", "osteoporosis_guideline"),
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/major-depressive-disorder-achieving-and-sustaining-remission/", "depression_guideline"),
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/generalised-anxiety-disorder-easing-burden-and-enabling-remission/", "anxiety_guideline"),
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/management-of-chronic-coronary-syndrome/", "coronary_syndrome_guideline"),
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/promoting-smoking-cessation-and-treating-tobacco-dependence/", "smoking_cessation_guideline"),
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/chronic-obstructive-pulmonary-disease-diagnosis-and-management/", "copd_guideline"),
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/initiating-basal-insulin-in-type-2-diabetes-mellitus/", "diabetes_insulin_guideline"),
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/foot-assessment-in-patients-with-diabetes-mellitus/", "diabetes_foot_guideline"),
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/venous-thromboembolism-treating-with-the-appropriate-anticoagulant-and-duration/", "vte_guideline"),
        ("https://www.ace-hta.gov.sg/healthcare-professionals/ace-repository-for-clinical-guidelines/lipid-management-focus-on-cardiovascular-risk/", "lipid_management_guideline"),
    ]

    downloaded = []
    for url, name in guidelines:
        if file_exists(url, "html"):
            print(f"Skipping (already exists): {name}")
            continue

        print(f"Downloading: {name}")
        content = await download_url(url)
        if content:
            file_path = get_file_path(url, "html")
            file_path.write_text(content, encoding='utf-8')
            downloaded.append(str(file_path))
            print(f"  Saved: {file_path.name}")
    return downloaded


async def extract_healthhub_content() -> list[str]:
    """Extract HealthHub health conditions and screening info."""
    pages = [
        ("https://www.healthhub.sg/health-conditions/high-cholesterol", "high_cholesterol"),
        ("https://www.healthhub.sg/health-conditions/diabetes", "diabetes"),
        ("https://www.healthhub.sg/health-conditions/hypertension", "hypertension"),
        ("https://www.healthhub.sg/well-being-and-lifestyle/personal-care/type-2-screening-tests", "health_screening_tests"),
        ("https://www.healthhub.sg/programmes/healthiersg-screening/screening-faq", "healthier_sg_screening_faq"),
    ]

    downloaded = []
    for url, name in pages:
        if file_exists(url, "html"):
            print(f"Skipping (already exists): {name}")
            continue

        print(f"Downloading: {name}")
        content = await download_url(url)
        if content:
            file_path = get_file_path(url, "html")
            file_path.write_text(content, encoding='utf-8')
            downloaded.append(str(file_path))
            print(f"  Saved: {file_path.name}")
    return downloaded


async def extract_hpp_guidelines() -> list[str]:
    """Extract HPP Guidelines index page."""
    pages = [
        ("https://hpp.moh.gov.sg/guidelines/", "hpp_guidelines_index"),
    ]

    downloaded = []
    for url, name in pages:
        if file_exists(url, "html"):
            print(f"Skipping (already exists): {name}")
            continue

        print(f"Downloading: {name}")
        content = await download_url(url)
        if content:
            file_path = get_file_path(url, "html")
            file_path.write_text(content, encoding='utf-8')
            downloaded.append(str(file_path))
            print(f"  Saved: {file_path.name}")
    return downloaded


async def extract_moh_content() -> list[str]:
    """Extract MOH Singapore main page."""
    pages = [
        ("https://www.moh.gov.sg/", "moh_singapore"),
    ]

    downloaded = []
    for url, name in pages:
        if file_exists(url, "html"):
            print(f"Skipping (already exists): {name}")
            continue

        print(f"Downloading: {name}")
        content = await download_url(url)
        if content:
            file_path = get_file_path(url, "html")
            file_path.write_text(content, encoding='utf-8')
            downloaded.append(str(file_path))
            print(f"  Saved: {file_path.name}")
    return downloaded


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

    print("\n[1/4] Downloading ACE Clinical Guidelines...")
    all_downloaded.extend(await extract_ace_clinical_guidelines())

    print("\n[2/4] Downloading HealthHub content...")
    all_downloaded.extend(await extract_healthhub_content())

    print("\n[3/4] Downloading HPP Guidelines...")
    all_downloaded.extend(await extract_hpp_guidelines())

    print("\n[4/4] Downloading MOH Singapore content...")
    all_downloaded.extend(await extract_moh_content())

    print("\n" + "=" * 60)
    print(f"Download complete! Total files in data/raw: {len(list_downloaded_files())}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
