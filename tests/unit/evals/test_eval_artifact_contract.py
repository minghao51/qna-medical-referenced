"""Offline contract tests for evaluation artifact persistence.

These tests only touch ``tmp_path`` and assert the exact failure surface of
``src.evals.artifacts`` (no live retrieval, no DeepEval, no network).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.evals.artifacts import ArtifactStore, find_reusable_run


def _temporary_siblings(target: Path) -> list[Path]:
    return sorted(target.parent.glob(f".{target.name}.*.tmp"))


def test_find_reusable_run_invalid_base_dir_behaviour(tmp_path: Path):
    """A missing run root yields no reuse; a non-directory run root raises."""
    missing_base = tmp_path / "missing-runs"

    assert find_reusable_run(missing_base, "test_identity") is None
    assert not missing_base.exists()

    file_base = tmp_path / "runs-is-a-file"
    file_base.write_text("not a directory", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        find_reusable_run(file_base, "test_identity")

    assert file_base.read_text(encoding="utf-8") == "not a directory"


def test_artifact_write_failure_leaves_no_partial_output(tmp_path: Path):
    """Writing onto unusable targets fails with the OS error and leaves no residue."""
    store = ArtifactStore(tmp_path / "evals", "write failure")

    # Target path already exists as a directory: os.replace() cannot publish the
    # temp file onto it and the temp sibling must be cleaned up.
    directory_target = store.path("occupied.json")
    directory_target.mkdir()

    with pytest.raises(IsADirectoryError):
        store.write_json("occupied.json", {"query_count": 1})

    assert directory_target.is_dir()
    assert list(directory_target.iterdir()) == []
    assert _temporary_siblings(directory_target) == []

    # Parent path is an existing regular file: the parent mkdir() fails before
    # any temp file is created.
    file_parent = store.path("parent-is-a-file")
    file_parent.write_text("blocker", encoding="utf-8")

    with pytest.raises(FileExistsError):
        store.write_json("parent-is-a-file/result.json", {"query_count": 1})

    assert file_parent.read_text(encoding="utf-8") == "blocker"
    assert sorted(path.name for path in store.run_dir.iterdir()) == [
        "occupied.json",
        "parent-is-a-file",
    ]
