"""Offline allowlist tests for the Qwen judge/embedder endpoint guard."""

import pytest

from src.config import settings
from src.evals.deepeval_models import _safe_qwen_endpoint

# Owner-approved canonical workspace-scoped Alibaba MaaS endpoint (not a secret).
_WORKSPACE_HOST = "llm-zz1xabubqkfxuo5m.ap-southeast-1.maas.aliyuncs.com"
_WORKSPACE_BASE = f"https://{_WORKSPACE_HOST}"


def _endpoint_for(monkeypatch: pytest.MonkeyPatch, base_url: str) -> str:
    monkeypatch.setattr(settings.llm, "qwen_base_url", base_url)
    return _safe_qwen_endpoint()


def test_accepts_canonical_workspace_maas_endpoint(monkeypatch: pytest.MonkeyPatch):
    assert _endpoint_for(monkeypatch, f"{_WORKSPACE_BASE}/compatible-mode/v1") == (
        f"https://{_WORKSPACE_HOST}/compatible-mode/v1"
    )


def test_accepts_workspace_maas_endpoint_with_trailing_slash(monkeypatch: pytest.MonkeyPatch):
    assert _endpoint_for(monkeypatch, f"{_WORKSPACE_BASE}/compatible-mode/v1/") == (
        f"https://{_WORKSPACE_HOST}/compatible-mode/v1"
    )


@pytest.mark.parametrize("host", ["dashscope-us.aliyuncs.com", "dashscope-intl.aliyuncs.com"])
def test_accepts_legacy_dashscope_hosts(monkeypatch: pytest.MonkeyPatch, host: str):
    assert _endpoint_for(monkeypatch, f"https://{host}/compatible-mode/v1") == (
        f"https://{host}/compatible-mode/v1"
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://maas.aliyuncs.com/compatible-mode/v1",
        "https://.maas.aliyuncs.com/compatible-mode/v1",
        "http://llm-zz1xabubqkfxuo5m.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
        f"https://user:pass@{_WORKSPACE_HOST}/compatible-mode/v1",
        f"https://{_WORKSPACE_HOST}:8443/compatible-mode/v1",
        f"https://{_WORKSPACE_HOST}/compatible-mode/v1?token=x",
        f"https://{_WORKSPACE_HOST}/compatible-mode/v1#fragment",
        f"https://{_WORKSPACE_HOST}/compatible-mode/v2",
        "https://llm.example.com/compatible-mode/v1",
    ],
)
def test_rejects_disallowed_endpoints(monkeypatch: pytest.MonkeyPatch, base_url: str):
    monkeypatch.setattr(settings.llm, "qwen_base_url", base_url)
    with pytest.raises(ValueError, match="not a supported DashScope route"):
        _safe_qwen_endpoint()
