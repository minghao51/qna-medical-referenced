#!/usr/bin/env python3
"""
L2: PDF Loader - multi-pass PDF text extraction with page-level metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from pypdf import PdfReader

from src.config import DATA_RAW_DIR
from src.ingestion.artifacts import SourceArtifact, persist_source_artifact
from src.ingestion.steps.download_web import get_manifest_record_by_filename

try:  # pragma: no cover - optional dependency
    import pdfplumber
except Exception:  # pragma: no cover - optional dependency
    pdfplumber = None


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


class PDFLoader:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else DATA_RAW_DIR

    def _extract_with_pypdf(self, pdf_path: Path) -> tuple[PdfReader, list[str]]:
        reader = PdfReader(str(pdf_path))
        texts = [(page.extract_text() or "") for page in reader.pages]
        return reader, texts

    def _extract_with_pdfplumber(self, pdf_path: Path) -> list[str]:
        if pdfplumber is None:
            return []
        outputs: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                outputs.append((page.extract_text() or "").strip())
        return outputs

    def load_pdf(self, pdf_path: str) -> str:
        _, texts = self._extract_with_pypdf(Path(pdf_path))
        return "\n".join(texts)

    def load_all_pdfs(self) -> List[dict]:
        documents = []
        pdf_files = sorted(self.data_dir.glob("*.pdf"))

        for pdf_file in pdf_files:
            reader, primary_texts = self._extract_with_pypdf(pdf_file)
            fallback_texts = self._extract_with_pdfplumber(pdf_file)
            pages = []
            all_blocks: list[dict] = []
            full_text_parts: list[str] = []
            fallback_used = 0
            low_conf_pages = 0
            ocr_required_pages = 0

            for page_num, primary_text in enumerate(primary_texts, 1):
                fallback_text = (
                    fallback_texts[page_num - 1] if page_num - 1 < len(fallback_texts) else ""
                )
                replacement_chars = primary_text.count("\ufffd")
                primary_lines = _normalize_lines(primary_text)
                use_fallback = bool(fallback_text) and (
                    len(primary_text.strip()) < 120
                    or replacement_chars > 2
                    or len(primary_lines) < 2
                )
                selected_text = fallback_text if use_fallback else primary_text
                extractor = "pdfplumber" if use_fallback else "pypdf"
                if use_fallback:
                    fallback_used += 1
                line_count = len(_normalize_lines(selected_text))
                confidence = _infer_confidence(selected_text, replacement_chars, line_count)
                if confidence == "low":
                    low_conf_pages += 1
                if not selected_text.strip():
                    ocr_required_pages += 1
                structured_blocks = _build_structured_blocks(page_num, selected_text)
                all_blocks.extend(structured_blocks)
                full_text_parts.append(selected_text)
                pages.append(
                    {
                        "page": page_num,
                        "content": selected_text,
                        "extractor": extractor,
                        "char_count": len(selected_text.strip()),
                        "line_count": line_count,
                        "suspected_table_count": _suspected_table_count(selected_text),
                        "replacement_char_count": replacement_chars,
                        "confidence": confidence,
                        "ocr_required": not selected_text.strip(),
                        "structured_blocks": structured_blocks,
                        "metadata": {
                            "selected_extractor": extractor,
                            "primary_char_count": len(primary_text.strip()),
                            "fallback_char_count": len(fallback_text.strip()),
                        },
                    }
                )

            artifact = SourceArtifact(
                source_id=pdf_file.stem,
                source_path=str(pdf_file),
                source_type="pdf",
                raw_source={
                    "page_count": len(reader.pages),
                    "size_bytes": pdf_file.stat().st_size,
                },
                extracted_text="\n\n".join(full_text_parts).strip(),
                structured_blocks=all_blocks,
                best_output={
                    "extractor": "mixed" if fallback_used else "pypdf",
                    "page_count": len(reader.pages),
                    "pages": pages,
                },
                fallback_output={
                    "extractor": "pdfplumber" if pdfplumber is not None else "unavailable",
                    "page_count": len(fallback_texts),
                },
                metadata={
                    "fallback_used_pages": fallback_used,
                    "low_confidence_pages": low_conf_pages,
                    "ocr_required_pages": ocr_required_pages,
                },
            )
            persist_source_artifact(artifact)

            # Lookup manifest record for additional metadata
            manifest_record = get_manifest_record_by_filename(pdf_file.name)
            metadata = artifact.metadata.copy()
            if manifest_record:
                metadata["logical_name"] = manifest_record.get("logical_name")
                metadata["source_url"] = manifest_record.get("url")

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

        return documents


def get_documents() -> List[dict]:
    loader = PDFLoader()
    return loader.load_all_pdfs()
