"""Regression tests for independent live-provider opt-ins.

``tests/conftest.py`` previously returned early when the Qwen opt-in was set,
which silently disabled the real-API and OpenRouter collection skip gates.
These tests exercise the hook policy for the full 2^3 flag matrix without
importing providers or issuing any network request.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

CONFTEST_PATH = Path(__file__).resolve().parents[1] / "conftest.py"

GATE_ENV = {
    "live_api": "RUN_LIVE_QWEN_TESTS",
    "live_openrouter": "RUN_LIVE_OPENROUTER_TESTS",
    "e2e_real_apis": "ENABLE_REAL_API_TESTS",
}


class _FakeItem:
    """Minimal item surface used by the collection/setup hooks."""

    def __init__(self, markers: set[str], nodeid: str = "tests/unit/test_sample.py::case") -> None:
        self.nodeid = nodeid
        self.keywords = dict.fromkeys(markers, 0)
        self.markers: list[pytest.Mark] = []

    def add_marker(self, marker: pytest.Mark) -> None:
        self.markers.append(marker)

    def skip_reasons(self) -> list[str]:
        return [
            str(marker.kwargs.get("reason", "")) for marker in self.markers if marker.name == "skip"
        ]


def _load_conftest(
    monkeypatch: pytest.MonkeyPatch,
    enabled: set[str],
) -> object:
    """Import a fresh conftest instance with the given opt-ins enabled."""
    for marker, env_var in GATE_ENV.items():
        monkeypatch.setenv(env_var, "1" if marker in enabled else "0")

    name = "conftest_gates_" + "_".join(sorted(enabled)) if enabled else "conftest_gates_none"
    spec = importlib.util.spec_from_file_location(name, CONFTEST_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MATRIX = [
    (live_api, live_openrouter, e2e_real_apis)
    for live_api in (False, True)
    for live_openrouter in (False, True)
    for e2e_real_apis in (False, True)
]


@pytest.mark.parametrize(("live_api", "live_openrouter", "e2e_real_apis"), MATRIX)
def test_each_requirement_is_gated_independently(
    monkeypatch: pytest.MonkeyPatch,
    live_api: bool,
    live_openrouter: bool,
    e2e_real_apis: bool,
) -> None:
    enabled = {
        marker
        for marker, is_enabled in (
            ("live_api", live_api),
            ("live_openrouter", live_openrouter),
            ("e2e_real_apis", e2e_real_apis),
        )
        if is_enabled
    }
    module = _load_conftest(monkeypatch, enabled)

    items = {marker: _FakeItem({marker}) for marker in GATE_ENV}
    module.pytest_collection_modifyitems(None, list(items.values()))  # type: ignore[attr-defined]

    for marker, env_var in GATE_ENV.items():
        reasons = items[marker].skip_reasons()
        if marker in enabled:
            assert reasons == [], f"{marker} must not be skipped when {env_var}=1"
        else:
            assert len(reasons) == 1, f"{marker} must be skipped on its own gate"
            assert env_var in reasons[0]
            assert f"{env_var}=1" in reasons[0]


def test_item_needing_several_opt_ins_keeps_every_missing_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_conftest(monkeypatch, {"e2e_real_apis"})
    item = _FakeItem({"live_api", "live_openrouter", "e2e_real_apis"})

    module.pytest_collection_modifyitems(None, [item])  # type: ignore[attr-defined]

    reasons = item.skip_reasons()
    assert len(reasons) == 2
    assert any("RUN_LIVE_QWEN_TESTS" in reason for reason in reasons)
    assert any("RUN_LIVE_OPENROUTER_TESTS" in reason for reason in reasons)
    assert not any("ENABLE_REAL_API_TESTS" in reason for reason in reasons)


def test_setup_precheck_runs_only_for_enabled_requirements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_conftest(monkeypatch, {"live_api"})
    calls: list[str] = []
    monkeypatch.setattr(module, "_ensure_live_qwen_available", lambda: calls.append("qwen"))
    monkeypatch.setattr(
        module, "_ensure_live_openrouter_available", lambda: calls.append("openrouter")
    )
    item = _FakeItem({"live_api", "live_openrouter"})

    module.pytest_runtest_setup(item)  # type: ignore[attr-defined]

    assert calls == ["qwen"]
