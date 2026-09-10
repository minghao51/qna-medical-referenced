#!/usr/bin/env python3
"""
L2: PDF Loader - multi-pass PDF text extraction with page-level metadata.
Supports pluggable extractor strategies: pypdf/pdfplumber and PyMuPDF/pdfplumber.
Supports Camelot for structured table extraction.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.config import DATA_RAW_DIR
from src.config.context import get_runtime_state
from src.core.source_metadata import build_document_source_metadata
from src.ingestion.artifacts import SourceArtifact, persist_source_artifact
from src.ingestion.steps.download_web import get_manifest_record_by_filename

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    pdfplumber: Any = importlib.import_module("pdfplumber")
except Exception:
    logger.debug("pdfplumber not available")
    pdfplumber = None

try:  # pragma: no cover - optional dependency
    pymupdf: Any = importlib.import_module("pymupdf")
except Exception:
    logger.debug("pymupdf not available")
    pymupdf = None

try:  # pragma: no cover - optional dependency
    camelot: Any = importlib.import_module("camelot")
except Exception:
    logger.debug("camelot not available")
    camelot = None

try:  # pragma: no cover - optional dependency
    TableList: Any = importlib.import_module("camelot.core").TableList
except Exception:
    logger.debug("camelot.core.TableList not available")
    TableList = Any


def read_pdf_with_pypdf(pdf_path: str | Path) -> tuple[PdfReader, list[str]]:
    """Extract per-page text with pypdf; shared by the L2 and L4 loaders."""
    reader = PdfReader(str(pdf_path))
    texts = [(page.extract_text() or "") for page in reader.pages]
    return reader, texts


def _pdf_extractor_strategy() -> str:
    return str(get_runtime_state().pdf_extractor_strategy)


def _pdf_table_extractor() -> str:
    return str(get_runtime_state().pdf_table_extractor)


def get_pdf_extractor_strategy() -> str:
    return _pdf_extractor_strategy()


def get_pdf_table_extractor() -> str:
    return _pdf_table_extractor()


def _normalize_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _suspected_table_count(text: str) -> int:
    count = 0
    for line in _normalize_lines(text):
        if line.count("|") >= 2:
            count += 1
            continue
        if len(line.split()) >= 4 and "  " in line:
            count += 1
    return count


def _infer_confidence(text: str, replacement_chars: int, line_count: int) -> str:
    stripped_len = len(text.strip())
    if stripped_len >= 400 and replacement_chars == 0 and line_count >= 3:
        return "high"
    if stripped_len >= 120 and replacement_chars <= 2:
        return "medium"
    return "low"


def _build_structured_blocks(page_num: int, text: str) -> list[dict]:
    lines = _normalize_lines(text)
    blocks: list[dict] = []
    block_index = 0
    section_path: list[str] = []
    buffer: list[str] = []
    current_type = "paragraph"

    def flush() -> None:
        nonlocal buffer, block_index, current_type
        chunk = "\n".join(buffer).strip()
        if not chunk:
            buffer = []
            return
        blocks.append(
            {
                "id": f"pdf_p{page_num}_block_{block_index}",
                "block_type": current_type,
                "text": chunk,
                "section_path": list(section_path),
                "metadata": {"page": page_num},
            }
        )
        block_index += 1
        buffer = []

    for line in lines:
        is_heading = len(line) < 100 and (line.isupper() or line.endswith(":"))
        is_list = line.startswith(("-", "*", "\u2022"))
        is_table = line.count("|") >= 2 or ("  " in line and len(line.split()) >= 4)
        next_type = "paragraph"
        if is_heading:
            flush()
            section_path = [line.rstrip(":")]
            blocks.append(
                {
                    "id": f"pdf_p{page_num}_block_{block_index}",
                    "block_type": "heading",
                    "text": line.rstrip(":"),
                    "section_path": list(section_path),
                    "metadata": {"page": page_num},
                }
            )
            block_index += 1
            continue
        if is_table:
            next_type = "table"
        elif is_list:
            next_type = "list"

        if buffer and next_type != current_type:
            flush()
        current_type = next_type
        buffer.append(line)

    flush()
    return blocks


def _build_camelot_table_blocks(
    page_num: int, tables: TableList, section_path: list[str]
) -> list[dict]:
    blocks: list[dict] = []
    for idx, table in enumerate(tables):
        table_data = table.data
        rows = table_data if isinstance(table_data, list) else []
        if not rows or len(rows) < 2:
            continue
        lines = []
        for row in rows:
            cleaned = [cell.strip() if cell else "" for cell in row]
            cleaned = [c for c in cleaned if c]
            if cleaned:
                lines.append(" | ".join(cleaned))
        if len(lines) < 2:
            continue
        text = "\n".join(lines)
        blocks.append(
            {
                "id": f"pdf_p{page_num}_block_camelot_{idx}",
                "block_type": "table",
                "text": text,
                "section_path": list(section_path),
                "metadata": {
                    "page": page_num,
                    "extractor": "camelot",
                    "table_metadata": {
                        "rows": len(rows),
                        "cols": len(rows[0]) if rows else 0,
                        "accuracy": getattr(table, "accuracy", None),
                        "whitespace": getattr(table, "whitespace", None),
                    },
                },
            }
        )
    return blocks


class PDFLoader:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else DATA_RAW_DIR

    def _extract_with_pypdf(self, pdf_path: Path) -> tuple[PdfReader, list[str]]:
        return read_pdf_with_pypdf(pdf_path)

    def _extract_with_pymupdf(self, pdf_path: Path) -> tuple[Any, list[str]]:
        reader = pymupdf.open(str(pdf_path))
        try:
            texts = [page.get_text("text") or "" for page in reader]
        finally:
            reader.close()
        return reader, texts

    def _extract_with_pdfplumber(self, pdf_path: Path) -> list[str]:
        if pdfplumber is None:
            return []
        outputs: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                outputs.append((page.extract_text() or "").strip())
        return outputs

    def _extract_primary(self, pdf_path: Path) -> tuple[Any, list[str]]:
        if _pdf_extractor_strategy() == "pymupdf_pdfplumber" and pymupdf is not None:
            return self._extract_with_pymupdf(pdf_path)
        return self._extract_with_pypdf(pdf_path)

    def _extract_tables_camelot(self, pdf_path: Path, page_num: int) -> TableList | None:
        if _pdf_table_extractor() != "camelot" or camelot is None:
            return None
        try:
            tables = camelot.read_pdf(str(pdf_path), pages=str(page_num), flavor="lattice")
            return tables if tables and len(tables) > 0 else None
        except Exception as e:
            logger.debug(
                "Camelot table extraction failed for %s page %s: %s", pdf_path, page_num, e
            )
            return None

    def load_pdf(self, pdf_path: str) -> str:
        _, texts = self._extract_primary(Path(pdf_path))
        return "\n".join(texts)

    def load_all_pdfs(self) -> list[dict]:
        documents = []
        pdf_files = sorted(self.data_dir.glob("*.pdf"))

        for pdf_file in pdf_files:
            # Per-file isolation: one corrupt/unreadable PDF must not abort the
            # whole ingestion run — log and continue with the remaining files.
            try:
                reader, primary_texts = self._extract_primary(pdf_file)
                # pdfplumber is the slowest extractor: parse it lazily, only
                # once at least one page actually triggers the fallback
                # criteria below (instead of eagerly for every file).
                fallback_texts: list[str] | None = None

                def fallback_for(page_index: int, _pdf_file: Path = pdf_file) -> str:
                    nonlocal fallback_texts
                    if fallback_texts is None:
                        fallback_texts = self._extract_with_pdfplumber(_pdf_file)
                    return fallback_texts[page_index] if page_index < len(fallback_texts) else ""

                pages = []
                all_blocks: list[dict] = []
                full_text_parts: list[str] = []
                fallback_used = 0
                low_conf_pages = 0
                ocr_required_pages = 0
                camelot_table_pages = 0
                camelot_total_rows = 0

                for page_num, primary_text in enumerate(primary_texts, 1):
                    replacement_chars = primary_text.count("\ufffd")
                    primary_lines = _normalize_lines(primary_text)
                    fallback_text = ""
                    if (
                        len(primary_text.strip()) < 120
                        or replacement_chars > 2
                        or len(primary_lines) < 2
                    ):
                        fallback_text = fallback_for(page_num - 1)
                    use_fallback = bool(fallback_text)
                    selected_text = fallback_text if use_fallback else primary_text
                    extractor = (
                        "pdfplumber"
                        if use_fallback
                        else (
                            "pymupdf"
                            if _pdf_extractor_strategy() == "pymupdf_pdfplumber"
                            else "pypdf"
                        )
                    )
                    if use_fallback:
                        fallback_used += 1
                    line_count = len(_normalize_lines(selected_text))
                    confidence = _infer_confidence(selected_text, replacement_chars, line_count)
                    if confidence == "low":
                        low_conf_pages += 1
                    if not selected_text.strip():
                        ocr_required_pages += 1

                    section_path: list[str] = []
                    structured_blocks = _build_structured_blocks(page_num, selected_text)

                    # Computed once per page and reused for the camelot trigger,
                    # the page metadata, and the artifact aggregate below.
                    suspected_table_count = _suspected_table_count(selected_text)
                    page_camelot_table_pages = 0
                    if _pdf_table_extractor() == "camelot" and camelot is not None:
                        if suspected_table_count > 0:
                            camelot_tables = self._extract_tables_camelot(pdf_file, page_num)
                            if camelot_tables and len(camelot_tables) > 0:
                                camelot_blocks = _build_camelot_table_blocks(
                                    page_num, camelot_tables, section_path
                                )
                                if camelot_blocks:
                                    structured_blocks.extend(camelot_blocks)
                                    camelot_table_pages += 1
                                    page_camelot_table_pages = 1
                                    for cb in camelot_blocks:
                                        tm = cb.get("metadata", {}).get("table_metadata", {})
                                        if isinstance(tm, dict):
                                            camelot_total_rows += int(tm.get("rows", 0))

                    all_blocks.extend(structured_blocks)
                    full_text_parts.append(selected_text)
                    pages.append(
                        {
                            "page": page_num,
                            "content": selected_text,
                            "extractor": extractor,
                            "char_count": len(selected_text.strip()),
                            "line_count": line_count,
                            "suspected_table_count": suspected_table_count,
                            "replacement_char_count": replacement_chars,
                            "confidence": confidence,
                            "ocr_required": not selected_text.strip(),
                            "structured_blocks": structured_blocks,
                            "metadata": {
                                "selected_extractor": extractor,
                                "primary_char_count": len(primary_text.strip()),
                                "fallback_char_count": len(fallback_text.strip()),
                                # Actual camelot outcome for this page (not the
                                # suspicion heuristic that triggered the attempt).
                                "camelot_table_pages": page_camelot_table_pages,
                            },
                        }
                    )

                artifact = SourceArtifact(
                    source_id=pdf_file.stem,
                    source_path=str(pdf_file),
                    source_type="pdf",
                    raw_source={
                        "page_count": (
                            reader.page_count
                            if hasattr(reader, "page_count")
                            else len(reader.pages)
                            if hasattr(reader, "pages") and not callable(reader.pages)
                            else len(primary_texts)
                        ),
                        "size_bytes": pdf_file.stat().st_size,
                        "pdf_extractor_strategy": _pdf_extractor_strategy(),
                        "pdf_table_extractor": _pdf_table_extractor(),
                    },
                    extracted_text="\n\n".join(full_text_parts).strip(),
                    structured_blocks=all_blocks,
                    best_output={
                        "extractor": (
                            "mixed_pymupdf"
                            if _pdf_extractor_strategy() == "pymupdf_pdfplumber"
                            and not fallback_used
                            else "pymupdf"
                            if _pdf_extractor_strategy() == "pymupdf_pdfplumber"
                            else "mixed"
                            if fallback_used
                            else "pypdf"
                        ),
                        "page_count": (
                            reader.page_count
                            if hasattr(reader, "page_count")
                            else len(reader.pages)
                            if hasattr(reader, "pages") and not callable(reader.pages)
                            else len(primary_texts)
                        ),
                        "pages": pages,
                    },
                    fallback_output={
                        "extractor": "pdfplumber" if pdfplumber is not None else "unavailable",
                        "page_count": len(fallback_texts) if fallback_texts is not None else 0,
                    },
                    metadata={
                        "fallback_used_pages": fallback_used,
                        "low_confidence_pages": low_conf_pages,
                        "ocr_required_pages": ocr_required_pages,
                        "camelot_table_pages": camelot_table_pages,
                        "camelot_total_rows": camelot_total_rows,
                        "pdf_extractor_strategy": _pdf_extractor_strategy(),
                        "pdf_table_extractor": _pdf_table_extractor(),
                    },
                )
                persist_source_artifact(artifact)

                manifest_record = get_manifest_record_by_filename(pdf_file.name)
                metadata = build_document_source_metadata(
                    artifact.metadata,
                    source=pdf_file.name,
                    source_type="pdf",
                    manifest_record=manifest_record,
                    explicit_class="guideline_pdf",
                )

                documents.append(
                    {
                        "id": pdf_file.stem,
                        "source": str(pdf_file.name),
                        "source_type": "pdf",
                        "pages": pages,
                        "structured_blocks": all_blocks,
                        "metadata": metadata,
                    }
                )
            except Exception as e:
                logger.warning("Failed to load PDF %s; skipping file: %s", pdf_file, e)
                continue

        return documents


def get_documents() -> list[dict]:
    loader = PDFLoader()
    return loader.load_all_pdfs()
