"""Idempotent sync between local data directories and a Cloudflare R2 bucket.

Three sync sets (R2 prefix <-> local directory, resolved under the repo root):

- ``corpus``  <-> ``data/chroma-d11``
- ``raw``     <-> ``data/raw``
- ``review``  <-> ``data/evals/review``

Uploads and downloads are idempotent: a file is skipped when the remote
object's size differs from the local size by at most 100 bytes (the housing
convention), so re-running either direction only transfers what changed. A
local file with no remote object is treated as "needs upload".

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
        key = f"{prefix}/{path.relative_to(local_dir).as_posix()}"
        files.append((path, key))
    return files


def _remote_sizes(s3: Any, bucket: str, prefix: str) -> dict[str, int]:
    """Map of R2 object key -> size under ``prefix`` via paginated listing."""
    paginator = s3.get_paginator("list_objects_v2")
    sizes: dict[str, int] = {}
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            sizes[obj["Key"]] = obj["Size"]
    return sizes


def _download_all(s3: Any, bucket: str, pending: list[tuple[Path, str, int]]) -> int:
    """Download each pending file atomically (temp file + os.replace)."""
    if not pending:
        return 0
    workers = min(_TRANSFER_CONCURRENCY, len(pending))

    def _one(item: tuple[Path, str, int]) -> None:
        local_path, key, _size = item
        local_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = local_path.parent / (local_path.name + ".r2part")
        s3.download_file(bucket, key, str(tmp))
        os.replace(tmp, local_path)

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
    }

    if mode == "verify":
        all_keys = sorted(set(remote_sizes) | set(local_by_key))
        for key in all_keys:
            if key not in remote_sizes:
                res["missing_in_r2"] += 1
            elif key not in local_by_key:
                res["missing_locally"] += 1
            elif abs(local_by_key[key].stat().st_size - remote_sizes[key]) > _SIZE_TOLERANCE_BYTES:
                res["size_mismatch"] += 1
            else:
                res["ok"] += 1
        return res

    if mode == "download":
        if not remote_sizes:
            res["remote_missing"] = len(local_by_key)
            return res
        pending: list[tuple[Path, str, int]] = []
        for key, size in sorted(remote_sizes.items()):
            local_path = local_by_key.get(key)
            if local_path is None:
                rel = key.removeprefix(prefix + "/")
                local_path = local_dir / rel
            if (
                local_path.exists()
                and abs(local_path.stat().st_size - size) <= _SIZE_TOLERANCE_BYTES
            ):
                res["up_to_date"] += 1
            else:
                pending.append((local_path, key, size))
        res["remote_missing"] = sum(1 for key in local_by_key if key not in remote_sizes)
        res["transferred"] = _download_all(s3, bucket, pending)
        return res

    # upload
    pending = []
    for path, key in local_files:
        size = path.stat().st_size
        if key in remote_sizes and abs(remote_sizes[key] - size) <= _SIZE_TOLERANCE_BYTES:
            res["up_to_date"] += 1
        else:
            pending.append((path, key))
    res["transferred"] = _upload_all(s3, bucket, pending)
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
    }
    for prefix, local_dir in sets:
        res = _sync_set(s3, bucket, args.mode, prefix, local_dir)
        if args.mode == "verify":
            totals["ok"] += res["ok"]
            totals["missing_locally"] += res["missing_locally"]
            totals["missing_in_r2"] += res["missing_in_r2"]
            totals["size_mismatch"] += res["size_mismatch"]
            print(
                f"{prefix}: ok={res['ok']}, missing_locally={res['missing_locally']}, "
                f"missing_in_r2={res['missing_in_r2']}, "
                f"size_mismatch={res['size_mismatch']}"
            )
        else:
            print(
                f"{prefix}: {res['transferred']} transferred, "
                f"{res['up_to_date']} up-to-date, "
                f"{res['remote_missing']} remote-missing"
            )

    if args.mode == "verify":
        print(
            f"VERIFY OK: ok={totals['ok']}, missing_locally={totals['missing_locally']}, "
            f"missing_in_r2={totals['missing_in_r2']}, "
            f"size_mismatch={totals['size_mismatch']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
