"""Offline tests for the manual R2 sync script.

Loads ``scripts/manual/r2_sync.py`` through importlib and exercises it against
in-memory fakes for ``boto3``/``botocore.config`` plus tmp-path sync
directories. No network, no real boto3 client, no real R2 credentials.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
import types
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "manual" / "r2_sync.py"
_MODULE_NAME = "r2_sync_under_test"
_PREFIXES = ("corpus", "raw", "review")
_FAKE_KEY = "AKIA_FAKE_KEY_123"
_FAKE_SECRET = "FAKE_SECRET_VALUE_456"
_ENV = {
    "R2_ACCOUNT_ID": "account_under_test",
    "R2_ACCESS_KEY_ID": _FAKE_KEY,
    "R2_SECRET_ACCESS_KEY": _FAKE_SECRET,
    "R2_BUCKET": "fake-bucket",
}


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("R2 sync script could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _StubS3:
    """In-memory stand-in for the boto3 S3 client used by the script."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.page_size = 1000
        self.list_calls: list[str] = []
        self.list_buckets: list[str] = []
        self.downloads: list[tuple[str, str]] = []
        self.uploads: list[tuple[str, Path]] = []
        self.get_object_calls: list[str] = []
        self.fail_download_keys: set[str] = set()

    def get_paginator(self, name: str) -> _StubS3:
        if name != "list_objects_v2":
            raise AssertionError(f"unexpected paginator: {name}")
        return self

    def paginate(self, *, Bucket: str, Prefix: str) -> Iterator[dict[str, Any]]:
        self.list_calls.append(Prefix)
        self.list_buckets.append(Bucket)
        keys = sorted(key for key in self.objects if key.startswith(Prefix))
        for start in range(0, len(keys), self.page_size):
            chunk = keys[start : start + self.page_size]
            yield {"Contents": [{"Key": key, "Size": len(self.objects[key])} for key in chunk]}
        if not keys:
            yield {"Contents": []}

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        self.downloads.append((key, filename))
        if key in self.fail_download_keys:
            Path(filename).write_bytes(b"partial")
            raise OSError(f"synthetic transfer failure for {key}")
        Path(filename).write_bytes(self.objects[key])

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        self.get_object_calls.append(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        path = Path(filename)
        self.uploads.append((key, path))
        self.objects[key] = path.read_bytes()


@dataclass
class _FakeAws:
    s3: _StubS3
    client_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _R2UnderTest:
    module: ModuleType
    aws: _FakeAws
    dirs: dict[str, Path]

    @property
    def s3(self) -> _StubS3:
        return self.aws.s3


def _install_fake_aws(monkeypatch: pytest.MonkeyPatch) -> _FakeAws:
    aws = _FakeAws(s3=_StubS3())

    def client(service_name: str, **kwargs: Any) -> _StubS3:
        aws.client_calls.append({"service_name": service_name, **kwargs})
        return aws.s3

    def config(**kwargs: Any) -> dict[str, Any]:
        return kwargs

    boto3_module = types.ModuleType("boto3")
    boto3_module.client = client  # type: ignore[attr-defined]
    botocore_module = types.ModuleType("botocore")
    botocore_config_module = types.ModuleType("botocore.config")
    botocore_config_module.Config = config  # type: ignore[attr-defined]
    botocore_module.config = botocore_config_module  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "boto3", boto3_module)
    monkeypatch.setitem(sys.modules, "botocore", botocore_module)
    monkeypatch.setitem(sys.modules, "botocore.config", botocore_config_module)
    return aws


