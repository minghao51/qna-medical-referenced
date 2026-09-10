import sys

from src.cli import ingest


def test_main_uses_pipeline_by_default(monkeypatch):
    calls: list[dict] = []

    monkeypatch.setattr(
        ingest,
        "run_pipeline",
        lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(sys, "argv", ["ingest", "--skip-download", "--force-html"])

    ingest.main()

    assert calls == [
        {
            "skip_download": True,
            "force_rebuild": False,
            "force_html_convert": True,
            "enable_hype": False,
            "enable_keyword_extraction": False,
            "enable_chunk_summaries": False,
            "parallel_cores": 1,
        }
    ]


def test_main_uses_same_pipeline_for_parallel_runs(monkeypatch):
    calls: list[dict] = []

    monkeypatch.setattr(
        ingest,
        "run_pipeline",
        lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(sys, "argv", ["ingest", "--parallel", "2", "--force", "--enable-hype"])

    ingest.main()

    assert calls == [
        {
            "skip_download": False,
            "force_rebuild": True,
            "force_html_convert": False,
            "enable_hype": True,
            "enable_keyword_extraction": False,
            "enable_chunk_summaries": False,
            "parallel_cores": 2,
        }
    ]
