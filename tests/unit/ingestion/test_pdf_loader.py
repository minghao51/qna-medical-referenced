"""Unit tests for the L2 PDF loader.

Fully offline: the tests generate small synthetic PDFs with pypdf-compatible
hand-built page streams (no real corpus in data/raw is required). One fixture
PDF includes a simple table-ish text layout to exercise table heuristics, and
one includes a poor-text page to exercise the pdfplumber fallback path.
"""

from pathlib import Path

import pytest

from src.config.context import get_runtime_state
from src.ingestion.runtime_config import (
    PdfRuntimeConfig,
    RuntimeConfig,
    apply_runtime_config,
)
from src.ingestion.steps import load_pdfs
from src.ingestion.steps.load_pdfs import (
    PDFLoader,
    get_documents,
    get_pdf_extractor_strategy,
    get_pdf_table_extractor,
)


def _set_pdf_extractors(strategy: str, table_extractor: str) -> None:
    """Write the PDF extractor overlay directly (setters died in roadmap P3.3)."""
    state = get_runtime_state()
    state.pdf_extractor_strategy = strategy
    state.pdf_table_extractor = table_extractor

# --- synthetic PDF generation -------------------------------------------------


def _esc(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _write_pdf(path: Path, pages_lines: list[list[str]]) -> None:
    """Write a minimal valid PDF whose pages draw the given text lines.

    Hand-built (pypdf is a read dependency, not a write API) with an
    uncompressed Helvetica content stream so extract_text() recovers the lines.
    """
    bodies: dict[int, bytes] = {1: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
    content_ids: list[int] = []
    next_id = 2
    for lines in pages_lines:
        parts = [b"BT /F1 11 Tf 72 720 Td 14 TL"]
        for line in lines:
            parts.append(f"({_esc(line)}) Tj T*".encode("latin-1", "replace"))
        parts.append(b"ET")
        stream = b"\n".join(parts)
        bodies[next_id] = (
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
        content_ids.append(next_id)
        next_id += 1
    pages_id = next_id
    next_id += 1
    for content_id in content_ids:
        bodies[next_id] = (
            b"<< /Type /Page /Parent "
            + str(pages_id).encode()
            + b" 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 1 0 R >> >>"
            b" /Contents " + str(content_id).encode() + b" 0 R >>"
        )
        next_id += 1
    kids = b" ".join(f"{pid} 0 R".encode() for pid in range(pages_id + 1, next_id))
    bodies[pages_id] = (
        b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(content_ids)).encode() + b" >>"
    )
    catalog_id = next_id
    bodies[catalog_id] = b"<< /Type /Catalog /Pages " + str(pages_id).encode() + b" 0 R >>"

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj_id in sorted(bodies):
        offsets.append(len(out))
        out += str(obj_id).encode() + b" 0 obj\n" + bodies[obj_id] + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(catalog_id + 1).encode() + b"\n0000000000 65535 f \n"
    for obj_id in range(1, catalog_id + 1):
        out += f"{offsets[obj_id]:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size "
        + str(catalog_id + 1).encode()
        + b" /Root "
        + str(catalog_id).encode()
        + b" 0 R >>\nstartxref\n"
        + str(xref_pos).encode()
        + b"\n%%EOF\n"
    )
    path.write_bytes(bytes(out))


LIPID_PAGE_1 = [
    "Lipid Management Guideline",
    "LDL cholesterol should be monitored regularly in adults.",
    "Target LDL is below 2.6 mmol/L for high risk patients.",
    "Statin therapy is recommended when targets are not met.",
    "Repeat the lipid panel after eight to twelve weeks.",
]
# Short page (<120 chars, <2 meaningful margins) to trigger pdfplumber fallback.
LIPID_PAGE_2 = ["Risk factors:", "smoking, diabetes"]
LIPID_PAGE_3 = [
    "Parameter | Target | Note",
    "LDL | < 2.6 mmol/L | high risk",
    "HbA1c | < 7.0% | monitor quarterly",
    "Blood pressure | < 140/90 | recheck in 3 months",
]
TABLE_PAGE = [
    "Screening Panel | Frequency | Notes",
    "Lipid profile | every 5 years | fasting sample preferred",
    "Fasting glucose | every 3 years | confirm with HbA1c",
    "Blood pressure | every visit | rest for five minutes first",
]


@pytest.fixture
def pdf_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Synthetic corpus in tmp_path; artifact persistence is a no-op."""
    _write_pdf(
        tmp_path / "Lipid_Management.pdf",
        [LIPID_PAGE_1, LIPID_PAGE_2, LIPID_PAGE_3],
    )
    _write_pdf(tmp_path / "Screening_Table.pdf", [TABLE_PAGE])
    # Second page is truly blank to exercise ocr_required marking.
    _write_pdf(tmp_path / "Blank_Notes.pdf", [["Notes"], []])
    monkeypatch.setattr(load_pdfs, "persist_source_artifact", lambda artifact: None)
    return tmp_path


@pytest.fixture
def baseline_extractors():
    yield
    _set_pdf_extractors("pypdf_pdfplumber", "heuristic")


class TestPDFLoader:
    def test_load_all_pdfs_returns_list(self, pdf_dir):
        docs = PDFLoader(pdf_dir).load_all_pdfs()
        assert isinstance(docs, list)
        assert len(docs) == 3

    def test_pdf_document_structure(self, pdf_dir):
        docs = PDFLoader(pdf_dir).load_all_pdfs()

        for doc in docs:
            assert "id" in doc
            assert "source" in doc
            assert "pages" in doc
            assert isinstance(doc["pages"], list)

    def test_page_content_extraction(self, pdf_dir):
        docs = PDFLoader(pdf_dir).load_all_pdfs()

        for doc in docs:
            for page in doc["pages"]:
                assert "page" in page
                assert "content" in page
                assert isinstance(page["page"], int)
                assert isinstance(page["content"], str)

    def test_metadata_attachment(self, pdf_dir):
        docs = PDFLoader(pdf_dir).load_all_pdfs()

        for doc in docs:
            assert doc["source"].endswith(".pdf")
            assert doc["source_type"] == "pdf"
            for page in doc["pages"]:
                assert page["page"] >= 1
                assert "extractor" in page
                assert "confidence" in page
                assert "ocr_required" in page

    def test_extraction_integrity_sample(self, pdf_dir):
        docs = PDFLoader(pdf_dir).load_all_pdfs()

        found_lipid = False
        for doc in docs:
            if "Lipid" in doc.get("source", ""):
                found_lipid = True
                text = " ".join(p["content"] for p in doc["pages"])
                assert "LDL" in text or "cholesterol" in text.lower()
                break
        assert found_lipid, "Expected to find lipid management document"

    def test_page_numbers_sequential(self, pdf_dir):
        docs = PDFLoader(pdf_dir).load_all_pdfs()

        for doc in docs:
            page_nums = [p["page"] for p in doc["pages"]]
            assert page_nums == sorted(page_nums), "Pages should be sequential"

    def test_empty_pages_are_explicitly_marked(self, pdf_dir):
        docs = PDFLoader(pdf_dir).load_all_pdfs()

        for doc in docs:
            for page in doc["pages"]:
                if len(page["content"].strip()) == 0:
                    assert page["ocr_required"] is True

    def test_get_documents_function(self, pdf_dir, monkeypatch):
        monkeypatch.setattr(load_pdfs, "DATA_RAW_DIR", pdf_dir)
        docs = get_documents()
        assert isinstance(docs, list)
        assert len(docs) == 3

    def test_pdfplumber_runs_lazily_only_for_poor_pages(self, pdf_dir, monkeypatch):
        calls = []

        def spy(self, path):
            calls.append(Path(path).name)
            return [" ".join(LIPID_PAGE_2)] * 3

        monkeypatch.setattr(PDFLoader, "_extract_with_pdfplumber", spy)
        docs = PDFLoader(pdf_dir).load_all_pdfs()

        # Exactly one pdfplumber parse per file that has a poor page
        # (Lipid_Management: short page 2; Blank_Notes: blank page 2) and none
        # for the good-text Screening_Table file.
        assert calls.count("Lipid_Management.pdf") == 1
        assert calls.count("Blank_Notes.pdf") == 1
        assert "Screening_Table.pdf" not in calls
        poor_page = next(d for d in docs if "Lipid" in d["source"])["pages"][1]
        assert poor_page["extractor"] == "pdfplumber"
        good_page = next(d for d in docs if "Lipid" in d["source"])["pages"][0]
        assert good_page["extractor"] == "pypdf"

    def test_pdfplumber_skipped_entirely_when_pypdf_text_is_good(self, tmp_path, monkeypatch):
        _write_pdf(tmp_path / "Good_Text.pdf", [LIPID_PAGE_1, TABLE_PAGE])
        monkeypatch.setattr(load_pdfs, "persist_source_artifact", lambda artifact: None)

        def boom(self, path):
            raise AssertionError("pdfplumber must not run when pypdf text is fine")

        monkeypatch.setattr(PDFLoader, "_extract_with_pdfplumber", boom)
        docs = PDFLoader(tmp_path).load_all_pdfs()
        assert len(docs) == 1
        assert all(p["extractor"] == "pypdf" for p in docs[0]["pages"])


class _FakeCamelotTable:
    def __init__(self, rows: list[list[str]]):
        self.data = rows
        self.accuracy = 99.0
        self.whitespace = []


class TestPDFExtractorStrategy:
    def test_apply_runtime_config_pdf_strategy_valid(self, baseline_extractors):
        apply_runtime_config(RuntimeConfig(pdf=PdfRuntimeConfig(extractor_strategy="pymupdf_pdfplumber")))
        assert get_pdf_extractor_strategy() == "pymupdf_pdfplumber"

    def test_apply_runtime_config_invalid_strategy_defaults_to_baseline(self, baseline_extractors):
        apply_runtime_config(RuntimeConfig(pdf=PdfRuntimeConfig(extractor_strategy="invalid_strategy")))
        assert get_pdf_extractor_strategy() == "pypdf_pdfplumber"

    def test_apply_runtime_config_table_extractor_valid(self, baseline_extractors):
        apply_runtime_config(RuntimeConfig(pdf=PdfRuntimeConfig(table_extractor="camelot")))
        assert get_pdf_table_extractor() == "camelot"

    def test_apply_runtime_config_invalid_table_extractor_defaults_to_heuristic(
        self, baseline_extractors
    ):
        apply_runtime_config(RuntimeConfig(pdf=PdfRuntimeConfig(table_extractor="invalid")))
        assert get_pdf_table_extractor() == "heuristic"

    def test_extractor_strategy_persisted_in_metadata(self, pdf_dir, baseline_extractors):
        loader = PDFLoader(pdf_dir)
        _set_pdf_extractors("pypdf_pdfplumber", "camelot")
        docs = loader.load_all_pdfs()
        assert len(docs) > 0
        for doc in docs:
            meta = doc["metadata"]
            assert meta.get("pdf_extractor_strategy") == "pypdf_pdfplumber"
            assert meta.get("pdf_table_extractor") == "camelot"

    def test_camelot_pages_tracked_in_metadata(self, pdf_dir, baseline_extractors):
        loader = PDFLoader(pdf_dir)
        _set_pdf_extractors("pypdf_pdfplumber", "camelot")
        docs = loader.load_all_pdfs()
        assert len(docs) > 0
        for doc in docs:
            meta = doc["metadata"]
            assert "camelot_table_pages" in meta
            assert "camelot_total_rows" in meta
            assert isinstance(meta["camelot_table_pages"], int)
            assert isinstance(meta["camelot_total_rows"], int)

    def test_per_page_camelot_metadata_reflects_actual_outcome(
        self, tmp_path, monkeypatch, baseline_extractors
    ):
        """camelot_table_pages per page must mirror real extraction outcome.

        Regression: pages where camelot was attempted (suspicion > 0) but found
        nothing used to report 1; only pages with actual camelot blocks count.
        """
        _write_pdf(tmp_path / "Tables.pdf", [LIPID_PAGE_3, LIPID_PAGE_3])
        monkeypatch.setattr(load_pdfs, "persist_source_artifact", lambda artifact: None)
        # Enable the camelot code path even though the optional dep is absent.
        monkeypatch.setattr(load_pdfs, "camelot", object())
        _set_pdf_extractors("pypdf_pdfplumber", "camelot")

        def fake_extract(self, pdf_path, page_num):
            # Camelot only succeeds on page 2; page 1 attempt finds nothing.
            if page_num == 2:
                return [
                    _FakeCamelotTable(
                        [["Parameter", "Target"], ["LDL", "< 2.6"], ["HbA1c", "< 7.0"]]
                    )
                ]
            return None

        monkeypatch.setattr(PDFLoader, "_extract_tables_camelot", fake_extract)

        docs = PDFLoader(tmp_path).load_all_pdfs()
        assert len(docs) == 1
        page1, page2 = docs[0]["pages"]
        # Both pages are table-suspicious...
        assert page1["suspected_table_count"] > 0
        assert page2["suspected_table_count"] > 0
        # ...but only page 2 actually produced camelot blocks.
        assert page1["metadata"]["camelot_table_pages"] == 0
        assert page2["metadata"]["camelot_table_pages"] == 1
        assert any("camelot" in str(b.get("id", "")) for b in page2["structured_blocks"])
        # The aggregate matches the sum of per-page outcomes.
        meta = docs[0]["metadata"]
        assert meta["camelot_table_pages"] == 1
        assert meta["camelot_total_rows"] == 3
