#!/usr/bin/env python3
"""
L1: Convert HTML files to Markdown for RAG processing.
Reads from data/raw/*.html and converts to data/raw/*.md
Extracts only main content (removes nav, footer, scripts, etc.)
Skips conversion if target .md file already exists.
"""

import hashlib
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify as md

DATA_DIR = Path("data/raw")


def _get_file_hash(file_path: Path) -> str:
    """Get SHA256 hash of a file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]


def extract_main_content(html_content: str) -> str:
    """Extract main content from HTML, removing nav, footer, scripts, etc."""
    soup = BeautifulSoup(html_content, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    main_content = soup.find("main") or soup.find("article") or soup.find("body")

    return str(main_content) if main_content else html_content


def convert_html_to_md(html_path: Path, force: bool = False) -> Path | None:
    """Convert HTML file to Markdown. Returns None if skipped."""
    md_path = html_path.with_suffix(".md")

    if md_path.exists() and not force:
        return None

    html_content = html_path.read_text(encoding="utf-8")
    main_content = extract_main_content(html_content)
    markdown_content = md(main_content, heading_style="ATX")

    lines = markdown_content.split("\n")
    cleaned_lines = []
    prev_empty = False

    for line in lines:
        is_empty = line.strip() == ""
        if is_empty and prev_empty:
            continue
        cleaned_lines.append(line)
        prev_empty = is_empty

    markdown_content = "\n".join(cleaned_lines).strip()

    md_path.write_text(markdown_content, encoding="utf-8")
    return md_path


def get_html_files() -> list[Path]:
    """Get all HTML files in data/raw."""
    return list(DATA_DIR.glob("*.html"))


def main(force: bool = False):
    """Convert all HTML files to Markdown."""
    print("=" * 60)
    print("L1: HTML to Markdown Converter")
    print("=" * 60)
    print(f"\nData directory: {DATA_DIR}")
    print()

    html_files = get_html_files()
    print(f"Found {len(html_files)} HTML files")

    converted = 0
    skipped = 0

    for html_path in html_files:
        md_path = html_path.with_suffix(".md")

        if md_path.exists() and not force:
            print(f"Skipping (MD exists): {html_path.name}")
            skipped += 1
            continue

        print(f"Converting: {html_path.name}")
        result = convert_html_to_md(html_path, force=force)
        if result:
            print(f"  → Saved: {result.name}")
            converted += 1
        else:
            skipped += 1

    print()
    print("=" * 60)
    print(f"Converted: {converted} files")
    print(f"Skipped:   {skipped} files")
    print(f"Total MD:  {len(list(DATA_DIR.glob('*.md')))} files")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    force_mode = "--force" in sys.argv or "-f" in sys.argv
    main(force=force_mode)
