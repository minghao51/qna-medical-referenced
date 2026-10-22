import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC
from datetime import datetime as DateTime
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Any

import pytest

from src.evals import artifacts
from src.evals.artifacts import (
    ArtifactStore,
    atomic_write_text,
    update_run_index,
    write_latest_pointer,
)


def _temporary_files(path: Path) -> list[Path]:
    return list(path.parent.glob(f".{path.name}.*.tmp"))


def test_json_serialization_failure_preserves_existing_artifact(tmp_path: Path):
    store = ArtifactStore(tmp_path, "serialization")
    target = store.path("result.json")
    target.write_text("previous", encoding="utf-8")

    with pytest.raises(ValueError):
        store.write_json("result.json", {"score": float("nan")})

    assert target.read_text(encoding="utf-8") == "previous"
    assert _temporary_files(target) == []


def test_jsonl_serialization_failure_preserves_existing_artifact(tmp_path: Path):
    store = ArtifactStore(tmp_path, "serialization")
    target = store.path("results.jsonl")
    target.write_text("previous\n", encoding="utf-8")

    with pytest.raises(ValueError):
        store.write_jsonl("results.jsonl", [{"score": 1.0}, {"score": float("inf")}])

    assert target.read_text(encoding="utf-8") == "previous\n"
    assert _temporary_files(target) == []


def test_atomic_write_text_failure_preserves_target_and_cleans_temp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    target = tmp_path / "artifact.txt"
    target.write_text("previous", encoding="utf-8")
    original_write_text = Path.write_text

    def fail_temporary_write(path: Path, content: str, **kwargs: Any) -> int:
        if path.name.startswith(f".{target.name}."):
            raise OSError("injected write failure")
        return original_write_text(path, content, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_temporary_write)

    with pytest.raises(OSError, match="injected write failure"):
        atomic_write_text(target, "replacement")

    assert target.read_text(encoding="utf-8") == "previous"
    assert _temporary_files(target) == []


def test_atomic_write_text_replace_failure_preserves_target_and_cleans_temp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    target = tmp_path / "artifact.txt"
    target.write_text("previous", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        assert source.exists()
        assert destination == target
        raise OSError("injected replace failure")

    monkeypatch.setattr(artifacts.os, "replace", fail_replace)

    with pytest.raises(OSError, match="injected replace failure"):
        atomic_write_text(target, "replacement")

    assert target.read_text(encoding="utf-8") == "previous"
    assert _temporary_files(target) == []


def test_atomic_write_text_publishes_only_after_temp_is_complete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    target = tmp_path / "artifact.txt"
    target.write_text("previous", encoding="utf-8")
    content = "complete replacement"
    original_replace = artifacts.os.replace
    observations: list[tuple[str, str]] = []

    def inspect_then_replace(source: Path, destination: Path) -> None:
        assert destination == target
        observations.append(
            (destination.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))
        )
        original_replace(source, destination)

    monkeypatch.setattr(artifacts.os, "replace", inspect_then_replace)

    result = atomic_write_text(target, content)

    assert result == target
    assert observations == [("previous", content)]
    assert target.read_text(encoding="utf-8") == content
    assert _temporary_files(target) == []


def test_concurrent_json_writers_never_expose_partial_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    store = ArtifactStore(tmp_path, "concurrent")
    target = store.path("shared.json")
    target.write_text(json.dumps({"writer": "initial", "values": []}), encoding="utf-8")

    writers_ready = threading.Barrier(2)
    replacement_lock = threading.Lock()
    replaced: Queue[None] = Queue()
    allow_next_replace: Queue[None] = Queue()
    original_replace = artifacts.os.replace
    payloads = {name: {"writer": name, "values": [name] * 256} for name in ("first", "second")}

    def synchronized_replace(source: Path, destination: Path) -> None:
        assert destination == target
        staged = json.loads(source.read_text(encoding="utf-8"))
        assert staged in payloads.values()
        writers_ready.wait(timeout=5)
        with replacement_lock:
            original_replace(source, destination)
            replaced.put(None)
            assert allow_next_replace.get(timeout=5) is None

    monkeypatch.setattr(artifacts.os, "replace", synchronized_replace)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(store.write_json, "shared.json", payload)
            for payload in payloads.values()
        ]
        for _ in payloads:
            assert replaced.get(timeout=5) is None
            visible = json.loads(target.read_text(encoding="utf-8"))
            assert visible["writer"] in {"initial", *payloads}
            if visible["writer"] != "initial":
                assert visible == payloads[visible["writer"]]
            allow_next_replace.put(None)
        for future in futures:
            assert future.result(timeout=5) == target

    assert json.loads(target.read_text(encoding="utf-8")) in payloads.values()
    assert _temporary_files(target) == []


