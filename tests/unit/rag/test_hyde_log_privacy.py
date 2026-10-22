"""HyDE success/failure logs exclude query, generated content, and exception details."""

import asyncio
import logging

import pytest

import src.rag.query_expansion as query_expansion
from src.rag.hyde import expand_query_with_hyde_async, generate_hypothetical_answer

QUERY_CANARY = "synthetic-patient-query-secret-canary"
ANSWER_CANARY = "synthetic generated answer canary"
EXCEPTION_CANARY = "synthetic-sdk-exception-secret-canary"


class StubLLMClient:
    def __init__(self, *, answer: str = ANSWER_CANARY, error: Exception | None = None):
        self._answer = answer
        self._error = error

    async def a_generate(self, prompt: str, context: str) -> str:
        if self._error is not None:
            raise self._error
        return self._answer


def _assert_no_canaries_or_exc_info(caplog: pytest.LogCaptureFixture) -> None:
    for record in caplog.records:
        assert record.exc_info is None
        for canary in (QUERY_CANARY, ANSWER_CANARY, EXCEPTION_CANARY):
            assert canary not in record.getMessage()


@pytest.mark.asyncio
async def test_hyde_success_log_reports_only_word_count(caplog):
    with caplog.at_level(logging.DEBUG):
        result = await generate_hypothetical_answer(QUERY_CANARY, StubLLMClient())
    assert result == ANSWER_CANARY
    assert f"Generated hypothetical answer ({len(ANSWER_CANARY.split())} words)" in caplog.text
    _assert_no_canaries_or_exc_info(caplog)


@pytest.mark.asyncio
async def test_hyde_failure_log_omits_query_and_exception_details(caplog):
    client = StubLLMClient(error=RuntimeError(EXCEPTION_CANARY))
    with caplog.at_level(logging.DEBUG):
        result = await generate_hypothetical_answer(QUERY_CANARY, client)
    assert result == ""
    assert "Hypothetical answer generation failed" in caplog.text
    _assert_no_canaries_or_exc_info(caplog)


@pytest.mark.asyncio
async def test_hyde_async_expansion_success_returns_both_variants_without_leaking(caplog):
    with caplog.at_level(logging.DEBUG):
        result = await expand_query_with_hyde_async(QUERY_CANARY, StubLLMClient(), enable_hyde=True)
    assert result == [QUERY_CANARY, ANSWER_CANARY]
    assert "HyDE generation failed" not in caplog.text
    _assert_no_canaries_or_exc_info(caplog)


@pytest.mark.asyncio
async def test_hyde_async_expansion_failure_falls_back_to_original_query(caplog):
    client = StubLLMClient(error=RuntimeError(EXCEPTION_CANARY))
    with caplog.at_level(logging.DEBUG):
        result = await expand_query_with_hyde_async(QUERY_CANARY, client, enable_hyde=True)
    assert result == [QUERY_CANARY]
    assert "HyDE generation failed, using original query only" in caplog.text
    _assert_no_canaries_or_exc_info(caplog)


@pytest.mark.asyncio
async def test_query_expansion_success_log_reports_only_variant_count(caplog):
    with caplog.at_level(logging.DEBUG):
        result = await query_expansion.expand_queries_async(
            QUERY_CANARY,
            hyde_client=StubLLMClient(),
            enable_hyde=True,
            pre_expanded_queries=[QUERY_CANARY],
        )
    assert result == [QUERY_CANARY, ANSWER_CANARY]
    assert "HyDE expanded query to 2 variants" in caplog.text
    _assert_no_canaries_or_exc_info(caplog)


@pytest.mark.asyncio
async def test_query_expansion_failure_falls_back_without_logging_query_or_exception(
    caplog, monkeypatch
):
    async def raise_hyde_failure(*args, **kwargs):
        raise RuntimeError(EXCEPTION_CANARY)

    monkeypatch.setattr(query_expansion, "expand_query_with_hyde_async", raise_hyde_failure)
    with caplog.at_level(logging.DEBUG):
        result = await query_expansion.expand_queries_async(
            QUERY_CANARY,
            hyde_client=StubLLMClient(),
            enable_hyde=True,
            pre_expanded_queries=[QUERY_CANARY],
        )
    assert result == [QUERY_CANARY]
    assert "HyDE expansion failed, falling back to base expansion" in caplog.text
    _assert_no_canaries_or_exc_info(caplog)


@pytest.mark.asyncio
async def test_hyde_cancellation_propagates_without_error_logging(caplog):
    client = StubLLMClient(error=asyncio.CancelledError())
    with caplog.at_level(logging.DEBUG), pytest.raises(asyncio.CancelledError):
        await generate_hypothetical_answer(QUERY_CANARY, client)
    assert "Hypothetical answer generation failed" not in caplog.text
    _assert_no_canaries_or_exc_info(caplog)
