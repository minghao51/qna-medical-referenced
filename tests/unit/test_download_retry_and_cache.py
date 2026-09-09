"""Unit tests for shared download retry helper, manifest cache, and group downloaders."""

import asyncio
import hashlib
import json
from pathlib import Path

import httpx

from src.ingestion.steps import _utils
from src.ingestion.steps import download_pdfs as dp
from src.ingestion.steps import download_web as dw
from src.ingestion.steps._utils import download_with_retry


def _client_returning(effects: list) -> tuple[type, dict]:
    """Build a fake httpx.AsyncClient whose .get() yields the given effects in order.

    Effects are httpx.Response objects (status raised via raise_for_status) or
    exceptions to raise. Returns (client_class, state) where state records the
    AsyncClient constructor kwargs and the number of requests made.
    """
    state: dict = {"calls": 0, "init_kwargs": None}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            state["init_kwargs"] = dict(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            assert state["calls"] < len(effects), "unexpected extra request"
            effect = effects[state["calls"]]
            state["calls"] += 1
            if isinstance(effect, Exception):
                raise effect
            return effect

    return FakeClient, state


def _record_sleep(monkeypatch) -> list[float]:
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return sleeps


# =============================================================================
# download_with_retry (shared retry/backoff helper)
# =============================================================================


def test_download_with_retry_succeeds_first_attempt(monkeypatch):
    url = "https://example.com/page"
    response = httpx.Response(200, text="hello", request=httpx.Request("GET", url))
    client_cls, state = _client_returning([response])
    monkeypatch.setattr("httpx.AsyncClient", client_cls)
    sleeps = _record_sleep(monkeypatch)

    result = asyncio.run(download_with_retry(url))

    assert result is response
    assert state["calls"] == 1
    assert sleeps == []


def test_download_with_retry_retries_transient_connect_error(monkeypatch):
    url = "https://example.com/page"
    request = httpx.Request("GET", url)
    ok = httpx.Response(200, text="hello", request=request)
    client_cls, state = _client_returning([httpx.ConnectError("boom", request=request), ok])
    monkeypatch.setattr("httpx.AsyncClient", client_cls)
    sleeps = _record_sleep(monkeypatch)

    result = asyncio.run(download_with_retry(url, max_retries=3))

    assert result is ok
    assert state["calls"] == 2
    assert sleeps == [1]


def test_download_with_retry_retries_5xx_status(monkeypatch):
    url = "https://example.com/page"
    request = httpx.Request("GET", url)
    ok = httpx.Response(200, text="hello", request=request)
    client_cls, state = _client_returning([httpx.Response(503, request=request), ok])
    monkeypatch.setattr("httpx.AsyncClient", client_cls)
    sleeps = _record_sleep(monkeypatch)

    result = asyncio.run(download_with_retry(url, max_retries=3))

    assert result is ok
    assert state["calls"] == 2
    assert sleeps == [1]


def test_download_with_retry_does_not_retry_fatal_4xx(monkeypatch):
    url = "https://example.com/page"
    client_cls, state = _client_returning([httpx.Response(404, request=httpx.Request("GET", url))])
    monkeypatch.setattr("httpx.AsyncClient", client_cls)
    sleeps = _record_sleep(monkeypatch)

    result = asyncio.run(download_with_retry(url, max_retries=3))

    assert result is None
    assert state["calls"] == 1
    assert sleeps == []


def test_download_with_retry_exhausts_retries_with_backoff(monkeypatch):
    url = "https://example.com/page"
    request = httpx.Request("GET", url)
    client_cls, state = _client_returning([httpx.ConnectError("boom", request=request)] * 3)
    monkeypatch.setattr("httpx.AsyncClient", client_cls)
    sleeps = _record_sleep(monkeypatch)

    result = asyncio.run(download_with_retry(url, max_retries=3))

    assert result is None
    assert state["calls"] == 3
    assert sleeps == [1, 2]


def test_download_with_retry_forwards_timeout_and_headers(monkeypatch):
    url = "https://example.com/page"
    response = httpx.Response(200, text="hello", request=httpx.Request("GET", url))
    client_cls, state = _client_returning([response])
    monkeypatch.setattr("httpx.AsyncClient", client_cls)

    asyncio.run(download_with_retry(url, timeout=12.5, headers={"User-Agent": "test-agent"}))

    assert state["init_kwargs"]["timeout"] == 12.5
    assert state["init_kwargs"]["headers"] == {"User-Agent": "test-agent"}
    assert state["init_kwargs"]["follow_redirects"] is True


def test_download_pdf_sends_user_agent_and_returns_bytes(monkeypatch):
    url = "https://example.com/guide.pdf"
    response = httpx.Response(
        200,
        content=b"%PDF-1.4 fake",
        headers={"content-type": "application/pdf"},
        request=httpx.Request("GET", url),
    )
    client_cls, state = _client_returning([response])
    monkeypatch.setattr("httpx.AsyncClient", client_cls)

    content = asyncio.run(dp.download_pdf(url))

    assert content == b"%PDF-1.4 fake"
    assert state["init_kwargs"]["headers"] == dp._PDF_REQUEST_HEADERS
    assert state["init_kwargs"]["timeout"] == 60


def test_is_transient_http_error_classification():
    request = httpx.Request("GET", "https://example.com")
    assert _utils.is_transient_http_error(httpx.ConnectError("boom", request=request))
    assert _utils.is_transient_http_error(httpx.ReadTimeout("slow", request=request))

    def _status_error(status_code: int) -> httpx.HTTPStatusError:
        try:
            httpx.Response(status_code, request=request).raise_for_status()
        except httpx.HTTPStatusError as e:
            return e
        raise AssertionError("raise_for_status did not raise")

    assert _utils.is_transient_http_error(_status_error(500))
    assert not _utils.is_transient_http_error(_status_error(404))
    assert not _utils.is_transient_http_error(ValueError("unrelated"))


# =============================================================================
# Manifest cache (mtime/size invalidation, write-through on save)
# =============================================================================


def test_manifest_load_is_cached_until_file_changes(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dw, "DATA_DIR", tmp_path)
    manifest_path = tmp_path / "download_manifest.json"
    monkeypatch.setattr(dw, "MANIFEST_PATH", manifest_path)

    dw._save_manifest(
        {"records": [{"filename": "alpha.html", "logical_name": "alpha", "status": "downloaded"}]}
    )

    first = dw._load_manifest()
    assert dw._load_manifest() is first  # served from cache, no re-read

    # External write bypassing _save_manifest changes size/mtime -> cache invalidated.
    external = {
        "records": [
            {
                "filename": "beta_with_longer_name.html",
                "logical_name": "beta",
                "status": "downloaded",
            }
        ]
    }
    manifest_path.write_text(json.dumps(external, indent=2), encoding="utf-8")

    reloaded = dw._load_manifest()
    assert reloaded is not first
    assert reloaded["records"][0]["filename"] == "beta_with_longer_name.html"


def test_save_manifest_refreshes_cache(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dw, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dw, "MANIFEST_PATH", tmp_path / "download_manifest.json")

    record_a = {"filename": "a.html", "logical_name": "a", "status": "downloaded"}
    dw._save_manifest({"records": [record_a]})
    cached = dw._load_manifest()

    record_b = {"filename": "b.html", "logical_name": "b", "status": "downloaded"}
    dw._save_manifest({"records": [record_a, record_b]})

    refreshed = dw._load_manifest()
    assert refreshed is not cached
    assert dw.get_manifest_record_by_filename("b.html") is not None
    assert dw.get_manifest_record_by_filename("a.html")["logical_name"] == "a"


def test_corrupt_manifest_not_cached(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dw, "DATA_DIR", tmp_path)
    manifest_path = tmp_path / "download_manifest.json"
    monkeypatch.setattr(dw, "MANIFEST_PATH", manifest_path)

    manifest_path.write_text("{not json", encoding="utf-8")
    assert dw._load_manifest() == {"records": []}
    assert dw._manifest_cache is None

    manifest_path.write_text(json.dumps({"records": []}), encoding="utf-8")
    assert dw._load_manifest() == {"records": []}
    assert dw._manifest_cache is not None  # healthy manifest is cached again


# =============================================================================
# Content-hash index (built once per run instead of per-URL scans)
# =============================================================================


def test_content_hash_index_built_once_for_repeated_lookups(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dw, "DATA_DIR", tmp_path)
    (tmp_path / "page_one.html").write_text("<html>one</html>", encoding="utf-8")
    (tmp_path / "page_two.html").write_text("<html>two</html>", encoding="utf-8")

    builds = {"n": 0}
    real_build = dw._build_content_hash_index

    def counting_build():
        builds["n"] += 1
        return real_build()

    monkeypatch.setattr(dw, "_build_content_hash_index", counting_build)

    digest = hashlib.sha256(b"<html>two</html>").hexdigest()[:16]
    first = dw._find_existing_file_by_content_hash(digest)
    second = dw._find_existing_file_by_content_hash(digest)

    assert first is not None
    assert first.name == "page_two.html"
    assert second == first
    assert builds["n"] == 1


def test_download_dedupes_against_unlisted_file_and_reuses_index(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dw, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dw, "MANIFEST_PATH", tmp_path / "download_manifest.json")

    content = "<html><body>same content</body></html>"
    (tmp_path / "orphan_page.html").write_text(content, encoding="utf-8")

    builds = {"n": 0}
    real_build = dw._build_content_hash_index

    def counting_build():
        builds["n"] += 1
        return real_build()

    monkeypatch.setattr(dw, "_build_content_hash_index", counting_build)

    async def fake_download(url: str, timeout: int = 30):
        return content

    monkeypatch.setattr(dw, "download_url", fake_download)

    result = asyncio.run(dw._download_and_save_html("https://example.com/a", "a"))
    assert result is None  # deduped against the orphan file on disk
    statuses = [r["status"] for r in dw._load_manifest()["records"]]
    assert statuses == ["duplicate_content_alias"]
    assert [f.name for f in tmp_path.glob("*.html")] == ["orphan_page.html"]
    assert builds["n"] == 1

    # A further identical download dedupes without rescanning the directory.
    result2 = asyncio.run(dw._download_and_save_html("https://example.com/b", "b"))
    assert result2 is None
    assert builds["n"] == 1


def test_downloaded_file_recorded_in_index_without_rebuild(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dw, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dw, "MANIFEST_PATH", tmp_path / "download_manifest.json")

    builds = {"n": 0}
    real_build = dw._build_content_hash_index

    def counting_build():
        builds["n"] += 1
        return real_build()

    monkeypatch.setattr(dw, "_build_content_hash_index", counting_build)

    async def fake_download(url: str, timeout: int = 30):
        return "<html><body>fresh content</body></html>"

    monkeypatch.setattr(dw, "download_url", fake_download)

    saved = asyncio.run(dw._download_and_save_html("https://example.com/new", "new"))
    assert saved is not None
    assert builds["n"] == 1

    digest = hashlib.sha256(b"<html><body>fresh content</body></html>").hexdigest()[:16]
    found = dw._find_existing_file_by_content_hash(digest)
    assert found is not None
    assert found.name == Path(saved).name
    assert builds["n"] == 1  # served from index, no rescan


# =============================================================================
# Group downloaders (web gather + pdf bounded gather)
# =============================================================================


def test_download_group_gathers_concurrently_and_filters(monkeypatch):
    seen: list[tuple[str, str, int]] = []

    async def fake_download_and_save(url: str, name: str, timeout: int = 30) -> str | None:
        seen.append((url, name, timeout))
        await asyncio.sleep(0)
        return f"{name}.html" if name != "skipped" else None

    monkeypatch.setattr(dw, "_download_and_save_html", fake_download_and_save)
    monkeypatch.setattr(
        dw,
        "_get_web_sources",
        lambda group: [
            ("https://example.com/1", "one"),
            ("https://example.com/2", "skipped"),
            ("https://example.com/3", "three"),
        ],
    )

    result = asyncio.run(dw.download_group("any_group", timeout=60))

    assert sorted(result) == ["one.html", "three.html"]
    assert seen == [
        ("https://example.com/1", "one", 60),
        ("https://example.com/2", "skipped", 60),
        ("https://example.com/3", "three", 60),
    ]


def test_download_pdfs_group_bounds_concurrency_and_filters(monkeypatch, tmp_path: Path):
    stats = {"active": 0, "peak": 0}

    async def fake_download_pdf_if_not_exists(url: str, name: str) -> Path | None:
        stats["active"] += 1
        stats["peak"] = max(stats["peak"], stats["active"])
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        stats["active"] -= 1
        return tmp_path / f"{name}.pdf" if name.endswith("keep") else None

    monkeypatch.setattr(dp, "download_pdf_if_not_exists", fake_download_pdf_if_not_exists)
    monkeypatch.setattr(
        dp,
        "_get_pdf_sources",
        lambda group: [
            ("https://example.com/1", "a_keep"),
            ("https://example.com/2", "b_drop"),
            ("https://example.com/3", "c_keep"),
            ("https://example.com/4", "d_drop"),
            ("https://example.com/5", "e_keep"),
            ("https://example.com/6", "f_drop"),
        ],
    )

    result = asyncio.run(dp.download_pdfs_group("any_group"))

    assert 2 <= stats["peak"] <= dp._PDF_DOWNLOAD_CONCURRENCY
    assert sorted(p.name for p in result) == ["a_keep.pdf", "c_keep.pdf", "e_keep.pdf"]
