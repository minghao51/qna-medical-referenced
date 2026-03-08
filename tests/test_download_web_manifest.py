from pathlib import Path

from src.ingestion.steps import convert_html
from src.ingestion.steps import download_web as dw


def test_normalize_url_canonicalizes_trailing_slash_and_fragment():
    assert dw.normalize_url("HTTPS://Example.COM/path/#frag") == "https://example.com/path"
    assert dw.normalize_url("https://example.com/") == "https://example.com/"


def test_download_and_save_html_skips_duplicate_content(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dw, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dw, "MANIFEST_PATH", tmp_path / "download_manifest.json")

    async def fake_download(url: str, timeout: int = 30):
        return "<html><body>same content</body></html>"

    monkeypatch.setattr(dw, "download_url", fake_download)

    import asyncio

    first = asyncio.run(dw._download_and_save_html("https://example.com/a", "a"))
    second = asyncio.run(dw._download_and_save_html("https://example.com/b", "b"))

    assert first is not None
    assert second is None
    html_files = list(tmp_path.glob("*.html"))
    assert len(html_files) == 1
    manifest = dw._load_manifest()
    statuses = [r["status"] for r in manifest["records"]]
    assert "downloaded" in statuses
    assert "duplicate_content_alias" in statuses


def test_migrate_existing_html_duplicates_marks_aliases_and_convert_skips(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(dw, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dw, "MANIFEST_PATH", tmp_path / "download_manifest.json")
    monkeypatch.setattr(convert_html, "DATA_DIR", tmp_path)

    (tmp_path / "a.html").write_text("<html><body>same</body></html>", encoding="utf-8")
    (tmp_path / "b.html").write_text("<html><body>same</body></html>", encoding="utf-8")
    (tmp_path / "c.html").write_text("<html><body>different</body></html>", encoding="utf-8")

    summary = dw.migrate_existing_html_duplicates(dry_run=False)
    assert summary["alias_count"] == 1

    manifest = dw._load_manifest()
    alias_names = dw.get_manifest_alias_filenames(manifest)
    assert len(alias_names) == 1

    html_files = {p.name for p in convert_html.get_html_files()}
    assert "c.html" in html_files
    assert len(html_files) == 2
    assert alias_names.isdisjoint(html_files)