@pytest.fixture
def r2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _R2UnderTest:
    monkeypatch.chdir(tmp_path)  # keeps the repo's real .env out of R2Settings
    for name in (*_ENV, "R2_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)

    aws = _install_fake_aws(monkeypatch)
    module = _load_module()
    dirs = {name: tmp_path / f"sync-{name}" for name in _PREFIXES}

    monkeypatch.setattr(module, "CORPUS_DIR", dirs["corpus"])
    monkeypatch.setattr(module, "RAW_DIR", dirs["raw"])
    monkeypatch.setattr(module, "REVIEW_DIR", dirs["review"])
    # _SYNC_SETS is bound at import time, so rebuild it from the patched constants.
    monkeypatch.setattr(module, "_SYNC_SETS", tuple((name, dirs[name]) for name in _PREFIXES))
    monkeypatch.setattr(sys, "argv", ["r2_sync.py"])
    return _R2UnderTest(module=module, aws=aws, dirs=dirs)


def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in _ENV.items():
        monkeypatch.setenv(name, value)


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _make_dirs(r2: _R2UnderTest) -> None:
    for local_dir in r2.dirs.values():
        local_dir.mkdir(parents=True, exist_ok=True)


def _run(r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["r2_sync.py", *args])
    return int(r2.module.main())


def _r2part_files(r2: _R2UnderTest) -> list[Path]:
    found: list[Path] = []
    for local_dir in r2.dirs.values():
        if local_dir.exists():
            found.extend(local_dir.rglob("*.r2part"))
    return found


def test_missing_config_refuses_and_never_builds_client(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    exit_code = _run(r2, monkeypatch)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1
    assert "Refusing to run" in captured.err
    assert "R2_ACCESS_KEY_ID" in captured.err
    assert r2.aws.client_calls == []


def test_settings_read_from_env_and_endpoint_derived_from_account(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch
):
    _set_env(monkeypatch)
    settings = r2.module.R2Settings()

    assert settings.r2_account_id == _ENV["R2_ACCOUNT_ID"]
    assert settings.r2_access_key_id.get_secret_value() == _FAKE_KEY
    assert settings.r2_secret_access_key.get_secret_value() == _FAKE_SECRET
    assert settings.r2_bucket == _ENV["R2_BUCKET"]
    assert settings.r2_endpoint == ""

    assert _run(r2, monkeypatch) == 0
    assert len(r2.aws.client_calls) == 1
    call = r2.aws.client_calls[0]
    assert call["service_name"] == "s3"
    assert call["endpoint_url"] == (f"https://{_ENV['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com")
    assert call["region_name"] == "auto"


def test_endpoint_override_is_used_verbatim(r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch):
    _set_env(monkeypatch)
    monkeypatch.setenv("R2_ENDPOINT", "https://r2.example.test/custom-endpoint")

    assert r2.module.R2Settings().r2_endpoint == "https://r2.example.test/custom-endpoint"
    assert _run(r2, monkeypatch) == 0
    assert r2.aws.client_calls[0]["endpoint_url"] == "https://r2.example.test/custom-endpoint"


def test_download_happy_path(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _set_env(monkeypatch)
    r2.s3.page_size = 1  # exercise pagination
    r2.s3.objects = {"corpus/A.txt": b"alpha", "raw/nested/b.bin": b"beta"}

    exit_code = _run(r2, monkeypatch)

    assert exit_code == 0
    assert (r2.dirs["corpus"] / "A.txt").read_bytes() == b"alpha"
    assert (r2.dirs["raw"] / "nested" / "b.bin").read_bytes() == b"beta"
    assert sorted(r2.s3.list_calls) == ["corpus", "raw", "review"]
    assert [key for key, _ in r2.s3.downloads] == ["corpus/A.txt", "raw/nested/b.bin"]
    assert _r2part_files(r2) == []
    assert capsys.readouterr().out.splitlines() == [
        "corpus: 1 transferred, 0 up-to-date, 0 remote-missing",
        "raw: 1 transferred, 0 up-to-date, 0 remote-missing",
        "review: 0 transferred, 0 up-to-date, 0 remote-missing",
    ]


def test_upload_happy_path(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _set_env(monkeypatch)
    _make_dirs(r2)
    _write(r2.dirs["corpus"] / "docs" / "one.txt", b"one")
    _write(r2.dirs["raw"] / "two.txt", b"two")

    exit_code = _run(r2, monkeypatch, "--upload")

    assert exit_code == 0
    assert sorted(key for key, _ in r2.s3.uploads) == ["corpus/docs/one.txt", "raw/two.txt"]
    assert r2.s3.objects["corpus/docs/one.txt"] == b"one"
    assert r2.s3.objects["raw/two.txt"] == b"two"
    assert r2.s3.downloads == []
    assert capsys.readouterr().out.splitlines() == [
        "corpus: 1 transferred, 0 up-to-date, 0 remote-missing",
        "raw: 1 transferred, 0 up-to-date, 0 remote-missing",
        "review: 0 transferred, 0 up-to-date, 0 remote-missing",
    ]


def test_download_skips_within_size_tolerance(r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch):
    _set_env(monkeypatch)
    _make_dirs(r2)
    r2.s3.objects["corpus/same.txt"] = b"r" * 50
    _write(r2.dirs["corpus"] / "same.txt", b"l" * 150)  # 100 bytes larger -> skip
    r2.s3.objects["raw/changed.txt"] = b"r" * 50
    _write(r2.dirs["raw"] / "changed.txt", b"l" * 151)  # 101 bytes larger -> transfer

    assert _run(r2, monkeypatch) == 0

    assert [key for key, _ in r2.s3.downloads] == ["raw/changed.txt"]
    assert (r2.dirs["corpus"] / "same.txt").read_bytes() == b"l" * 150
    assert (r2.dirs["raw"] / "changed.txt").read_bytes() == b"r" * 50


def test_upload_skips_within_size_tolerance(r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch):
    _set_env(monkeypatch)
    _make_dirs(r2)
    _write(r2.dirs["corpus"] / "same.txt", b"l" * 150)
    r2.s3.objects["corpus/same.txt"] = b"r" * 50  # 100 bytes smaller -> skip
    _write(r2.dirs["raw"] / "changed.txt", b"l" * 151)
    r2.s3.objects["raw/changed.txt"] = b"r" * 50  # 101 bytes smaller -> upload

    assert _run(r2, monkeypatch, "--upload") == 0

    assert [key for key, _ in r2.s3.uploads] == ["raw/changed.txt"]
    assert r2.s3.objects["corpus/same.txt"] == b"r" * 50
    assert r2.s3.objects["raw/changed.txt"] == b"l" * 151


def test_verify_reports_exact_counters_without_transfers(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _set_env(monkeypatch)
    _make_dirs(r2)
    corpus = r2.dirs["corpus"]
    _write(corpus / "ok.txt", b"ok")
    r2.s3.objects["corpus/ok.txt"] = b"ok"
    r2.s3.objects["corpus/remote_only.txt"] = b"remote"
    _write(corpus / "local_only.txt", b"local")
    _write(corpus / "mismatch.txt", b"m" * 200)
    r2.s3.objects["corpus/mismatch.txt"] = b"m" * 50  # 150 bytes off

    exit_code = _run(r2, monkeypatch, "--verify")

    assert exit_code == 0
    assert r2.s3.downloads == []
    assert r2.s3.uploads == []
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "corpus: ok=1, missing_locally=1, missing_in_r2=1, size_mismatch=1, checksum_mismatch=0",
        "raw: ok=0, missing_locally=0, missing_in_r2=0, size_mismatch=0, checksum_mismatch=0",
        "review: ok=0, missing_locally=0, missing_in_r2=0, size_mismatch=0, checksum_mismatch=0",
        "VERIFY MISMATCH: ok=1, missing_locally=1, missing_in_r2=1, size_mismatch=1, "
        "checksum_mismatch=0",
    ]
    # Verify hashes only size-equal pairs; the size mismatch is not downloaded.
    assert r2.s3.get_object_calls == ["corpus/ok.txt"]


def test_verify_prints_ok_only_when_no_drift_is_found(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _set_env(monkeypatch)
    _make_dirs(r2)
    _write(r2.dirs["corpus"] / "ok.txt", b"ok")
    r2.s3.objects["corpus/ok.txt"] = b"ok"

    assert _run(r2, monkeypatch, "--verify") == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == (
        "VERIFY OK: ok=1, missing_locally=0, missing_in_r2=0, size_mismatch=0, checksum_mismatch=0"
    )


def test_only_raw_lists_only_raw_prefix(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _set_env(monkeypatch)
    r2.s3.objects = {"corpus/c.txt": b"c", "review/r.txt": b"r"}

    exit_code = _run(r2, monkeypatch, "--only", "raw")

    assert exit_code == 0
    assert r2.s3.list_calls == ["raw"]
    assert r2.s3.downloads == []
    assert capsys.readouterr().out.splitlines() == [
        "raw: 0 transferred, 0 up-to-date, 0 remote-missing"
    ]


@pytest.mark.parametrize("flag", ["--upload", "--verify"])
def test_refuses_when_selected_local_dir_is_missing(
    r2: _R2UnderTest,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flag: str,
):
    _set_env(monkeypatch)
    r2.dirs["corpus"].mkdir(parents=True, exist_ok=True)
    r2.dirs["review"].mkdir(parents=True, exist_ok=True)
    assert not r2.dirs["raw"].exists()

    exit_code = _run(r2, monkeypatch, flag)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1
    assert "'raw'" in captured.err
    assert r2.aws.client_calls == []


def test_secrets_never_printed(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _set_env(monkeypatch)
    _make_dirs(r2)
    _write(r2.dirs["raw"] / "f.txt", b"data")

    assert _run(r2, monkeypatch, "--upload") == 0
    captured = capsys.readouterr()
    assert _FAKE_KEY not in captured.out
    assert _FAKE_SECRET not in captured.out
    assert _FAKE_KEY not in captured.err
    assert _FAKE_SECRET not in captured.err

    for name in (*_ENV, "R2_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)

    assert _run(r2, monkeypatch) == 1
    captured = capsys.readouterr()
    assert _FAKE_KEY not in captured.out
    assert _FAKE_SECRET not in captured.out
    assert _FAKE_KEY not in captured.err
    assert _FAKE_SECRET not in captured.err


def test_symlinked_file_is_not_uploaded(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _set_env(monkeypatch)
    _make_dirs(r2)
    _write(r2.dirs["raw"] / "real.txt", b"real")
    outside = _write(tmp_path / "outside.txt", b"outside-data")
    (r2.dirs["raw"] / "link.txt").symlink_to(outside)

    exit_code = _run(r2, monkeypatch, "--upload")

    assert exit_code == 0
    assert [key for key, _ in r2.s3.uploads] == ["raw/real.txt"]
    assert "raw/link.txt" not in r2.s3.objects


def test_download_rejects_keys_that_escape_the_sync_root(
    r2: _R2UnderTest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    _set_env(monkeypatch)
    escape_target = tmp_path / "escaped.env"
    absolute_target = tmp_path / "absolute.env"
    r2.s3.objects = {
        "corpus/ok.txt": b"ok",
        "raw/../escaped.env": b"stolen",
        f"raw//{absolute_target}": b"stolen",
        "raw/nested/": b"",
        "raw/directory/../.env": b"stolen",
    }

    exit_code = _run(r2, monkeypatch)

    assert exit_code == 0
    assert not escape_target.exists()
    assert not absolute_target.exists()
    assert [key for key, _ in r2.s3.downloads] == ["corpus/ok.txt"]
    assert (r2.dirs["corpus"] / "ok.txt").read_bytes() == b"ok"
    captured = capsys.readouterr()
    assert "raw: skipped unsafe remote key: ../escaped.env" in captured.err
    assert "raw: skipped unsafe remote key: nested/" in captured.err
    assert "raw: skipped unsafe remote key: directory/../.env" in captured.err
    assert len(captured.err.splitlines()) == 4
    assert captured.out.splitlines() == [
        "corpus: 1 transferred, 0 up-to-date, 0 remote-missing",
        "raw: 0 transferred, 0 up-to-date, 0 remote-missing",
        "review: 0 transferred, 0 up-to-date, 0 remote-missing",
    ]


def test_unsafe_key_message_is_sanitized(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _set_env(monkeypatch)
    escape_key = "raw/\x1b[31mescape\x1b[0m/../../escaped.env"
    long_key = "raw/" + "a" * 400 + "/../../escaped.env"
    r2.s3.objects = {
        "corpus/ok.txt": b"ok",
        escape_key: b"stolen",
        long_key: b"stolen",
    }

    assert _run(r2, monkeypatch) == 0

    captured = capsys.readouterr()
    assert "\x1b" not in captured.err
    assert "\x07" not in captured.err
    messages = [line for line in captured.err.splitlines() if "skipped unsafe remote key" in line]
    assert len(messages) == 2
    for message in messages:
        assert message.startswith("raw: skipped unsafe remote key: ")
        displayed = message.split(": ", 2)[-1]
        assert len(displayed) <= r2.module._MAX_DISPLAY_KEY_CHARS
        assert displayed.isprintable()
    assert messages[0] == ("raw: skipped unsafe remote key: ?[31mescape?[0m/../../escaped.env")
    assert messages[1].endswith("...")
    assert [key for key, _ in r2.s3.downloads] == ["corpus/ok.txt"]


def test_failed_download_removes_partial_temp_file(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch
):
    _set_env(monkeypatch)
    r2.s3.objects = {"raw/broken.bin": b"payload"}
    r2.s3.fail_download_keys = {"raw/broken.bin"}

    with pytest.raises(OSError, match="synthetic transfer failure"):
        _run(r2, monkeypatch)

    assert _r2part_files(r2) == []
    assert not (r2.dirs["raw"] / "broken.bin").exists()


def test_download_removes_stale_partial_files_from_an_earlier_run(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch
):
    _set_env(monkeypatch)
    _make_dirs(r2)
    stale = _write(r2.dirs["raw"] / "stale.bin.r2part", b"half-written")
    r2.s3.objects["raw/fresh.bin"] = b"fresh"

    assert _run(r2, monkeypatch) == 0

    assert not stale.exists()
    assert _r2part_files(r2) == []
    assert (r2.dirs["raw"] / "fresh.bin").read_bytes() == b"fresh"


def test_r2part_files_are_excluded_from_upload_and_verify(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _set_env(monkeypatch)
    _make_dirs(r2)
    _write(r2.dirs["raw"] / "real.txt", b"real")
    _write(r2.dirs["raw"] / "real.txt.r2part", b"partial-leftover")

    assert _run(r2, monkeypatch, "--upload") == 0

    assert [key for key, _ in r2.s3.uploads] == ["raw/real.txt"]
    assert "raw/real.txt.r2part" not in r2.s3.objects

    capsys.readouterr()
    assert _run(r2, monkeypatch, "--verify") == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == (
        "raw: ok=1, missing_locally=0, missing_in_r2=0, size_mismatch=0, checksum_mismatch=0"
    )


def test_verify_detects_same_size_checksum_drift(
    r2: _R2UnderTest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _set_env(monkeypatch)
    _make_dirs(r2)
    corpus = r2.dirs["corpus"]
    _write(corpus / "match.txt", b"abcd")
    r2.s3.objects["corpus/match.txt"] = b"abcd"
    _write(corpus / "drift.txt", b"abcd")
    r2.s3.objects["corpus/drift.txt"] = b"abce"  # same size, different bytes
    _write(corpus / "tolerated.txt", b"x" * 150)
    r2.s3.objects["corpus/tolerated.txt"] = b"y" * 50  # 100-byte tolerance applies

    assert _run(r2, monkeypatch, "--verify") == 0

    assert r2.s3.downloads == []
    assert r2.s3.uploads == []
    # Only size-equal pairs are hashed; the tolerated pair costs no extra read.
    assert r2.s3.get_object_calls == ["corpus/drift.txt", "corpus/match.txt"]
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "corpus: ok=2, missing_locally=0, missing_in_r2=0, size_mismatch=0, checksum_mismatch=1",
        "raw: ok=0, missing_locally=0, missing_in_r2=0, size_mismatch=0, checksum_mismatch=0",
        "review: ok=0, missing_locally=0, missing_in_r2=0, size_mismatch=0, checksum_mismatch=0",
        "VERIFY MISMATCH: ok=2, missing_locally=0, missing_in_r2=0, size_mismatch=0, "
        "checksum_mismatch=1",
    ]


def test_sha256_remote_closes_body_when_a_read_fails(r2: _R2UnderTest):
    """A failing read must still close the streaming body."""

    class _ExplodingBody:
        def __init__(self) -> None:
            self.close_calls = 0

        def read(self, size: int) -> bytes:
            raise OSError("synthetic read failure")

        def close(self) -> None:
            self.close_calls += 1

    body = _ExplodingBody()

    class _FailingS3:
        def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
            return {"Body": body}

    with pytest.raises(OSError, match="synthetic read failure"):
        r2.module._sha256_remote(_FailingS3(), "fake-bucket", "corpus/key.txt")

    assert body.close_calls == 1


def test_sha256_remote_tolerates_a_body_without_close(r2: _R2UnderTest):
    """Bodies that expose no ``close`` must not break the checksum."""

    class _BareBody:
        def __init__(self) -> None:
            self._chunks = [b"abcd"]

        def read(self, size: int) -> bytes:
            return self._chunks.pop(0) if self._chunks else b""

    class _BareS3:
        def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
            return {"Body": _BareBody()}

    digest = r2.module._sha256_remote(_BareS3(), "fake-bucket", "corpus/key.txt")

    assert digest == hashlib.sha256(b"abcd").hexdigest()
