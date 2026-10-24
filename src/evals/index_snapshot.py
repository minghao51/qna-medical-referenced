"""Immutable local index snapshots and isolated, supplied-embedding copies.

A normal Chroma collection is mutable and does not expose a transactionally
consistent read snapshot. Callers may only freeze a source that implements the
explicit ``read_consistent_index_snapshot`` public seam; the shared runtime
store is deliberately not adapted to that seam.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, cast
from urllib.parse import urlsplit

SNAPSHOT_CONTRACT_VERSION = 1
_MAX_EXPORT_BYTES = 256 * 1024 * 1024
_MAX_DOCUMENTS = 250_000
_SOURCE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
# URL-shaped strings are inspected only at scheme-anchored spans so free
# prose containing "://", "?" or "#" away from a real URL is never urlsplit()'ed.
_SCHEME_PREFIX = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
_URL_SPAN = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://\S+")
_REQUIRED_BUILD_METADATA = {
    "source_snapshot_sha256",
    "embedding_model",
    "embedding_batch_size",
    "semantic_weight",
    "keyword_weight",
    "boost_weight",
    "page_classification_enabled",
    "index_only_classified_pages",
    "html_extractor_mode",
    "html_extractor_strategy",
    "pdf_extractor_strategy",
    "pdf_table_extractor",
    "structured_chunking_enabled",
    "source_chunk_configs",
    "enable_hype",
    "hype_sample_rate",
    "hype_max_chunks",
    "hype_questions_per_chunk",
    "enable_keyword_extraction",
    "enable_chunk_summaries",
    "keyword_extraction_sample_rate",
    "keyword_extraction_max_chunks",
}


class ConsistentIndexSnapshotSource(Protocol):
    """Public seam for a privately owned/quiescent collection snapshot."""

    def read_consistent_index_snapshot(self) -> Mapping[str, Any]:
        """Return ``{'snapshot': ..., 'build_spec': ...}`` from one frozen view."""


class SnapshotError(ValueError):
    """The supplied index data cannot be certified as a complete local snapshot."""


def _reject_credentials(value: Any) -> None:
    error = "Index snapshot metadata must not contain credentials or credential-bearing URLs"
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SnapshotError("Index snapshot object keys must be strings")
            normalized = key.lower().replace("-", "_")
            compact = normalized.replace("_", "")
            if (
                compact
                in {
                    "key",
                    "accesskey",
                    "privatekey",
                    "clientsecret",
                    "token",
                    "auth",
                    "bearer",
                }
                or any(
                    marker in compact
                    for marker in (
                        "apikey",
                        "password",
                        "secret",
                        "credential",
                        "authorization",
                        "cookie",
                        "headers",
                    )
                )
                or compact.endswith("token")
            ):
                raise SnapshotError(error)
            _reject_credentials(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_credentials(item)
    elif isinstance(value, str) and "://" in value:
        # Only URL-shaped content goes through urlsplit(): running it over
        # arbitrary prose parses any later "?" or "#" as a URL query/
        # fragment and false-positives on free text such as "See
        # https://example.com/x ... is it useful? Yes #indeed". Leading
        # whitespace is stripped before the scheme-prefix test, and every
        # scheme-anchored span of the string is checked individually so a
        # padded or prose-embedded credential-bearing URL is still caught.
        spans: list[str] = []
        stripped = value.lstrip()
        if _SCHEME_PREFIX.match(stripped):
            spans.append(stripped)
        spans.extend(found.group(0) for found in _URL_SPAN.finditer(value))
        try:
            for span in spans:
                parsed = urlsplit(span)
                if parsed.username or parsed.password or parsed.query or parsed.fragment:
                    raise SnapshotError(error)
        except ValueError:
            raise SnapshotError(error) from None


def _json_value(value: Any) -> Any:
    """Copy supported public API values into strict, finite JSON values."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    elif hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SnapshotError("Index snapshot contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise SnapshotError("Index snapshot object keys must be strings")
        copied = {key: _json_value(item) for key, item in value.items()}
        _reject_credentials(copied)
        return copied
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise SnapshotError("Index snapshot contains an unsupported value")


