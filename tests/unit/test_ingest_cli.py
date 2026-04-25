import sys

from src.cli import ingest


def test_main_uses_non_parallel_pipeline_by_default(monkeypatch):
    calls: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        ingest,
        "run_pipeline",
        lambda **kwargs: calls.append(("run_pipeline", kwargs)),
    )
    monkeypatch.setattr(
        ingest,
        "run_hamilton_pipeline",
        lambda **kwargs: calls.append(("run_hamilton_pipeline", kwargs)),
    )
    monkeypatch.setattr(sys, "argv", ["ingest", "--skip-download", "--force-html"])

    ingest.main()

    assert calls == [
        (
            "run_pipeline",
            {
                "skip_download": True,
                "force_rebuild": False,
                "force_html_convert": True,
                "enable_hype": False,
                "enable_keyword_extraction": False,
                "enable_chunk_summaries": False,
                "parallel_cores": 1,
            },
        )
    ]


def test_main_uses_hamilton_pipeline_for_parallel_runs(monkeypatch):
    calls: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        ingest,
        "run_pipeline",
        lambda **kwargs: calls.append(("run_pipeline", kwargs)),
    )
    monkeypatch.setattr(
        ingest,
        "run_hamilton_pipeline",
        lambda **kwargs: calls.append(("run_hamilton_pipeline", kwargs)),
    )
    monkeypatch.setattr(sys, "argv", ["ingest", "--parallel", "2"])

    ingest.main()

    assert calls == [
        (
            "run_hamilton_pipeline",
            {
                "skip_download": False,
                "force_rebuild": False,
                "enable_hype": False,
                "enable_keyword_extraction": False,
                "enable_chunk_summaries": False,
                "parallel_cores": 2,
            },
        )
    ]
