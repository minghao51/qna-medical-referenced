"""Metric lookup must not depend on optional inferential-statistics packages."""

import builtins
import importlib

import pytest

from src.experiments import metric_utils


def test_lookup_works_without_numpy_or_scipy(monkeypatch):
    original_import = builtins.__import__

    def deny_statistics(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"numpy", "scipy"}:
            raise ModuleNotFoundError("synthetically unavailable statistical dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny_statistics)
    importlib.reload(metric_utils)
    assert metric_utils.resolve_metric_key({"ndcg_at_k": 0.5}, "ndcg@5") == 0.5
    with pytest.raises(RuntimeError, match="provisioned SciPy"):
        metric_utils.wilcoxon_test([0.0, 1.0], [1.0, 1.0])
    with pytest.raises(RuntimeError, match="provisioned NumPy"):
        metric_utils.bootstrap_ci([0.0, 1.0])
