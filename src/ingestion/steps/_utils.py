from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)

SOURCES_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "sources.yaml"


def load_sources_config() -> dict[str, Any]:
    """Load config/sources.yaml; returns {} when the file is missing."""
    if not SOURCES_CONFIG_PATH.exists():
        return {}
    with open(SOURCES_CONFIG_PATH, encoding="utf-8") as f:
        return dict(yaml.safe_load(f) or {})


def url_file_path(
    url: str,
    data_dir: Path,
    extension: str = "html",
    *,
    include_hash_suffix: bool = True,
) -> Path:
    """Derive a safe target file path for `url` under `data_dir`.

    With `include_hash_suffix` (web/HTML style) the name is
    ``{safe_name}_{url_hash}.{extension}``; otherwise (PDF style) the extension
    is appended only when the URL slug does not already end with it.
    """
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]  # nosec B324
    safe_name = re.sub(r"[^\w\-]", "_", url.split("/")[-1][:50])
    if not safe_name or safe_name.endswith("_"):
        safe_name = f"content_{url_hash}"
    if include_hash_suffix:
        filename = f"{safe_name}_{url_hash}.{extension}"
    elif not safe_name.endswith(f".{extension}"):
        filename = f"{safe_name}.{extension}"
    else:
        filename = safe_name
    return data_dir / filename


def register_manifest_record(
    *,
    manifest: dict[str, Any],
    url: str,
    normalized_url: str,
    logical_name: str,
    file_path: Path | None,
    content_hash: str | None,
    status: str,
    duplicate_of: str | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    """Append one download record to `manifest` (shared by HTML and PDF downloaders).

    `extra_fields` adds module-specific keys (e.g. ``record_type``) before the
    timestamp.
    """
    record: dict[str, Any] = {
        "url": url,
        "normalized_url": normalized_url,
        "logical_name": logical_name,
        "filename": file_path.name if file_path else None,
        "content_hash": content_hash,
        "status": status,
        "duplicate_of": duplicate_of,
    }
    if extra_fields:
        record.update(extra_fields)
    record["timestamp_utc"] = datetime.now(UTC).isoformat()
    manifest.setdefault("records", []).append(record)


def is_transient_http_error(exc: Exception) -> bool:
    """Whether a download error is transient and worth retrying."""
    if isinstance(exc, httpx.HTTPStatusError):
        return bool(exc.response.status_code >= 500)
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError))


async def download_with_retry(
    url: str,
    *,
    timeout: float = 30,
    max_retries: int = 3,
    headers: dict[str, str] | None = None,
) -> httpx.Response | None:
    """GET `url` with exponential backoff for transient errors.

    Returns the response on success (callers extract `.text` for HTML/JSON or
    `.content` for binaries, then validate the payload) or None on failure.
    """
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for attempt in range(max_retries):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if is_transient_http_error(e) and attempt < max_retries - 1:
                    delay = 2**attempt
                    logger.warning(
                        "Transient HTTP error (attempt %d/%d) for %s, retrying in %ds: %s",
                        attempt + 1,
                        max_retries,
                        url,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.warning("HTTP error downloading %s: %s", url, e)
                return None
            except httpx.RequestError as e:
                if is_transient_http_error(e) and attempt < max_retries - 1:
                    delay = 2**attempt
                    logger.warning(
                        "Transient request error (attempt %d/%d) for %s, retrying in %ds: %s",
                        attempt + 1,
                        max_retries,
                        url,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.warning("Request error downloading %s: %s", url, e)
                return None
    return None


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine, even when called from inside a running event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _weighted_sample_chunks(
    chunks: list[dict[str, Any]],
    sample_rate: float,
    max_chunks: int,
    label: str = "sampling",
) -> list[dict[str, Any]]:
    if not chunks:
        return []

    target_count = min(max_chunks, max(1, int(len(chunks) * sample_rate)))
    population = list(chunks)
    sampled: list[dict[str, Any]] = []

    while population and len(sampled) < target_count:
        weights = [max(0.01, float(c.get("quality_score", 0.5)) ** 2) for c in population]
        selected = random.choices(population, weights=weights, k=1)[0]  # nosec B311
        sampled.append(selected)
        population = [chunk for chunk in population if chunk["id"] != selected["id"]]

    logger.info(f"{label}: selected {len(sampled)} chunks from {len(chunks)} total")
    return sampled