def test_same_timestamp_and_name_stores_get_unique_attempt_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    class FrozenDateTime:
        @staticmethod
        def now(tz: object) -> DateTime:
            return DateTime(2026, 3, 19, tzinfo=UTC)

    identifiers = iter(("attempt-one", "attempt-two"))
    monkeypatch.setattr(artifacts, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        artifacts.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex=next(identifiers)),
    )

    first = ArtifactStore(tmp_path, "same name")
    second = ArtifactStore(tmp_path, "same name")

    assert first.run_dir != second.run_dir
    assert first.execution_id == "attempt-one"
    assert second.execution_id == "attempt-two"
    assert first.run_dir.name.startswith("20260319T000000.000000Z_same-name_")
    assert second.run_dir.name.startswith("20260319T000000.000000Z_same-name_")


def test_store_retries_existing_attempt_suffix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    class FrozenDateTime:
        @staticmethod
        def now(tz: object) -> DateTime:
            return DateTime(2026, 3, 19, tzinfo=UTC)

    base_dir = tmp_path / "runs"
    base_dir.mkdir()
    occupied = base_dir / "20260319T000000.000000Z_demo_existing"
    occupied.mkdir()
    identifiers = iter(("existing", "fresh"))
    monkeypatch.setattr(artifacts, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        artifacts.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex=next(identifiers)),
    )

    store = ArtifactStore(base_dir, "demo")

    assert store.execution_id == "fresh"
    assert store.run_dir == base_dir / "20260319T000000.000000Z_demo_fresh"
    assert occupied.is_dir()


def test_run_index_and_latest_pointer_use_atomic_writer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    base_dir = tmp_path / "runs"
    run_dir = base_dir / "attempt"
    run_dir.mkdir(parents=True)
    calls: list[tuple[Path, str]] = []
    original_atomic_write_text = artifacts.atomic_write_text

    def record_atomic_write(path: Path, content: str) -> Path:
        calls.append((path, content))
        return original_atomic_write_text(path, content)

    monkeypatch.setattr(artifacts, "atomic_write_text", record_atomic_write)

    index_path = update_run_index(
        base_dir, run_identity="fingerprint", run_dir=run_dir, status="completed"
    )
    pointer_path = write_latest_pointer(base_dir, run_dir)

    assert index_path == base_dir / "run_index.json"
    assert pointer_path == base_dir / "latest_run.txt"
    assert [path for path, _ in calls] == [index_path, pointer_path]
    assert json.loads(calls[0][1]) == {
        "entries": {"fingerprint": {"run_dir": str(run_dir), "status": "completed"}}
    }
    assert calls[1][1] == str(run_dir)
    assert json.loads(index_path.read_text(encoding="utf-8"))["entries"]["fingerprint"]
    assert pointer_path.read_text(encoding="utf-8") == str(run_dir)


def test_independent_process_writers_publish_whole_snapshots(tmp_path):
    # Fresh interpreters avoid forking an already multithreaded test process.
    # Install child isolation before importing the artifact-only module.
    script = """
import json
import sys
from pathlib import Path
repo = Path.cwd().resolve()
def deny_unsafe_io(event, args):
    if event in {
        'socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname',
        'socket.gethostbyaddr', 'socket.sendto',
    }:
        raise RuntimeError('Network denied by atomic publication test')
    if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
        if Path(args[0]).resolve().is_relative_to(repo):
            raise RuntimeError('Repository SQLite denied by atomic publication test')
sys.addaudithook(deny_unsafe_io)
from src.evals.artifacts import atomic_write_text
target, name = Path(sys.argv[1]), sys.argv[2]
for iteration in range(50):
    content = json.dumps({'writer': name, 'iteration': iteration, 'data': [name] * 500})
    atomic_write_text(target, content)
"""
    target = tmp_path / "shared.json"
    target.write_text(json.dumps({"writer": "initial", "iteration": 0, "data": []}))
    workers = []
    try:
        for name in ("first", "second"):
            workers.append(
                subprocess.Popen(
                    [sys.executable, "-c", script, str(target), name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        deadline = time.monotonic() + 10
        while any(worker.poll() is None for worker in workers):
            payload = json.loads(target.read_text())
            assert payload["writer"] in {"initial", "first", "second"}
            if payload["writer"] != "initial":
                assert payload["data"] == [payload["writer"]] * 500
            assert time.monotonic() < deadline
        for worker in workers:
            _, stderr = worker.communicate(timeout=5)
            assert worker.returncode == 0, stderr
        payload = json.loads(target.read_text())
        assert payload["writer"] in {"first", "second"}
        assert payload["data"] == [payload["writer"]] * 500
        assert _temporary_files(target) == []
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.terminate()
            worker.communicate(timeout=5)
