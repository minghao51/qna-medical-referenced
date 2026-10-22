"""No request-time model downloads or raw loader-error logging."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.rag.reranker import CrossEncoderReranker


def test_loader_requires_local_assets_and_reuses_the_loaded_model(monkeypatch):
    # Public API verified against the locked sentence-transformers 5.3.0 source.
    # This fake is not evidence that optional weights/runtime are installed.
    construct = Mock(return_value=SimpleNamespace(predict=lambda pairs: [0.75] * len(pairs)))
    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(CrossEncoder=construct)
    )
    reranker = CrossEncoderReranker()
    result = reranker.rerank("synthetic query", [{"content": "synthetic evidence"}], top_k=1)
    reranker.rerank("another query", [{"content": "synthetic evidence"}], top_k=1)
    construct.assert_called_once_with(
        "BAAI/bge-reranker-base",
        device="cpu",
        local_files_only=True,
        trust_remote_code=False,
    )
    assert result.reranked_results[0]["rerank_score"] == 0.75


def test_missing_assets_fail_without_disabling_reranking_or_logging_sdk_details(
    monkeypatch, caplog
):
    construct = Mock(side_effect=OSError("synthetic-secret-canary"))
    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(CrossEncoder=construct)
    )
    reranker = CrossEncoderReranker()
    with pytest.raises(RuntimeError, match="Request-time downloads are disabled"):
        reranker.rerank("synthetic query", [{"content": "synthetic evidence"}], top_k=1)
    assert reranker._model is None
    assert "synthetic-secret-canary" not in caplog.text
    assert construct.call_args.kwargs["local_files_only"] is True
