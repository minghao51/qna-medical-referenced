"""Reporting helpers for evaluation runs."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def git_head() -> str | None:
    try:
        result = subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception as e:
        logger.debug("Failed to get git HEAD: %s", e)
        return None


def sha256_file(path: str | Path | None) -> str | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


_PROVENANCE_SCOPE = "src-python-v1"
_PROVENANCE_LIMITATIONS = [
    "Covers src/**/*.py, uv.lock, and Git revision/status only.",
    "This is not an atomic whole-tree snapshot or a complete runtime semantic identity.",
    "Not a promotion-eligibility signal.",
]
_MAX_CORPUS_ENTRIES = 20_000
_MAX_CORPUS_FILES = 10_000
_MAX_CORPUS_BYTES = 512 * 1024 * 1024


class _ProvenanceFailure(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class _SnapshotUnstable(Exception):
    pass


def _stat_signature(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        stat.S_IFMT(info.st_mode),
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _safe_repository_root(root: Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(root)))
    try:
        for component in reversed((absolute, *absolute.parents)):
            info = component.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise _ProvenanceFailure("repository_unavailable")
        if not stat.S_ISDIR(absolute.lstat().st_mode):
            raise _ProvenanceFailure("repository_unavailable")
    except OSError as exc:
        raise _ProvenanceFailure("repository_unavailable") from exc
    return absolute


def _git_command(root: Path, *args: str) -> bytes:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    try:
        result = subprocess.run(  # nosec B603
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                *args,
            ],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise _ProvenanceFailure("git_metadata_unavailable") from exc
    return result.stdout


def _git_snapshot(root: Path) -> tuple[str, bytes]:
    try:
        top_level = _git_command(root, "rev-parse", "--show-toplevel")
        reported_root = os.fsdecode(top_level.rstrip(b"\n"))
        if os.path.normcase(os.path.abspath(reported_root)) != os.path.normcase(str(root)):
            raise _ProvenanceFailure("git_metadata_unavailable")

        revision = _git_command(root, "rev-parse", "--verify", "HEAD^{commit}").strip()
        revision_text = revision.decode("ascii")
        if len(revision_text) not in (40, 64) or any(
            character not in "0123456789abcdefABCDEF" for character in revision_text
        ):
            raise _ProvenanceFailure("git_metadata_unavailable")
        status = _git_command(
            root,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--no-renames",
        )
    except (UnicodeError, OSError) as exc:
        raise _ProvenanceFailure("git_metadata_unavailable") from exc
    return revision_text.lower(), status


def _open_directory(parent_fd: int, name: str) -> int:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise _ProvenanceFailure("source_scope_unavailable")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise _ProvenanceFailure("source_scope_unavailable") from exc


def _inventory_source(
    root_fd: int,
) -> tuple[dict[str, tuple[int, ...]], dict[str, tuple[int, ...]]]:
    directories: dict[str, tuple[int, ...]] = {}
    source_files: dict[str, tuple[int, ...]] = {}
    try:
        src_info = os.stat("src", dir_fd=root_fd, follow_symlinks=False)
        if not stat.S_ISDIR(src_info.st_mode):
            raise _ProvenanceFailure("source_scope_unavailable")
        src_fd = _open_directory(root_fd, "src")
    except OSError as exc:
        raise _ProvenanceFailure("source_scope_unavailable") from exc

    try:
        if _stat_signature(os.fstat(src_fd)) != _stat_signature(src_info):
            raise _SnapshotUnstable
        directories["src"] = _stat_signature(src_info)

        def walk(directory_fd: int, relative_directory: str) -> None:
            try:
                names = sorted(os.listdir(directory_fd), key=os.fsencode)
            except OSError as exc:
                raise _ProvenanceFailure("source_scope_unavailable") from exc
            for name in names:
                relative_path = f"{relative_directory}/{name}"
                try:
                    info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                except OSError as exc:
                    raise _ProvenanceFailure("source_scope_unavailable") from exc
                if stat.S_ISLNK(info.st_mode):
                    raise _ProvenanceFailure("source_scope_unavailable")
                if stat.S_ISDIR(info.st_mode):
                    child_fd = _open_directory(directory_fd, name)
                    try:
                        if _stat_signature(os.fstat(child_fd)) != _stat_signature(info):
                            raise _SnapshotUnstable
                        directories[relative_path] = _stat_signature(info)
                        walk(child_fd, relative_path)
                    finally:
                        os.close(child_fd)
                elif name.endswith(".py"):
                    if not stat.S_ISREG(info.st_mode):
                        raise _ProvenanceFailure("source_scope_unavailable")
                    source_files[relative_path] = _stat_signature(info)

        walk(src_fd, "src")
    finally:
        os.close(src_fd)

    if not source_files:
        raise _ProvenanceFailure("source_scope_unavailable")
    return directories, source_files


def _hash_designated_file(
    root_fd: int,
    relative_path: str,
    *,
    expected_signature: tuple[int, ...] | None = None,
    directory_signatures: dict[str, tuple[int, ...]] | None = None,
) -> tuple[str, int]:
    parts = relative_path.split("/")
    parent_fd = os.dup(root_fd)
    directory_parts: list[str] = []
    try:
        for part in parts[:-1]:
            directory_parts.append(part)
            child_fd = _open_directory(parent_fd, part)
            try:
                expected_directory = (directory_signatures or {}).get("/".join(directory_parts))
                if (
                    expected_directory is not None
                    and _stat_signature(os.fstat(child_fd)) != expected_directory
                ):
                    raise _SnapshotUnstable
            except Exception:
                os.close(child_fd)
                raise
            os.close(parent_fd)
            parent_fd = child_fd

        name = parts[-1]
        try:
            before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as exc:
            raise _ProvenanceFailure("source_scope_unavailable") from exc
        if not stat.S_ISREG(before.st_mode):
            raise _ProvenanceFailure("source_scope_unavailable")
        before_signature = _stat_signature(before)
        if expected_signature is not None and before_signature != expected_signature:
            raise _SnapshotUnstable
        if not hasattr(os, "O_NOFOLLOW"):
            raise _ProvenanceFailure("source_scope_unavailable")
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            file_fd = os.open(name, flags, dir_fd=parent_fd)
        except OSError as exc:
            raise _ProvenanceFailure("source_scope_unavailable") from exc

        digest = hashlib.sha256()
        byte_count = 0
        try:
            if _stat_signature(os.fstat(file_fd)) != before_signature:
                raise _SnapshotUnstable
            while chunk := os.read(file_fd, 1024 * 1024):
                digest.update(chunk)
                byte_count += len(chunk)
            after_fd = _stat_signature(os.fstat(file_fd))
        finally:
            os.close(file_fd)

        try:
            after_path = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as exc:
            raise _ProvenanceFailure("source_scope_unavailable") from exc
        after_signature = _stat_signature(after_path)
        if (
            after_signature != before_signature
            or after_fd != before_signature
            or byte_count != before.st_size
        ):
            raise _SnapshotUnstable
        return digest.hexdigest(), byte_count
    finally:
        os.close(parent_fd)


def _root_still_stable(root: Path, root_fd: int, signature: tuple[int, ...]) -> bool:
    try:
        info = root.lstat()
        return (
            not stat.S_ISLNK(info.st_mode)
            and stat.S_ISDIR(info.st_mode)
            and _stat_signature(info) == signature
            and _stat_signature(os.fstat(root_fd)) == signature
        )
    except OSError:
        return False


def source_provenance(root: Path | None = None) -> dict[str, Any]:
    """Capture bounded, non-secret provenance for Git, uv.lock, and src Python files.

    The source digest covers the names and bytes of all regular ``src/**/*.py`` files,
    whether tracked or untracked. This is a stable best-effort capture, not an atomic
    snapshot of the entire repository or a complete runtime semantic identity.
    """
    result: dict[str, Any] = {
        "version": 1,
        "status": "unverified",
        "git_head": None,
        "dirty": None,
        "source_content_sha256": None,
        "dependency_lock_sha256": None,
        "scope": _PROVENANCE_SCOPE,
        "reason": None,
        "limitations": list(_PROVENANCE_LIMITATIONS),
    }
    root_fd: int | None = None
    try:
        requested_root = root if root is not None else Path(__file__).resolve().parents[3]
        repository_root = _safe_repository_root(requested_root)
        root_stat = repository_root.lstat()
        root_signature = _stat_signature(root_stat)
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise _ProvenanceFailure("repository_unavailable")
        root_fd = os.open(
            repository_root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
        )
        if _stat_signature(os.fstat(root_fd)) != root_signature:
            raise _ProvenanceFailure("snapshot_unstable")

        git_before = _git_snapshot(repository_root)
        result["git_head"] = git_before[0]
        result["dirty"] = bool(git_before[1])

        try:
            lock_digest, _ = _hash_designated_file(root_fd, "uv.lock")
        except (_ProvenanceFailure, OSError, _SnapshotUnstable):
            raise _ProvenanceFailure("dependency_lock_unavailable") from None
        result["dependency_lock_sha256"] = lock_digest

        directories_before, files_before = _inventory_source(root_fd)
        source_digest = hashlib.sha256()
        source_digest.update(b"src-python-v1\0")
        for relative_path in sorted(files_before, key=os.fsencode):
            path_bytes = os.fsencode(relative_path)
            file_digest, file_size = _hash_designated_file(
                root_fd,
                relative_path,
                expected_signature=files_before[relative_path],
                directory_signatures=directories_before,
            )
            digest_bytes = bytes.fromhex(file_digest)
            source_digest.update(len(path_bytes).to_bytes(8, "big"))
            source_digest.update(path_bytes)
            source_digest.update(file_size.to_bytes(8, "big"))
            source_digest.update(digest_bytes)

        directories_after, files_after = _inventory_source(root_fd)
        if directories_after != directories_before or files_after != files_before:
            raise _ProvenanceFailure("snapshot_unstable")
        try:
            final_lock_digest, _ = _hash_designated_file(root_fd, "uv.lock")
        except (_ProvenanceFailure, OSError, _SnapshotUnstable):
            raise _ProvenanceFailure("dependency_lock_unavailable") from None
        if final_lock_digest != lock_digest:
            raise _ProvenanceFailure("snapshot_unstable")
        if not _root_still_stable(repository_root, root_fd, root_signature):
            raise _ProvenanceFailure("snapshot_unstable")
        _safe_repository_root(repository_root)
        git_after = _git_snapshot(repository_root)
        if git_after != git_before:
            raise _ProvenanceFailure("snapshot_unstable")

        result["source_content_sha256"] = source_digest.hexdigest()
        result["status"] = "verified"
    except _ProvenanceFailure as exc:
        result["reason"] = exc.reason
        result["source_content_sha256"] = None
    except Exception:
        result["reason"] = "snapshot_unstable"
        result["source_content_sha256"] = None
    finally:
        if root_fd is not None:
            try:
                os.close(root_fd)
            except OSError:
                result["status"] = "unverified"
                result["reason"] = "snapshot_unstable"
                result["source_content_sha256"] = None
    return result


def content_directory_provenance(root: Path) -> dict[str, Any]:
    """Hash a stable tree of regular source files without returning paths or contents."""
    result: dict[str, Any] = {
        "version": 1,
        "status": "unverified",
        "content_sha256": None,
        "file_count": 0,
        "reason": None,
    }
    try:
        directory = Path(os.path.abspath(os.fspath(root)))
        for component in reversed((directory, *directory.parents)):
            info = component.lstat()
            if stat.S_ISLNK(info.st_mode):
                result["reason"] = "source_tree_unavailable"
                return result
        if not stat.S_ISDIR(directory.lstat().st_mode):
            result["reason"] = "source_tree_unavailable"
            return result
        before: list[Path] = []
        for path in directory.rglob("*"):
            before.append(path)
            if len(before) > _MAX_CORPUS_ENTRIES:
                result["reason"] = "source_tree_too_large"
                return result
        before.sort(key=lambda path: os.fsencode(str(path)))
        signatures: dict[str, tuple[int, ...]] = {}
        for path in before:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                result["reason"] = "source_tree_unavailable"
                return result
            if stat.S_ISREG(info.st_mode):
                signatures[str(path.relative_to(directory))] = _stat_signature(info)
            elif not stat.S_ISDIR(info.st_mode):
                result["reason"] = "source_tree_unavailable"
                return result
        total_bytes = sum(signature[3] for signature in signatures.values())
        if len(signatures) > _MAX_CORPUS_FILES or total_bytes > _MAX_CORPUS_BYTES:
            result["reason"] = "source_tree_too_large"
            return result
        if not signatures:
            result["reason"] = "source_tree_empty"
            return result

        digest = hashlib.sha256(b"source-tree-v1\0")
        for relative_path in sorted(signatures, key=os.fsencode):
            path = directory / relative_path
            before_signature = signatures[relative_path]
            if _stat_signature(path.lstat()) != before_signature:
                result["reason"] = "source_tree_unstable"
                return result
            if not hasattr(os, "O_NOFOLLOW"):
                result["reason"] = "source_tree_unavailable"
                return result
            file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
            try:
                if _stat_signature(os.fstat(file_fd)) != before_signature:
                    result["reason"] = "source_tree_unstable"
                    return result
                file_hash = hashlib.sha256()
                byte_count = 0
                while chunk := os.read(file_fd, 1024 * 1024):
                    file_hash.update(chunk)
                    byte_count += len(chunk)
                after_signature = _stat_signature(os.fstat(file_fd))
            finally:
                os.close(file_fd)
            if (
                byte_count != before_signature[3]
                or after_signature != before_signature
                or _stat_signature(path.lstat()) != before_signature
            ):
                result["reason"] = "source_tree_unstable"
                return result
            path_bytes = os.fsencode(relative_path)
            digest.update(len(path_bytes).to_bytes(8, "big"))
            digest.update(path_bytes)
            digest.update(before_signature[3].to_bytes(8, "big"))
            digest.update(file_hash.digest())

        after: list[Path] = []
        for path in directory.rglob("*"):
            after.append(path)
            if len(after) > _MAX_CORPUS_ENTRIES:
                result["reason"] = "source_tree_unstable"
                return result
        after.sort(key=lambda path: os.fsencode(str(path)))
        after_signatures: dict[str, tuple[int, ...]] = {}
        for path in after:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                result["reason"] = "source_tree_unstable"
                return result
            if stat.S_ISREG(info.st_mode):
                after_signatures[str(path.relative_to(directory))] = _stat_signature(info)
        if after_signatures != signatures or len(after) != len(before):
            result["reason"] = "source_tree_unstable"
            return result
        result.update(
            status="verified",
            content_sha256=digest.hexdigest(),
            file_count=len(signatures),
        )
    except OSError:
        result["reason"] = "source_tree_unavailable"
    return result


def _format_dict_as_table(d: dict[str, Any], indent: str = "  ") -> list[str]:
    if not d:
        return [f"{indent}(empty)"]
    keys = list(d.keys())
    lines = [
        f"{indent}| Metric | Value |",
        f"{indent}|--------|-------|",
    ]
    for k in keys:
        v = d[k]
        if isinstance(v, dict):
            lines.append(f"{indent}| **{k}** | |")
            lines.extend(_format_dict_as_table(v, indent + "  "))
        elif isinstance(v, list):
            lines.append(f"{indent}| {k} | `{json.dumps(v, ensure_ascii=False)}` |")
        elif isinstance(v, float):
            lines.append(f"{indent}| {k} | {v:.4f} |")
        else:
            lines.append(f"{indent}| {k} | `{v}` |")
    return lines


def render_summary(
    *,
    step_metrics: dict[str, Any],
    retrieval_metrics: dict[str, Any],
    l6_answer_quality_metrics: dict[str, Any],
    dataset_stats: dict[str, Any],
    failed_thresholds: list[dict[str, Any]],
    usage_summary: dict[str, Any] | None = None,
) -> str:
    lines = [
        "# Pipeline Quality Assessment Summary",
        "",
        "## Dataset",
        f"- Fixture records: {dataset_stats.get('fixture_records', 0)}",
        f"- Synthetic records: {dataset_stats.get('synthetic_records', 0)}",
        f"- Merged records: {dataset_stats.get('merged_records', 0)}",
        "",
        "## Step Metrics",
    ]
    for stage in ["l0", "l1", "l2", "l3", "l4", "l5"]:
        agg = step_metrics.get(stage, {}).get("aggregate", {})
        lines.append(f"### {stage.upper()}")
        lines.extend(_format_dict_as_table(agg))
        lines.append("")
    lines.extend(
        [
            "## Retrieval Metrics (L6)",
        ]
    )
    lines.extend(_format_dict_as_table(retrieval_metrics))
    lines.extend(
        [
            "",
            "## L6 Answer Quality",
        ]
    )
    lines.extend(_format_dict_as_table(l6_answer_quality_metrics))
    lines.extend(
        [
            "",
            "## Usage Summary",
        ]
    )
    lines.extend(_format_dict_as_table(usage_summary or {"status": "unknown"}))
    lines.extend(
        [
            "",
            "## Threshold Failures",
        ]
    )
    if failed_thresholds:
        lines.append("| Metric | Value | Threshold Op | Threshold Value |")
        lines.append("|--------|-------|-------------|-----------------|")
        for failure in failed_thresholds:
            lines.append(
                f"| {failure['metric']} | {failure['value']} "
                f"| {failure['threshold_op']} | {failure['threshold_value']} |"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"