def _finite_number(value: int | float) -> bool:
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _canonical_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise SnapshotError("Index snapshot cannot be serialized canonically") from None
    if len(encoded) > _MAX_EXPORT_BYTES:
        raise SnapshotError("Index snapshot exceeds the supported export size")
    return encoded


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _validate_build_spec(build_spec: dict[str, Any], dimensions: int) -> None:
    metadata = build_spec.get("collection_metadata")
    embedder = build_spec.get("embedder")
    weights = build_spec.get("retrieval_weights")
    if (
        not isinstance(metadata, dict)
        or not isinstance(embedder, dict)
        or not isinstance(weights, dict)
    ):
        raise SnapshotError("Index build specification is incomplete")
    if (
        not isinstance(build_spec.get("collection_name"), str)
        or not build_spec["collection_name"].strip()
    ):
        raise SnapshotError("Index collection identity is missing")
    if not _REQUIRED_BUILD_METADATA.issubset(metadata):
        raise SnapshotError("Index build metadata is missing; rebuild with source provenance")
    source_digest = metadata.get("source_snapshot_sha256")
    if not isinstance(source_digest, str) or not _SOURCE_DIGEST.fullmatch(source_digest):
        raise SnapshotError("Index source provenance is missing; rebuild with source provenance")
    for key in (
        "html_extractor_mode",
        "html_extractor_strategy",
        "pdf_extractor_strategy",
        "pdf_table_extractor",
    ):
        if not isinstance(metadata.get(key), str) or not metadata[key]:
            raise SnapshotError("Index build metadata is incomplete")
    for key in (
        "page_classification_enabled",
        "index_only_classified_pages",
        "structured_chunking_enabled",
        "enable_hype",
        "enable_keyword_extraction",
        "enable_chunk_summaries",
    ):
        if not isinstance(metadata.get(key), bool):
            raise SnapshotError("Index build metadata is incomplete")
    chunk_configs = metadata.get("source_chunk_configs")
    if isinstance(chunk_configs, str):
        try:
            chunk_configs = json.loads(chunk_configs)
        except json.JSONDecodeError:
            raise SnapshotError("Index build metadata is incomplete") from None
    if not isinstance(chunk_configs, dict):
        raise SnapshotError("Index build metadata is incomplete")
    _reject_credentials(chunk_configs)
    model = embedder.get("model")
    batch_size = embedder.get("batch_size")
    if (
        not isinstance(model, str)
        or not model
        or not isinstance(batch_size, int)
        or isinstance(batch_size, bool)
        or batch_size < 1
        or embedder.get("dimensions") != dimensions
    ):
        raise SnapshotError("Index embedder provenance is incomplete")
    if (
        metadata.get("embedding_model") != model
        or metadata.get("embedding_batch_size") != batch_size
    ):
        raise SnapshotError("Index embedder metadata does not match the build specification")
    for key in ("semantic", "keyword", "boost"):
        value = weights.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not _finite_number(value)
        ):
            raise SnapshotError("Index retrieval weights are incomplete")
    for key in ("semantic", "keyword", "boost"):
        metadata_value = metadata.get(f"{key}_weight")
        if (
            isinstance(metadata_value, bool)
            or not isinstance(metadata_value, (int, float))
            or not _finite_number(metadata_value)
            or float(metadata_value) != float(weights[key])
        ):
            raise SnapshotError("Index retrieval weights do not match build metadata")


