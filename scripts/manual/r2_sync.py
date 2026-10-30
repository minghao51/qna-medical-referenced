"""Idempotent sync between local data directories and a Cloudflare R2 bucket.

Three sync sets (R2 prefix <-> local directory, resolved under the repo root):

- ``corpus``  <-> ``data/chroma-d11``
- ``raw``     <-> ``data/raw``
- ``review``  <-> ``data/evals/review``

Uploads and downloads are idempotent: a file is skipped when the remote
object's size differs from the local size by at most 100 bytes (the housing
convention), so re-running either direction only transfers what changed. A
local file with no remote object is treated as "needs upload".

Remote keys are confined to the selected sync set's local directory: keys with
absolute paths, ``..`` components, or directory markers are skipped and
reported, and the resolved destination must stay inside the sync root.
Interrupted downloads are cleaned up: each file lands as ``<name>.r2part`` and
is renamed into place only on success. A failed transfer removes its temp file,
leftovers from an earlier interrupted run are removed before a download starts,
and ``*.r2part`` files are excluded from local enumeration so they are never
uploaded.

``--verify`` is read-only and additionally compares SHA-256 digests of size-equal
pairs, so same-size content drift is reported instead of hidden by the size
tolerance. Verify is report-only by design: it prints ``VERIFY OK`` when every
counter is zero and ``VERIFY MISMATCH`` (with the same counters) otherwise, and
exits 0 in both cases. Investigate a mismatch before trusting either side.

Remote-controlled keys are sanitized before they reach the terminal: the sync
prefix is stripped, control characters are replaced, and the remainder is
length-capped, so a hostile object name cannot inject terminal escapes or dump
long identifiers.

Exclusion policy: this script never syncs ``data/evals/cache``,
``rate_limits.db``, chat-history files, logs, or ``.env``. Those paths are
simply not part of any sync set, so they are never enumerated or written.

Secrets are never logged: credentials and the endpoint's account id are used
only to build the boto3 client and are never printed, echoed, or included in
any error payload.

Usage:
    uv run python scripts/manual/r2_sync.py            # download (R2 -> local)
    uv run python scripts/manual/r2_sync.py --upload   # upload (local -> R2)
    uv run python scripts/manual/r2_sync.py --verify   # report only, no transfers
    uv run python scripts/manual/r2_sync.py --only raw  # one sync set only
"""

import argparse
import hashlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

CORPUS_DIR = REPO_ROOT / "data" / "chroma-d11"
RAW_DIR = REPO_ROOT / "data" / "raw"
REVIEW_DIR = REPO_ROOT / "data" / "evals" / "review"

_SIZE_TOLERANCE_BYTES = 100

# Temp-file suffix for atomic downloads; also excluded from local enumeration.
_PARTIAL_SUFFIX = ".r2part"
_CHECKSUM_CHUNK_BYTES = 1024 * 1024

# Printed keys come from the bucket, so they are untrusted: cap the length and
# replace non-printable characters before reporting them.
_MAX_DISPLAY_KEY_CHARS = 120

# Bounded transfer concurrency; boto3 S3 clients are thread-safe for the
# operations used here (download_file / upload_file / list_objects_v2).
_TRANSFER_CONCURRENCY = 8

_SYNC_SETS: tuple[tuple[str, Path], ...] = (
    ("corpus", CORPUS_DIR),
    ("raw", RAW_DIR),
    ("review", REVIEW_DIR),
)


