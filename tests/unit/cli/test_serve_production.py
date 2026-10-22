import sys

import pytest

from src.cli import serve_production


@pytest.mark.parametrize("workers", [0, 2, -1])
def test_production_cli_rejects_unsupported_worker_counts_before_uvicorn(monkeypatch, workers):
    calls = []
    monkeypatch.setattr(serve_production.settings.app, "environment", "production")
    monkeypatch.setattr(serve_production.uvicorn, "run", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(sys, "argv", ["serve_production", "--workers", str(workers)])

    with pytest.raises(SystemExit) as error:
        serve_production.main()

    assert error.value.code == 2
    assert calls == []


def test_production_cli_keeps_single_worker_and_bind_defaults(monkeypatch):
    calls = []
    monkeypatch.setattr(serve_production.settings.app, "environment", "production")
    monkeypatch.setattr(
        serve_production.uvicorn,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(sys, "argv", ["serve_production"])

    serve_production.main()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("src.app.factory:app",)
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8000
    assert kwargs["workers"] == 1
    assert kwargs["access_log"] is False


def test_production_cli_rejects_development_mode_before_uvicorn(monkeypatch):
    calls = []
    monkeypatch.setattr(serve_production.settings.app, "environment", "development")
    monkeypatch.setattr(serve_production.uvicorn, "run", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(sys, "argv", ["serve_production"])

    with pytest.raises(SystemExit) as error:
        serve_production.main()

    assert error.value.code == 2
    assert calls == []
