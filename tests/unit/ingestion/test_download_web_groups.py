"""Regression tests for the download_web group order (the moh group must not be skipped)."""

import asyncio
from pathlib import Path

import pytest
import yaml

from src.ingestion.steps import download_web as dw

_SOURCES_YAML = Path(__file__).resolve().parents[3] / "config" / "sources.yaml"


def _configured_web_groups() -> list[str]:
    config = yaml.safe_load(_SOURCES_YAML.read_text(encoding="utf-8"))
    return list(config["web_sources"].keys())


def test_download_groups_match_configured_web_sources():
    groups = dw.DOWNLOAD_GROUPS
    configured = _configured_web_groups()
    assert len(groups) == len(set(groups)), "DOWNLOAD_GROUPS must not repeat a group"
    assert len(groups) == len(configured)
    assert set(groups) == set(configured)


def test_download_groups_include_moh_between_healthhub_and_hpp():
    groups = dw.DOWNLOAD_GROUPS
    assert "moh" in groups
    assert groups.index("healthhub") < groups.index("moh") < groups.index("hpp_guidelines")


def test_main_iterates_every_configured_group(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, int]] = []

    async def record_download_group(group: str, *, timeout: int = 30) -> list[str]:
        calls.append((group, timeout))
        return []

    monkeypatch.setattr(dw, "download_group", record_download_group)

    asyncio.run(dw.main())

    assert [group for group, _ in calls] == list(dw.DOWNLOAD_GROUPS)
    assert "moh" in [group for group, _ in calls]
    timeouts = dict(calls)
    assert timeouts["international_guidelines"] == 60
    assert {timeout for group, timeout in calls if group != "international_guidelines"} == {30}
    assert set(dw._GROUP_LOG_LABELS) == set(dw.DOWNLOAD_GROUPS)
    assert dw._GROUP_TIMEOUTS.get("international_guidelines") == 60
