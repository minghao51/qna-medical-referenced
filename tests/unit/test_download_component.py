import importlib
from pathlib import Path
from unittest.mock import patch


def _import_download_module():
    with patch.dict("sys.modules", {}):
        return importlib.import_module("src.ingestion.components.01_download")


class TestBronzeDataPath:
    def test_returns_expected_path(self):
        dc = _import_download_module()
        assert dc.bronze_data_path(Path("/project")) == "/project/data/01_bronze"


class TestDownloadsDir:
    def test_returns_expected_path(self):
        dc = _import_download_module()
        assert dc.downloads_dir("/project/data/01_bronze") == "/project/data/01_bronze/downloads"


class TestRawPdfsDir:
    def test_returns_expected_path(self):
        dc = _import_download_module()
        assert dc.raw_pdfs_dir("/data/downloads") == "/data/downloads/pdf"


class TestRawHtmlDir:
    def test_returns_expected_path(self):
        dc = _import_download_module()
        assert dc.raw_html_dir("/data/downloads") == "/data/downloads/html"


class TestRawMarkdownDir:
    def test_returns_expected_path(self):
        dc = _import_download_module()
        assert dc.raw_markdown_dir("/data/downloads") == "/data/downloads/markdown"


class TestArtifactsDir:
    def test_returns_expected_path(self):
        dc = _import_download_module()
        assert dc.artifacts_dir("/data/01_bronze") == "/data/01_bronze/artifacts"


class TestAllWebDownloads:
    def test_returns_html_files(self, tmp_path):
        dc = _import_download_module()
        html_dir = tmp_path / "html"
        html_dir.mkdir()
        (html_dir / "page1.html").write_text("<html></html>")
        (html_dir / "page2.html").write_text("<html></html>")
        (html_dir / "readme.txt").write_text("not html")

        result = dc.all_web_downloads(str(html_dir))
        assert len(result) == 2
        assert all(r.endswith(".html") for r in result)

    def test_returns_empty_for_empty_dir(self, tmp_path):
        dc = _import_download_module()
        html_dir = tmp_path / "empty"
        html_dir.mkdir()
        assert dc.all_web_downloads(str(html_dir)) == []


class TestAllPdfDownloads:
    def test_returns_pdf_files(self, tmp_path):
        dc = _import_download_module()
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir()
        (pdf_dir / "doc1.pdf").write_bytes(b"%PDF")
        (pdf_dir / "doc2.pdf").write_bytes(b"%PDF")
        (pdf_dir / "notes.txt").write_text("not pdf")

        result = dc.all_pdf_downloads(str(pdf_dir))
        assert len(result) == 2
        assert all(r.endswith(".pdf") for r in result)

    def test_returns_empty_for_empty_dir(self, tmp_path):
        dc = _import_download_module()
        pdf_dir = tmp_path / "empty"
        pdf_dir.mkdir()
        assert dc.all_pdf_downloads(str(pdf_dir)) == []
