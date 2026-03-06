#!/usr/bin/env python3
"""
L1: Convert HTML files to structured markdown artifacts for RAG processing.
Reads from data/raw/*.html and converts to data/raw/*.md.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup

from src.config import DATA_RAW_DIR
from src.ingestion.artifacts import SourceArtifact, persist_source_artifact
from src.ingestion.steps.download_web import get_manifest_alias_filenames

try:  # pragma: no cover - optional dependency
    import trafilatura
except Exception:  # pragma: no cover - optional dependency
    trafilatura = None

DATA_DIR = DATA_RAW_DIR
PAGE_CLASSIFICATION_ENABLED = True

_REMOVAL_SELECTORS = [
    "nav",
    "footer",
    "header",
    "aside",
    "script",
    "style",
    "noscript",
    "form",
    '[role="navigation"]',
    '[aria-label*="breadcrumb" i]',
    '[class*="cookie" i]',
    '[id*="cookie" i]',
    '[class*="breadcrumb" i]',
    '[class*="share" i]',
    '[class*="social" i]',
]
_BOILERPLATE_TERMS = {
    "cookie",
    "privacy",
    "terms",
    "navigation",
    "subscribe",
    "feedback",
    "share",
    "scamshield",
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_tracking(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _hash_text(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()[:16]


def _trafilatura_extract(html_content: str) -> tuple[str, dict[str, Any]]:
    if trafilatura is None:
        return "", {"extractor": "trafilatura", "available": False}
    markdown = trafilatura.extract(
        html_content,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        no_fallback=False,
    ) or ""
    return markdown.strip(), {"extractor": "trafilatura", "available": True}


def _remove_noise(soup: BeautifulSoup) -> None:
    for selector in _REMOVAL_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()


def _classify_page(soup: BeautifulSoup, visible_text: str) -> str:
    if not PAGE_CLASSIFICATION_ENABLED:
        return "article"
    nav_links = len(soup.select("nav a, header a"))
    headings = len(soup.find_all(re.compile(r"^h[1-6]$")))
    faq_markers = len(re.findall(r"\?$", visible_text, flags=re.MULTILINE))
    list_items = len(soup.find_all("li"))
    if faq_markers >= 2:
        return "faq"
    if nav_links >= 15 and len(visible_text) < 5000:
        return "navigation-heavy"
    if list_items >= 12 and headings <= 3:
        return "index/listing"
    return "article"


def _collect_structured_blocks(soup: BeautifulSoup) -> list[dict[str, Any]]:
    body = soup.find("main") or soup.find("article") or soup.find("body") or soup
    blocks: list[dict[str, Any]] = []
    section_stack: list[str] = []
    block_index = 0

    for node in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table"], recursive=True):
        tag = node.name or ""
        text = ""
        content_type = "paragraph"
        if tag.startswith("h"):
            level = int(tag[1])
            text = _normalize_text(node.get_text(" ", strip=True))
            if not text:
                continue
            section_stack = section_stack[: max(0, level - 1)]
            section_stack.append(text)
            content_type = "heading"
        elif tag in {"ul", "ol"}:
            items = [_normalize_text(li.get_text(" ", strip=True)) for li in node.find_all("li", recursive=False)]
            items = [item for item in items if item]
            if not items:
                continue
            text = "\n".join(f"- {item}" for item in items)
            content_type = "list"
        elif tag == "table":
            rows = []
            for row in node.find_all("tr"):
                cols = [_normalize_text(col.get_text(" ", strip=True)) for col in row.find_all(["th", "td"])]
                cols = [col for col in cols if col]
                if cols:
                    rows.append(cols)
            if not rows:
                continue
            text = "\n".join(" | ".join(row) for row in rows)
            content_type = "table"
        else:
            text = _normalize_text(node.get_text(" ", strip=True))

        if not text:
            continue
        blocks.append(
            {
                "id": f"html_block_{block_index}",
                "block_type": content_type,
                "text": text,
                "section_path": list(section_stack),
                "metadata": {"tag": tag},
            }
        )
        block_index += 1
    return blocks


def _markdown_from_blocks(blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for block in blocks:
        block_type = block.get("block_type")
        text = str(block.get("text", "")).strip()
        if not text:
            continue
        if block_type == "heading":
            depth = max(1, min(6, len(block.get("section_path") or [1])))
            lines.append(f"{'#' * depth} {text}")
        elif block_type == "table":
            rows = [row for row in text.splitlines() if row.strip()]
            if rows:
                first = [cell.strip() for cell in rows[0].split("|")]
                header = " | ".join(first)
                divider = " | ".join(["---"] * len(first))
                lines.extend([f"| {header} |", f"| {divider} |"])
                for row in rows[1:]:
                    vals = " | ".join(cell.strip() for cell in row.split("|"))
                    lines.append(f"| {vals} |")
        else:
            lines.append(text)
        lines.append("")
    return "\n".join(lines).strip()


def _visible_text(soup: BeautifulSoup) -> str:
    return soup.get_text("\n", strip=True)


def _density(text: str, html_content: str) -> float:
    return len(_normalize_text(text)) / max(1, len(html_content))


def _boilerplate_ratio(text: str) -> float:
    lowered = text.lower()
    hits = sum(lowered.count(term) for term in _BOILERPLATE_TERMS)
    return hits / max(1, len(lowered))


def _fallback_extract(html_content: str) -> dict[str, Any]:
    soup = BeautifulSoup(html_content, "html.parser")
    _remove_noise(soup)
    visible_text = _visible_text(soup)
    page_type = _classify_page(soup, visible_text)
    blocks = _collect_structured_blocks(soup)
    markdown = _markdown_from_blocks(blocks)
    return {
        "extractor": "beautifulsoup",
        "page_type": page_type,
        "visible_text": visible_text,
        "structured_blocks": blocks,
        "markdown": markdown,
    }


def _should_use_fallback(primary_markdown: str, page_type: str, html_content: str) -> bool:
    if not primary_markdown.strip():
        return True
    if page_type in {"index/listing", "navigation-heavy"}:
        return True
    if _density(primary_markdown, html_content) < 0.02:
        return True
    if _boilerplate_ratio(primary_markdown) > 0.02:
        return True
    if len(re.findall(r"^#{1,6}\s", primary_markdown, flags=re.MULTILINE)) == 0 and len(primary_markdown) > 250:
        return True
    return False


def _compute_global_boilerplate_hashes(html_files: list[Path]) -> set[str]:
    counts: Counter[str] = Counter()
    for html_path in html_files:
        raw = html_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(raw, "html.parser")
        _remove_noise(soup)
        for node in soup.find_all(["p", "li", "div", "span"]):
            text = _normalize_text(node.get_text(" ", strip=True))
            if len(text) < 20:
                continue
            counts[_hash_text(text)] += 1
    threshold = max(2, len(html_files) // 3) if html_files else 2
    return {key for key, count in counts.items() if count >= threshold}


def _drop_repeated_boilerplate(blocks: list[dict[str, Any]], repeated_hashes: set[str]) -> list[dict[str, Any]]:
    filtered = []
    for block in blocks:
        text = str(block.get("text", ""))
        if _hash_text(text) in repeated_hashes and _boilerplate_ratio(text) > 0:
            continue
        filtered.append(block)
    return filtered


def convert_html_to_md(html_path: Path, force: bool = False, repeated_hashes: set[str] | None = None) -> Path | None:
    """Convert one HTML file to markdown and persist its artifact."""
    md_path = html_path.with_suffix(".md")
    if md_path.exists() and not force:
        return None

    html_content = html_path.read_text(encoding="utf-8", errors="ignore")
    raw_soup = BeautifulSoup(html_content, "html.parser")
    page_type = _classify_page(raw_soup, _visible_text(raw_soup))

    primary_markdown, primary_meta = _trafilatura_extract(html_content)
    fallback = _fallback_extract(html_content)
    blocks = list(fallback["structured_blocks"])
    if repeated_hashes:
        blocks = _drop_repeated_boilerplate(blocks, repeated_hashes)
    fallback["structured_blocks"] = blocks
    fallback["markdown"] = _markdown_from_blocks(blocks)

    use_fallback = _should_use_fallback(primary_markdown, page_type, html_content)
    markdown_content = fallback["markdown"] if use_fallback else primary_markdown
    selected_extractor = "beautifulsoup" if use_fallback else "trafilatura"

    lines = [line.rstrip() for line in markdown_content.splitlines()]
    cleaned_lines: list[str] = []
    prev_empty = False
    for line in lines:
        normalized = line.strip()
        if normalized.startswith("[") and "](" in normalized:
            link_text = normalized.split("](", 1)[0].lstrip("[")
            link_url = normalized.split("](", 1)[1].rstrip(")")
            line = f"[{link_text}]({_strip_tracking(link_url)})"
        is_empty = not line.strip()
        if is_empty and prev_empty:
            continue
        cleaned_lines.append(line)
        prev_empty = is_empty
    markdown_content = "\n".join(cleaned_lines).strip()

    artifact = SourceArtifact(
        source_id=html_path.stem,
        source_path=str(html_path),
        source_type="html",
        raw_source={"page_type": page_type, "size_bytes": html_path.stat().st_size},
        extracted_text=fallback["visible_text"],
        structured_blocks=blocks,
        markdown_text=markdown_content,
        best_output={"extractor": selected_extractor, "markdown": markdown_content},
        fallback_output={"extractor": fallback["extractor"], "markdown": fallback["markdown"]},
        metadata={
            "page_type": page_type,
            "selected_extractor": selected_extractor,
            "primary_extractor": primary_meta,
            "text_density": _density(markdown_content, html_content),
            "boilerplate_ratio": _boilerplate_ratio(markdown_content),
            "indexable": page_type in {"article", "faq"},
            "heading_count": len([b for b in blocks if b.get("block_type") == "heading"]),
            "table_count": len([b for b in blocks if b.get("block_type") == "table"]),
        },
    )
    persist_source_artifact(artifact)
    md_path.write_text(markdown_content, encoding="utf-8")
    return md_path


def set_page_classification_enabled(enabled: bool) -> None:
    global PAGE_CLASSIFICATION_ENABLED
    PAGE_CLASSIFICATION_ENABLED = bool(enabled)


def get_html_files() -> list[Path]:
    """Get all non-alias HTML files in data/raw."""
    alias_names = get_manifest_alias_filenames()
    return [p for p in sorted(DATA_DIR.glob("*.html")) if p.name not in alias_names]


def main(force: bool = False):
    """Convert all HTML files to Markdown."""
    print("=" * 60)
    print("L1: HTML to Markdown Converter")
    print("=" * 60)
    print(f"\nData directory: {DATA_DIR}")
    print()

    html_files = get_html_files()
    repeated_hashes = _compute_global_boilerplate_hashes(html_files)
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
        result = convert_html_to_md(html_path, force=force, repeated_hashes=repeated_hashes)
        if result:
            print(f"  -> Saved: {result.name}")
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