def _normalize_snapshot(
    snapshot: Mapping[str, Any], build_spec: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(snapshot, Mapping) or not isinstance(build_spec, Mapping):
        raise SnapshotError("Frozen index snapshot data is unavailable")
    snapshot_data = _json_value(dict(snapshot))
    spec_data = _json_value(dict(build_spec))
    ids = snapshot_data.get("ids")
    contents = snapshot_data.get("contents")
    metadatas = snapshot_data.get("metadatas")
    embeddings = snapshot_data.get("embeddings")
    index_metadata = snapshot_data.get("index_metadata")
    if not all(isinstance(items, list) for items in (ids, contents, metadatas, embeddings)):
        raise SnapshotError("Index snapshot arrays are incomplete")
    if not ids or len(ids) > _MAX_DOCUMENTS:
        raise SnapshotError("Index snapshot is empty or exceeds the supported document count")
    if not (len(ids) == len(contents) == len(metadatas) == len(embeddings)):
        raise SnapshotError("Index snapshot arrays have mismatched lengths")
    if any(not isinstance(item, str) or not item for item in ids) or len(set(ids)) != len(ids):
        raise SnapshotError("Index snapshot IDs are invalid or duplicated")
    if any(not isinstance(item, str) for item in contents):
        raise SnapshotError("Index snapshot documents are invalid")
    if any(not isinstance(item, dict) for item in metadatas):
        raise SnapshotError("Index snapshot document metadata is invalid")
    if not isinstance(index_metadata, dict):
        raise SnapshotError("Index collection build metadata is unavailable")
    if spec_data.get("collection_metadata") != index_metadata:
        raise SnapshotError("Index collection metadata does not match the build specification")
    normalized_embeddings: list[list[float]] = []
    dimensions: set[int] = set()
    for vector in embeddings:
        if not isinstance(vector, list) or not vector:
            raise SnapshotError("Index embeddings are incomplete")
        normalized: list[float] = []
        for item in vector:
            if (
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not _finite_number(item)
            ):
                raise SnapshotError("Index embeddings contain invalid values")
            normalized.append(float(item))
        dimensions.add(len(normalized))
        normalized_embeddings.append(normalized)
    if len(dimensions) != 1:
        raise SnapshotError("Index embedding dimensions are inconsistent")
    snapshot_data["embeddings"] = normalized_embeddings
    _validate_build_spec(spec_data, next(iter(dimensions)))
    _reject_credentials(snapshot_data)
    _reject_credentials(spec_data)
    ordered = sorted(
        zip(ids, contents, metadatas, normalized_embeddings, strict=True), key=lambda row: row[0]
    )
    snapshot_data["ids"] = [row[0] for row in ordered]
    snapshot_data["contents"] = [row[1] for row in ordered]
    snapshot_data["metadatas"] = [row[2] for row in ordered]
    snapshot_data["embeddings"] = [row[3] for row in ordered]
    _canonical_bytes({"snapshot": snapshot_data, "build_spec": spec_data})
    return snapshot_data, spec_data


def _fingerprints(snapshot: dict[str, Any], build_spec: dict[str, Any]) -> tuple[str, str, str]:
    snapshot_sha256 = hashlib.sha256(
        _canonical_bytes({"snapshot": snapshot, "build_spec": build_spec})
    ).hexdigest()
    records = sorted(
        zip(
            snapshot["ids"],
            snapshot["contents"],
            snapshot["metadatas"],
            snapshot["embeddings"],
            strict=True,
        ),
        key=lambda row: row[0],
    )
    fingerprint = hashlib.sha256(
        _canonical_bytes(
            {"config": {"records": records, "build_spec": build_spec}, "git_head": None}
        )
    ).hexdigest()
    build_spec_sha256 = hashlib.sha256(
        _canonical_bytes({"config": build_spec, "git_head": None})
    ).hexdigest()
    return snapshot_sha256, fingerprint, build_spec_sha256


@dataclass(frozen=True, slots=True, init=False)
class FrozenIndexSnapshot:
    """Deeply immutable, revalidated collection records and build specification."""

    _snapshot: Mapping[str, Any]
    _build_spec: Mapping[str, Any]
    _snapshot_sha256: str
    _fingerprint: str
    _build_spec_sha256: str

    def __init__(
        self,
        snapshot: dict[str, Any],
        build_spec: dict[str, Any],
        snapshot_sha256: str,
        fingerprint: str,
        build_spec_sha256: str,
        *,
        _token: object,
    ) -> None:
        if _token is not _SNAPSHOT_TOKEN:
            raise TypeError("Use freeze_index_snapshot() or load_snapshot_export()")
        object.__setattr__(self, "_snapshot", _freeze(snapshot))
        object.__setattr__(self, "_build_spec", _freeze(build_spec))
        object.__setattr__(self, "_snapshot_sha256", snapshot_sha256)
        object.__setattr__(self, "_fingerprint", fingerprint)
        object.__setattr__(self, "_build_spec_sha256", build_spec_sha256)

    @property
    def collection_name(self) -> str:
        return str(self._build_spec["collection_name"])

    @property
    def document_count(self) -> int:
        return len(self._snapshot["ids"])

    @property
    def snapshot_sha256(self) -> str:
        return self._snapshot_sha256

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    @property
    def build_spec_sha256(self) -> str:
        return self._build_spec_sha256

    def revalidate(self) -> None:
        snapshot, build_spec = _normalize_snapshot(_thaw(self._snapshot), _thaw(self._build_spec))
        actual = _fingerprints(snapshot, build_spec)
        if actual != (self._snapshot_sha256, self._fingerprint, self._build_spec_sha256):
            raise SnapshotError("Frozen index snapshot identity changed")

    def capture_payload(self) -> dict[str, Any]:
        self.revalidate()
        return {
            "status": "verified",
            "reason": None,
            "freeze_guarantee": True,
            "snapshot_sha256": self._snapshot_sha256,
            "fingerprint": self._fingerprint,
            "build_spec_sha256": self._build_spec_sha256,
            "snapshot": _thaw(self._snapshot),
            "build_spec": _thaw(self._build_spec),
        }

    def materialize(
        self,
        parent_dir: str | Path | None = None,
        *,
        backend_factory: Any | None = None,
    ) -> PrivateIndexMaterialization:
        return materialize_index_snapshot(self, parent_dir, backend_factory=backend_factory)


_SNAPSHOT_TOKEN = object()


def freeze_index_snapshot(source: ConsistentIndexSnapshotSource) -> FrozenIndexSnapshot:
    """Freeze one result from an explicit consistent, privately owned source seam."""
    if not callable(getattr(source, "read_consistent_index_snapshot", None)):
        raise SnapshotError("A consistent private index snapshot source is required")
    try:
        payload = source.read_consistent_index_snapshot()
    except Exception:
        raise SnapshotError("Private index snapshot source is unavailable") from None
    if not isinstance(payload, Mapping):
        raise SnapshotError("Private index snapshot source returned an invalid payload")
    raw_snapshot = payload.get("snapshot")
    raw_build_spec = payload.get("build_spec")
    if not isinstance(raw_snapshot, Mapping) or not isinstance(raw_build_spec, Mapping):
        raise SnapshotError("Private index snapshot source returned incomplete data")
    snapshot, build_spec = _normalize_snapshot(raw_snapshot, raw_build_spec)
    snapshot_sha256, fingerprint, build_spec_sha256 = _fingerprints(snapshot, build_spec)
    return FrozenIndexSnapshot(
        snapshot,
        build_spec,
        snapshot_sha256,
        fingerprint,
        build_spec_sha256,
        _token=_SNAPSHOT_TOKEN,
    )


def _path_has_symlink(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                return True
        except FileNotFoundError:
            return False
    return False


def write_snapshot_export(snapshot: FrozenIndexSnapshot, path: str | Path) -> Path:
    """Write a new, read-only export without following links or overwriting files."""
    snapshot.revalidate()
    target = Path(path).absolute()
    parent = target.parent
    if _path_has_symlink(parent) or not parent.is_dir() or target.exists() or target.is_symlink():
        raise SnapshotError("Snapshot export path must be a new file in a real directory")
    payload = {
        "contract_version": SNAPSHOT_CONTRACT_VERSION,
        "snapshot_sha256": snapshot.snapshot_sha256,
        "snapshot": _thaw(snapshot._snapshot),
        "build_spec": _thaw(snapshot._build_spec),
    }
    encoded = _canonical_bytes(payload)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    created = False
    try:
        descriptor = os.open(target, flags, 0o400)
        created = True
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(target, 0o400, follow_symlinks=False)
        loaded = load_snapshot_export(target)
        if loaded.snapshot_sha256 != snapshot.snapshot_sha256:
            raise SnapshotError("Snapshot export verification failed")
        snapshot.revalidate()
    except BaseException:
        if created:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return target


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SnapshotError("Snapshot export contains duplicate object keys")
        result[key] = value
    return result


def load_snapshot_export(path: str | Path) -> FrozenIndexSnapshot:
    """Load an export, validate its actual bytes/data/build spec, and ignore status flags."""
    target = Path(path).absolute()
    if _path_has_symlink(target) or not target.is_file():
        raise SnapshotError("Snapshot export must be a regular non-symlink file")
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(target, flags)
        with os.fdopen(descriptor, "rb") as source:
            descriptor = None
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode) & 0o222:
                raise SnapshotError("Snapshot export must be a read-only regular file")
            if before.st_size <= 0 or before.st_size > _MAX_EXPORT_BYTES:
                raise SnapshotError("Snapshot export has an unsupported size")
            raw = source.read(_MAX_EXPORT_BYTES + 1)
            after = os.fstat(source.fileno())
    except OSError:
        raise SnapshotError("Snapshot export is unavailable") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or len(raw) != after.st_size:
        raise SnapshotError("Snapshot export changed while being read")
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SnapshotError("Snapshot export is invalid") from None
    if (
        not isinstance(payload, dict)
        or payload.get("contract_version") != SNAPSHOT_CONTRACT_VERSION
    ):
        raise SnapshotError("Snapshot export contract is unsupported")
    raw_snapshot = payload.get("snapshot")
    raw_build_spec = payload.get("build_spec")
    if not isinstance(raw_snapshot, Mapping) or not isinstance(raw_build_spec, Mapping):
        raise SnapshotError("Snapshot export payload is incomplete")
    snapshot, build_spec = _normalize_snapshot(raw_snapshot, raw_build_spec)
    snapshot_sha256, fingerprint, build_spec_sha256 = _fingerprints(snapshot, build_spec)
    if payload.get("snapshot_sha256") != snapshot_sha256:
        raise SnapshotError("Snapshot export content digest mismatch")
    return FrozenIndexSnapshot(
        snapshot,
        build_spec,
        snapshot_sha256,
        fingerprint,
        build_spec_sha256,
        _token=_SNAPSHOT_TOKEN,
    )


class PrivateIndexMaterialization:
    """Caller-owned writable Chroma copy, isolated from the source export/index."""

    __slots__ = ("_build_spec", "_cleaned", "_identity", "client", "collection", "path")

    def __init__(
        self, path: Path, client: Any, collection: Any, build_spec: dict[str, Any]
    ) -> None:
        self.path = path
        self.collection = collection
        self.client = client
        self._build_spec = build_spec
        info = path.stat()
        self._identity = (info.st_dev, info.st_ino)
        self._cleaned = False

    def read_consistent_index_snapshot(self) -> dict[str, Any]:
        """Read the owned, quiescent copy through Chroma's public collection API.

        Callers must keep this private copy single-process and read-only while
        using the returned payload as a consistency snapshot.
        """
        if self._cleaned or self.collection is None:
            raise SnapshotError("Private index materialization is unavailable")
        readback = self.collection.get(include=["documents", "metadatas", "embeddings"])
        snapshot = {
            "ids": list(readback.get("ids") or []),
            "contents": list(readback.get("documents") or []),
            "metadatas": list(readback.get("metadatas") or []),
            "embeddings": list(readback.get("embeddings") or []),
            "index_metadata": _json_value(self._build_spec["collection_metadata"]),
        }
        build_spec = _json_value(self._build_spec)
        if not isinstance(build_spec, dict):
            raise SnapshotError("Private index build metadata is invalid")
        return {"snapshot": snapshot, "build_spec": build_spec}

    def query_with_embedding(
        self,
        embedding: Sequence[float],
        *,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._cleaned:
            raise SnapshotError("Private index materialization has been cleaned up")
        if isinstance(n_results, bool) or not isinstance(n_results, int) or n_results < 1:
            raise ValueError("n_results must be a positive integer")
        if self.collection is None:
            raise SnapshotError("Private index backend has been released")
        vector = _json_value(list(embedding))
        if not vector:
            raise ValueError("Query embedding must not be empty")
        expected_dimensions = self.collection.metadata.get("embedding_dimensions")
        if expected_dimensions is not None and len(vector) != expected_dimensions:
            raise ValueError("Query embedding dimensions do not match the frozen index")
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in vector):
            raise ValueError("Query embedding must contain finite numbers")
        if any(not _finite_number(item) for item in vector):
            raise ValueError("Query embedding must contain finite numbers")
        query: dict[str, Any] = {
            "query_embeddings": [[float(item) for item in vector]],
            "n_results": n_results,
        }
        if where is not None:
            query["where"] = _json_value(where)
        return cast(dict[str, Any], self.collection.query(**query))

    def release_backend(self) -> None:
        """Drop references without closing; caller owns any backend-specific close step."""
        self.collection = None
        self.client = None

    def cleanup(self) -> None:
        """Remove only this owned directory; caller must first release backend handles."""
        if self._cleaned:
            return
        if self.collection is not None or self.client is not None:
            raise SnapshotError("Release the private backend before removing its directory")
        if _path_has_symlink(self.path):
            raise SnapshotError("Private index directory was replaced by a symlink")
        try:
            info = self.path.stat()
        except OSError:
            self._cleaned = True
            return
        if (info.st_dev, info.st_ino) != self._identity:
            raise SnapshotError("Private index directory identity changed")
        shutil.rmtree(self.path)
        self._cleaned = True


def _open_chroma_collection(path: Path, build_spec: dict[str, Any]) -> tuple[Any, Any]:
    try:
        import chromadb
    except ImportError:
        raise SnapshotError("Chroma is required to materialize a private index copy") from None
    client = chromadb.PersistentClient(path=str(path))
    collection = client.get_or_create_collection(
        name=build_spec["collection_name"],
        metadata={"embedding_dimensions": build_spec["embedder"]["dimensions"]},
        embedding_function=None,
    )
    return client, collection


def materialize_index_snapshot(
    snapshot: FrozenIndexSnapshot,
    parent_dir: str | Path | None = None,
    *,
    backend_factory: Any | None = None,
) -> PrivateIndexMaterialization:
    """Create a unique local collection and upsert only the frozen supplied vectors."""
    if not isinstance(snapshot, FrozenIndexSnapshot):
        raise SnapshotError("Only a revalidated frozen index snapshot can be copied")
    snapshot.revalidate()
    root = (
        Path(parent_dir).absolute()
        if parent_dir is not None
        else Path(tempfile.gettempdir()).absolute()
    )
    if _path_has_symlink(root) or not root.is_dir():
        raise SnapshotError("Private index parent must be an existing non-symlink directory")
    directory = Path(tempfile.mkdtemp(prefix="qna-index-run-", dir=root))
    client: Any = None
    try:
        data = _thaw(snapshot._snapshot)
        spec = _thaw(snapshot._build_spec)
        write_snapshot_export(snapshot, directory / "snapshot.json")
        if backend_factory is None:
            client, collection = _open_chroma_collection(directory, spec)
        else:
            client, collection = backend_factory(directory, spec)
        collection.upsert(
            ids=data["ids"],
            documents=data["contents"],
            metadatas=data["metadatas"],
            embeddings=data["embeddings"],
        )
        readback = collection.get(include=["documents", "metadatas", "embeddings"])
        copied = {
            "ids": list(readback.get("ids") or []),
            "contents": list(readback.get("documents") or []),
            "metadatas": list(readback.get("metadatas") or []),
            "embeddings": list(readback.get("embeddings") or []),
            "index_metadata": spec["collection_metadata"],
        }
        copied, verified_spec = _normalize_snapshot(copied, spec)
        if _fingerprints(copied, verified_spec)[0] != snapshot.snapshot_sha256:
            raise SnapshotError("Private index copy did not match the frozen snapshot")
        snapshot.revalidate()
        return PrivateIndexMaterialization(directory, client, collection, spec)
    except BaseException:
        try:
            shutil.rmtree(directory)
        except OSError:
            pass
        raise