class R2Settings(BaseSettings):
    """R2 credentials and bucket, read from the environment (and an optional .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    r2_account_id: str = ""
    r2_access_key_id: SecretStr = SecretStr("")
    r2_secret_access_key: SecretStr = SecretStr("")
    r2_bucket: str = "qna-medical-referenced-data"
    r2_endpoint: str = ""


def _settings() -> R2Settings:
    return R2Settings()


def _s3_client(settings: R2Settings) -> Any:
    endpoint = settings.r2_endpoint or f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.r2_access_key_id.get_secret_value(),
        aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
        region_name="auto",
        config=BotoConfig(retries={"max_attempts": 3, "mode": "standard"}),
    )


def _iter_local(prefix: str, local_dir: Path) -> list[tuple[Path, str]]:
    """List (local_path, r2_key) pairs under ``local_dir`` for ``prefix``.

    Skips symlinks and non-regular files; preserves relative paths under the
    prefix.
    """
    if not local_dir.exists():
        return []
    files: list[tuple[Path, str]] = []
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if path.name.endswith(_PARTIAL_SUFFIX):
            continue
        key = f"{prefix}/{path.relative_to(local_dir).as_posix()}"
        files.append((path, key))
    return files


def _safe_local_path(prefix: str, local_dir: Path, key: str) -> Path | None:
    """Resolve an R2 key under ``local_dir``; ``None`` when the key is unsafe.

    Rejects keys that do not belong to the prefix, carry an absolute path, a
    ``..`` component, or a directory marker (trailing slash). The resolved
    destination must stay inside the resolved sync root, so symlinked parents
    cannot redirect a write outside it.
    """
    prefix_root = f"{prefix}/"
    if not key.startswith(prefix_root):
        return None
    relative = key[len(prefix_root) :]
    if not relative or relative.endswith("/"):
        return None
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or ".." in parts:
        return None
    root = local_dir.resolve()
    target = (local_dir / relative).resolve()
    if target == root or not target.is_relative_to(root):
        return None
    return target


def _sanitize_key_for_display(key: str, prefix: str) -> str:
    """Make a remote-controlled object key safe to print.

    The sync prefix is already in the message, so it is stripped; remaining
    control characters (including ANSI escapes) are replaced with ``?`` and the
    result is capped at ``_MAX_DISPLAY_KEY_CHARS`` so an arbitrary bucket key
    cannot manipulate the terminal or dump a long identifier.
    """
    prefix_root = f"{prefix}/"
    displayed = key[len(prefix_root) :] if key.startswith(prefix_root) else key
    cleaned = "".join(char if char.isprintable() else "?" for char in displayed)
    if len(cleaned) > _MAX_DISPLAY_KEY_CHARS:
        cleaned = cleaned[: _MAX_DISPLAY_KEY_CHARS - 3] + "..."
    return cleaned


def _sha256_local(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHECKSUM_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_remote(s3: Any, bucket: str, key: str) -> str:
    digest = hashlib.sha256()
    body = s3.get_object(Bucket=bucket, Key=key)["Body"]
    try:
        while chunk := body.read(_CHECKSUM_CHUNK_BYTES):
            digest.update(chunk)
    finally:
        # Streaming bodies hold an HTTP connection open; close it even when a
        # read fails so the failure cannot leak the connection.
        close = getattr(body, "close", None)
        if callable(close):
            close()
    return digest.hexdigest()


def _remote_sizes(s3: Any, bucket: str, prefix: str) -> dict[str, int]:
    """Map of R2 object key -> size under ``prefix`` via paginated listing."""
    paginator = s3.get_paginator("list_objects_v2")
    sizes: dict[str, int] = {}
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            sizes[obj["Key"]] = obj["Size"]
    return sizes


def _remove_stale_partials(local_dir: Path) -> None:
    """Delete ``*.r2part`` temp files left by an interrupted earlier run."""
    if not local_dir.exists():
        return
    for path in local_dir.rglob(f"*{_PARTIAL_SUFFIX}"):
        if path.is_file():
            path.unlink(missing_ok=True)


def _download_all(s3: Any, bucket: str, pending: list[tuple[Path, str, int]]) -> int:
    """Download each pending file atomically (temp file + os.replace)."""
    if not pending:
        return 0
    workers = min(_TRANSFER_CONCURRENCY, len(pending))

    def _one(item: tuple[Path, str, int]) -> None:
        local_path, key, _size = item
        local_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = local_path.parent / (local_path.name + _PARTIAL_SUFFIX)
        try:
            s3.download_file(bucket, key, str(tmp))
            os.replace(tmp, local_path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    transferred = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, item) for item in pending]
        for future in as_completed(futures):
            future.result()  # propagate transfer errors
            transferred += 1
    return transferred


def _upload_all(s3: Any, bucket: str, pending: list[tuple[Path, str]]) -> int:
    """Upload each pending local file to R2."""
    if not pending:
        return 0
    workers = min(_TRANSFER_CONCURRENCY, len(pending))

    def _one(item: tuple[Path, str]) -> None:
        path, key = item
        s3.upload_file(str(path), bucket, key)

    transferred = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, item) for item in pending]
        for future in as_completed(futures):
            future.result()  # propagate transfer errors
            transferred += 1
    return transferred


def _sync_set(
    s3: Any,
    bucket: str,
    mode: str,
    prefix: str,
    local_dir: Path,
) -> dict[str, int]:
    """Sync a single set; returns per-set counters for the summary line."""
    local_files = _iter_local(prefix, local_dir)
    local_by_key = {key: path for path, key in local_files}
    remote_sizes = _remote_sizes(s3, bucket, prefix)
    res = {
        "transferred": 0,
        "up_to_date": 0,
        "remote_missing": 0,
        "ok": 0,
        "missing_locally": 0,
        "missing_in_r2": 0,
        "size_mismatch": 0,
        "checksum_mismatch": 0,
    }

    if mode == "verify":
        all_keys = sorted(set(remote_sizes) | set(local_by_key))
        for key in all_keys:
            if key not in remote_sizes:
                res["missing_in_r2"] += 1
            elif key not in local_by_key:
                res["missing_locally"] += 1
            else:
                local_path = local_by_key[key]
                local_size = local_path.stat().st_size
                remote_size = remote_sizes[key]
                if abs(local_size - remote_size) > _SIZE_TOLERANCE_BYTES:
                    res["size_mismatch"] += 1
                elif local_size == remote_size and _sha256_local(local_path) != _sha256_remote(
                    s3, bucket, key
                ):
                    res["checksum_mismatch"] += 1
                else:
                    res["ok"] += 1
        return res

    if mode == "download":
        _remove_stale_partials(local_dir)
        if not remote_sizes:
            res["remote_missing"] = len(local_by_key)
            return res
        pending: list[tuple[Path, str, int]] = []
        for key, size in sorted(remote_sizes.items()):
            destination = _safe_local_path(prefix, local_dir, key)
            if destination is None:
                print(
                    f"{prefix}: skipped unsafe remote key: "
                    f"{_sanitize_key_for_display(key, prefix)}",
                    file=sys.stderr,
                )
                continue
            if (
                destination.exists()
                and abs(destination.stat().st_size - size) <= _SIZE_TOLERANCE_BYTES
            ):
                res["up_to_date"] += 1
            else:
                pending.append((destination, key, size))
        res["remote_missing"] = sum(1 for key in local_by_key if key not in remote_sizes)
        res["transferred"] = _download_all(s3, bucket, pending)
        return res

    # upload
    pending_uploads: list[tuple[Path, str]] = []
    for path, key in local_files:
        size = path.stat().st_size
        if key in remote_sizes and abs(remote_sizes[key] - size) <= _SIZE_TOLERANCE_BYTES:
            res["up_to_date"] += 1
        else:
            pending_uploads.append((path, key))
    res["transferred"] = _upload_all(s3, bucket, pending_uploads)
    return res


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Idempotent sync between local data dirs and Cloudflare R2."
    )
    parser.add_argument(
        "--upload", action="store_true", help="Upload local data to R2 (local -> R2)."
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Compare local vs R2 without transferring.",
    )
    parser.add_argument(
        "--only",
        choices=("corpus", "raw", "review", "all"),
        default="all",
        help="Restrict the operation to one sync set (default: all).",
    )
    args = parser.parse_args()
    args.mode = "verify" if args.verify else ("upload" if args.upload else "download")
    return args


def main() -> int:
    args = _parse_args()
    settings = _settings()

    missing = []
    if not settings.r2_account_id:
        missing.append("R2_ACCOUNT_ID")
    if not settings.r2_access_key_id.get_secret_value():
        missing.append("R2_ACCESS_KEY_ID")
    if not settings.r2_secret_access_key.get_secret_value():
        missing.append("R2_SECRET_ACCESS_KEY")
    if not settings.r2_bucket:
        missing.append("R2_BUCKET")
    if missing:
        print(
            f"Refusing to run: missing required R2 configuration: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    sets = (
        _SYNC_SETS if args.only == "all" else [item for item in _SYNC_SETS if item[0] == args.only]
    )

    if args.mode in ("upload", "verify"):
        for prefix, local_dir in sets:
            if not local_dir.exists():
                print(
                    f"Refusing to run: local directory for '{prefix}' does not exist: {local_dir}",
                    file=sys.stderr,
                )
                return 1

    s3 = _s3_client(settings)
    bucket = settings.r2_bucket

    totals = {
        "ok": 0,
        "missing_locally": 0,
        "missing_in_r2": 0,
        "size_mismatch": 0,
        "checksum_mismatch": 0,
    }
    for prefix, local_dir in sets:
        res = _sync_set(s3, bucket, args.mode, prefix, local_dir)
        if args.mode == "verify":
            totals["ok"] += res["ok"]
            totals["missing_locally"] += res["missing_locally"]
            totals["missing_in_r2"] += res["missing_in_r2"]
            totals["size_mismatch"] += res["size_mismatch"]
            totals["checksum_mismatch"] += res["checksum_mismatch"]
            print(
                f"{prefix}: ok={res['ok']}, missing_locally={res['missing_locally']}, "
                f"missing_in_r2={res['missing_in_r2']}, "
                f"size_mismatch={res['size_mismatch']}, "
                f"checksum_mismatch={res['checksum_mismatch']}"
            )
        else:
            print(
                f"{prefix}: {res['transferred']} transferred, "
                f"{res['up_to_date']} up-to-date, "
                f"{res['remote_missing']} remote-missing"
            )

    if args.mode == "verify":
        counters = (
            f"ok={totals['ok']}, missing_locally={totals['missing_locally']}, "
            f"missing_in_r2={totals['missing_in_r2']}, "
            f"size_mismatch={totals['size_mismatch']}, "
            f"checksum_mismatch={totals['checksum_mismatch']}"
        )
        drift = (
            totals["missing_locally"]
            + totals["missing_in_r2"]
            + totals["size_mismatch"]
            + totals["checksum_mismatch"]
        )
        # Report-only: drift is reported, not enforced, so the exit code stays 0.
        print(f"{'VERIFY MISMATCH' if drift else 'VERIFY OK'}: {counters}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
