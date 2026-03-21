import sys

from src.ingestion.steps.load_pdfs import (
    PDFLoader,
    get_documents,
    set_pdf_extractor_strategy,
    set_pdf_table_extractor,
)


def _pdf_strategy():
    return sys.modules["src.ingestion.steps.load_pdfs"].PDF_EXTRACTOR_STRATEGY


def _pdf_table_extractor():
    return sys.modules["src.ingestion.steps.load_pdfs"].PDF_TABLE_EXTRACTOR


class TestPDFLoader:
    def test_load_all_pdfs_returns_list(self):
        loader = PDFLoader("data/raw")
        docs = loader.load_all_pdfs()
        assert isinstance(docs, list)
        assert len(docs) > 0

    def test_pdf_document_structure(self):
        loader = PDFLoader("data/raw")
        docs = loader.load_all_pdfs()

        for doc in docs:
            assert "id" in doc
            assert "source" in doc
            assert "pages" in doc
            assert isinstance(doc["pages"], list)

    def test_page_content_extraction(self):
        loader = PDFLoader("data/raw")
        docs = loader.load_all_pdfs()

        for doc in docs:
            for page in doc["pages"]:
                assert "page" in page
                assert "content" in page
                assert isinstance(page["page"], int)
                assert isinstance(page["content"], str)

    def test_metadata_attachment(self):
        loader = PDFLoader("data/raw")
        docs = loader.load_all_pdfs()

        for doc in docs:
            assert doc["source"].endswith(".pdf")
            assert doc["source_type"] == "pdf"
            for page in doc["pages"]:
                assert page["page"] >= 1
                assert "extractor" in page
                assert "confidence" in page
                assert "ocr_required" in page

    def test_extraction_integrity_sample(self):
        loader = PDFLoader("data/raw")
        docs = loader.load_all_pdfs()

        found_lipid = False
        for doc in docs:
            if "Lipid" in doc.get("source", ""):
                found_lipid = True
                text = " ".join(p["content"] for p in doc["pages"])
                assert "LDL" in text or "cholesterol" in text.lower()
                break
        assert found_lipid, "Expected to find lipid management document"

    def test_page_numbers_sequential(self):
        loader = PDFLoader("data/raw")
        docs = loader.load_all_pdfs()

        for doc in docs:
            pages = doc["pages"]
            page_nums = [p["page"] for p in pages]
            assert page_nums == sorted(page_nums), "Pages should be sequential"

    def test_empty_pages_are_explicitly_marked(self):
        loader = PDFLoader("data/raw")
        docs = loader.load_all_pdfs()

        for doc in docs:
            for page in doc["pages"]:
                if len(page["content"].strip()) == 0:
                    assert page["ocr_required"] is True

    def test_get_documents_function(self):
        docs = get_documents()
        assert isinstance(docs, list)
        assert len(docs) > 0


class TestPDFExtractorStrategy:
    def test_set_pdf_extractor_strategy_valid(self):
        set_pdf_extractor_strategy("pymupdf_pdfplumber")
        assert _pdf_strategy() == "pymupdf_pdfplumber"

    def test_set_pdf_extractor_strategy_invalid_defaults_to_baseline(self):
        set_pdf_extractor_strategy("invalid_strategy")
        assert _pdf_strategy() == "pypdf_pdfplumber"

    def test_set_pdf_table_extractor_valid(self):
        set_pdf_table_extractor("camelot")
        assert _pdf_table_extractor() == "camelot"

    def test_set_pdf_table_extractor_invalid_defaults_to_heuristic(self):
        set_pdf_table_extractor("invalid")
        assert _pdf_table_extractor() == "heuristic"

    def test_extractor_strategy_persisted_in_metadata(self):
        loader = PDFLoader("data/raw")
        set_pdf_extractor_strategy("pymupdf_pdfplumber")
        set_pdf_table_extractor("camelot")
        docs = loader.load_all_pdfs()
        assert len(docs) > 0
        for doc in docs:
            meta = doc["metadata"]
            assert meta.get("pdf_extractor_strategy") == "pymupdf_pdfplumber"
            assert meta.get("pdf_table_extractor") == "camelot"
        set_pdf_extractor_strategy("pypdf_pdfplumber")
        set_pdf_table_extractor("heuristic")

    def test_camelot_pages_tracked_in_metadata(self):
        loader = PDFLoader("data/raw")
        set_pdf_table_extractor("camelot")
        docs = loader.load_all_pdfs()
        assert len(docs) > 0
        for doc in docs:
            meta = doc["metadata"]
            assert "camelot_table_pages" in meta
            assert "camelot_total_rows" in meta
            assert isinstance(meta["camelot_table_pages"], int)
            assert isinstance(meta["camelot_total_rows"], int)
        set_pdf_table_extractor("heuristic")
