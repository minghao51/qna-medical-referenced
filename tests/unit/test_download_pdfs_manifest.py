import asyncio
from pathlib import Path

from src.ingestion.steps import download_pdfs as dp
from src.ingestion.steps import download_web as dw


def test_download_pdf_if_not_exists_retries_after_prior_failure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dp, "DATA_RAW_DIR", tmp_path)
    monkeypatch.setattr(dw, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dw, "MANIFEST_PATH", tmp_path / "download_manifest.json")

    url = "https://example.com/file.pdf"
    manifest = {
        "records": [
            {
                "url": url,
                "normalized_url": dp.normalize_url(url),
                "logical_name": "prior_attempt",
                "filename": None,
                "content_hash": None,
                "status": "download_failed",
                "record_type": "pdf_download",
            }
        ]
    }
    dp._save_manifest(manifest)

    async def fake_download(_: str, timeout: int = 60):
        return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"

    monkeypatch.setattr(dp, "download_pdf", fake_download)
    result = asyncio.run(dp.download_pdf_if_not_exists(url, "example_pdf"))

    assert result is not None
    assert result.exists()
    statuses = [r["status"] for r in dp._load_manifest()["records"]]
    assert "downloaded" in statuses


def test_download_pdf_rejects_non_pdf_payload(monkeypatch):
    class FakeResponse:
        headers = {"content-type": "text/html"}
        content = b"<html>not-a-pdf</html>"

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str):
            return FakeResponse()

    monkeypatch.setattr(dp.httpx, "AsyncClient", FakeClient)
    content = asyncio.run(dp.download_pdf("https://example.com/file"))
    assert content is None
