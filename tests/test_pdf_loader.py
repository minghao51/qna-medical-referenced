import json
from pathlib import Path
from src.pipeline.L2_pdf_loader import PDFLoader, get_documents


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
            for page in doc["pages"]:
                assert page["page"] >= 1
                assert len(page["content"]) > 0

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

    def test_no_empty_pages(self):
        loader = PDFLoader("data/raw")
        docs = loader.load_all_pdfs()
        
        for doc in docs:
            for page in doc["pages"]:
                assert len(page["content"].strip()) > 0, f"Empty content in {doc['id']} page {page['page']}"

    def test_get_documents_function(self):
        docs = get_documents()
        assert isinstance(docs, list)
        assert len(docs) > 0
