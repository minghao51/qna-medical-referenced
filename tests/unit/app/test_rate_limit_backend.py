"""SQLite rate limit backend initialises lazily, exactly once, and thread-safely."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.app.middleware import rate_limit


@pytest.fixture
def backend_db(monkeypatch, tmp_path):
    """Isolate the module-level database path and return it with a fresh backend."""
    db_path = tmp_path / "rate_limits.db"
    monkeypatch.setattr(rate_limit, "RATE_LIMIT_DB", str(db_path))
    return db_path, rate_limit.SQLiteRateLimitBackend(window_seconds=60)


def test_construction_does_not_create_database(backend_db):
    db_path, _backend = backend_db

    assert not db_path.exists()


def test_first_check_creates_database_and_enforces_limit(backend_db):
    db_path, backend = backend_db

    first = backend.check("client", limit=2, now=1_000)
    assert db_path.exists()
    assert (first.allowed, first.remaining, first.retry_after) == (True, 1, 0)

    second = backend.check("client", limit=2, now=1_001)
    assert (second.allowed, second.remaining) == (True, 0)

    third = backend.check("client", limit=2, now=1_002)
    assert third.allowed is False
    assert third.remaining == 0
    assert third.retry_after >= 1


def test_repeated_checks_run_schema_setup_once(backend_db, monkeypatch):
    _db_path, backend = backend_db
    init_calls = []
    original_init_db = backend._init_db

    def counting_init_db():
        init_calls.append(1)
        original_init_db()

    monkeypatch.setattr(backend, "_init_db", counting_init_db)

    assert backend.check("client", limit=5, now=1_000).allowed is True
    assert backend.check("client", limit=5, now=1_001).allowed is True
    assert backend.check("other", limit=5, now=1_002).allowed is True

    assert len(init_calls) == 1


def test_initialisation_is_thread_safe(backend_db, monkeypatch):
    _db_path, backend = backend_db
    init_calls = []

    def slow_counting_init_db():
        init_calls.append(1)
        time.sleep(0.05)

    monkeypatch.setattr(backend, "_init_db", slow_counting_init_db)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: backend._ensure_initialized(), range(8)))

    assert len(init_calls) == 1
