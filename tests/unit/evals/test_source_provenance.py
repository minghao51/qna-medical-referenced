from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from src.evals.assessment import reporting


def _git(root: Path, *args: str) -> bytes:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    result = subprocess.run(
        ["git", "-c", f"core.hooksPath={os.devnull}", *args],
        cwd=root,
        env=env,
        check=True,
        capture_output=True,
    )
    return result.stdout


def _repository(root: Path) -> Path:
    root.mkdir()
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (root / "src" / "nested").mkdir(parents=True)
    (root / "src" / "app.py").write_text("VALUE = 'before'\n", encoding="utf-8")
    (root / "src" / "nested" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "init", "--quiet")
    _git(root, "add", "uv.lock", "src")
    _git(
        root,
        "-c",
        "user.name=Provenance Fixture",
        "-c",
        "user.email=provenance@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "fixture",
    )
    return root


def test_source_provenance_reports_bounded_verified_fixture(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")

    provenance = reporting.source_provenance(root)

    assert provenance["version"] == 1
    assert provenance["status"] == "verified"
    assert provenance["reason"] is None
    assert provenance["scope"] == "src-python-v1"
    assert provenance["dirty"] is False
    assert provenance["git_head"] == _git(root, "rev-parse", "HEAD").decode().strip()
    assert re.fullmatch(r"[0-9a-f]{64}", provenance["source_content_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", provenance["dependency_lock_sha256"])
    assert any("not an atomic whole-tree snapshot" in text for text in provenance["limitations"])
    assert any("promotion-eligibility" in text for text in provenance["limitations"])


def test_default_root_comes_from_module_location_not_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repository(tmp_path / "repo")
    module_path = root / "src" / "evals" / "assessment" / "reporting.py"
    monkeypatch.setattr(reporting, "__file__", str(module_path))

    provenance = reporting.source_provenance()

    assert provenance["status"] == "verified"
    assert provenance["git_head"] == _git(root, "rev-parse", "HEAD").decode().strip()


def test_detached_head_is_valid_and_missing_git_is_unverified(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")
    _git(root, "checkout", "--detach", "--quiet", "HEAD")

    detached = reporting.source_provenance(root)
    assert detached["status"] == "verified"
    assert detached["git_head"] == _git(root, "rev-parse", "HEAD").decode().strip()

    no_git = tmp_path / "not-a-repository"
    no_git.mkdir()
    (no_git / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (no_git / "src").mkdir()
    (no_git / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")

    missing = reporting.source_provenance(no_git)
    assert missing["status"] == "unverified"
    assert missing["reason"] == "git_metadata_unavailable"
    assert missing["git_head"] is None
    assert missing["dirty"] is None
    assert str(no_git) not in repr(missing)


def test_source_and_lock_content_changes_affect_digests_with_preserved_mtime(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path / "repo")
    before = reporting.source_provenance(root)

    source = root / "src" / "app.py"
    source_stat = source.stat()
    source.write_text("VALUE = 'after!'\n", encoding="utf-8")
    os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
    after_source = reporting.source_provenance(root)
    assert after_source["source_content_sha256"] != before["source_content_sha256"]
    assert after_source["dirty"] is True

    lock = root / "uv.lock"
    lock_stat = lock.stat()
    lock.write_text("version = 2\n", encoding="utf-8")
    os.utime(lock, ns=(lock_stat.st_atime_ns, lock_stat.st_mtime_ns))
    after_lock = reporting.source_provenance(root)
    assert after_lock["dependency_lock_sha256"] != before["dependency_lock_sha256"]
    assert after_lock["dirty"] is True


def test_untracked_source_addition_and_deletion_change_inventory_digest(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")
    original = reporting.source_provenance(root)
    added_source = root / "src" / "untracked.py"
    added_source.write_text("ADDED = True\n", encoding="utf-8")

    added = reporting.source_provenance(root)
    assert added["status"] == "verified"
    assert added["dirty"] is True
    assert added["source_content_sha256"] != original["source_content_sha256"]

    added_source.unlink()
    deleted = reporting.source_provenance(root)
    assert deleted["status"] == "verified"
    assert deleted["dirty"] is False
    assert deleted["source_content_sha256"] == original["source_content_sha256"]


def test_git_dirty_includes_untracked_paths_without_returning_path_or_status(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path / "repo")
    (root / "src" / "secret-path-canary.py").write_text(
        "VALUE = 'raw-content-canary'\n", encoding="utf-8"
    )

    provenance = reporting.source_provenance(root)
    returned = repr(provenance)
    assert provenance["status"] == "verified"
    assert provenance["dirty"] is True
    assert "secret-path-canary" not in returned
    assert "raw-content-canary" not in returned
    assert "??" not in returned


def test_non_source_secret_configuration_is_not_hashed_or_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repository(tmp_path / "repo")
    protected_files = {
        ".env": "TOKEN=secret-value-canary\n",
        "config/settings.yaml": "api_key: settings-value-canary\n",
        "secrets.json": '{"secret": "secret-file-canary"}\n',
    }
    for relative_path, content in protected_files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    opened_paths: list[str] = []
    original_hash = reporting._hash_designated_file

    def recording_hash(root_fd, relative_path, **kwargs):
        opened_paths.append(relative_path)
        return original_hash(root_fd, relative_path, **kwargs)

    monkeypatch.setattr(reporting, "_hash_designated_file", recording_hash)
    first = reporting.source_provenance(root)
    for relative_path, content in protected_files.items():
        (root / relative_path).write_text(content + "changed\n", encoding="utf-8")
    second = reporting.source_provenance(root)

    assert first["source_content_sha256"] == second["source_content_sha256"]
    assert first["dependency_lock_sha256"] == second["dependency_lock_sha256"]
    assert set(opened_paths) == {
        "uv.lock",
        "src/app.py",
        "src/nested/module.py",
    }
    serialized = repr(second)
    for marker in (".env", "settings.yaml", "secrets.json", "secret-value-canary"):
        assert marker not in serialized


@pytest.mark.parametrize("link_kind", ["source_file", "source_directory", "source_root"])
def test_source_symlinks_fail_closed(tmp_path: Path, link_kind: str) -> None:
    root = _repository(tmp_path / "repo")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside.py").write_text("OUTSIDE = True\n", encoding="utf-8")

    if link_kind == "source_file":
        (root / "src" / "linked.py").symlink_to(outside / "outside.py")
    elif link_kind == "source_directory":
        (root / "src" / "linked").symlink_to(outside, target_is_directory=True)
    else:
        source_root = root / "src"
        source_root.rename(root / "src-real")
        source_root.symlink_to(root / "src-real", target_is_directory=True)

    provenance = reporting.source_provenance(root)
    assert provenance["status"] == "unverified"
    assert provenance["reason"] == "source_scope_unavailable"
    assert provenance["source_content_sha256"] is None
    assert str(outside) not in repr(provenance)


def test_symlinked_repository_root_and_lock_fail_closed(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")
    root_link = tmp_path / "repo-link"
    root_link.symlink_to(root, target_is_directory=True)
    linked_root = reporting.source_provenance(root_link)
    assert linked_root["status"] == "unverified"
    assert linked_root["reason"] == "repository_unavailable"

    lock = root / "uv.lock"
    lock.unlink()
    lock.symlink_to(tmp_path / "outside-lock")
    lock_provenance = reporting.source_provenance(root)
    assert lock_provenance["status"] == "unverified"
    assert lock_provenance["reason"] == "dependency_lock_unavailable"
    assert lock_provenance["dependency_lock_sha256"] is None
    assert str(root) not in repr(lock_provenance)


def test_source_read_error_is_sanitized_and_unverified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repository(tmp_path / "repo")
    original_hash = reporting._hash_designated_file

    def fail_source_read(root_fd, relative_path, **kwargs):
        if relative_path.endswith(".py"):
            raise PermissionError("private /absolute/path and secret-canary")
        return original_hash(root_fd, relative_path, **kwargs)

    monkeypatch.setattr(reporting, "_hash_designated_file", fail_source_read)
    provenance = reporting.source_provenance(root)

    assert provenance["status"] == "unverified"
    assert provenance["reason"] == "snapshot_unstable"
    assert provenance["source_content_sha256"] is None
    assert "/absolute/path" not in repr(provenance)
    assert "secret-canary" not in repr(provenance)


def test_source_drift_during_capture_fails_closed(tmp_path: Path, monkeypatch) -> None:
    root = _repository(tmp_path / "repo")
    source = root / "src" / "app.py"
    source_stat = source.stat()
    original_hash = reporting._hash_designated_file
    changed = False

    def mutate_after_source_read(root_fd, relative_path, **kwargs):
        nonlocal changed
        outcome = original_hash(root_fd, relative_path, **kwargs)
        if relative_path == "src/app.py" and not changed:
            changed = True
            source.write_text("VALUE = 'changed'\n", encoding="utf-8")
            os.utime(source, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        return outcome

    monkeypatch.setattr(reporting, "_hash_designated_file", mutate_after_source_read)
    provenance = reporting.source_provenance(root)

    assert changed is True
    assert provenance["status"] == "unverified"
    assert provenance["reason"] == "snapshot_unstable"
    assert provenance["source_content_sha256"] is None


def test_missing_lock_or_source_scope_is_unverified(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")
    (root / "uv.lock").unlink()

    missing_lock = reporting.source_provenance(root)
    assert missing_lock["status"] == "unverified"
    assert missing_lock["reason"] == "dependency_lock_unavailable"

    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    source_root = root / "src"
    for path in source_root.rglob("*.py"):
        path.unlink()
    missing_source = reporting.source_provenance(root)
    assert missing_source["status"] == "unverified"
    assert missing_source["reason"] == "source_scope_unavailable"
    assert missing_source["source_content_sha256"] is None
