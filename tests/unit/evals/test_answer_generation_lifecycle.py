"""One generation client per evaluation, closed on its owning loop."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.evals.assessment import answer_eval
from src.evals.metrics import medical


@pytest.fixture
def evaluation_leaves(monkeypatch):
    import src.infra.llm as llm
    import src.rag.runtime as runtime

    class Client:
        model = "synthetic-model"

        def __init__(self):
            self.outcome = "success"
            self.close_failure = False
            self.calls = 0
            self.closed = []
            self.close_entered = asyncio.Event()
            self.close_release = None

        async def a_generate(self, **kwargs):
            self.calls += 1
            if self.outcome == "failure":
                raise RuntimeError("synthetic generation failure")
            if self.outcome == "cancellation":
                raise asyncio.CancelledError
            return "synthetic answer"

        async def aclose(self):
            self.closed.append(asyncio.get_running_loop())
            self.close_entered.set()
            if self.close_release is not None:
                await self.close_release.wait()
            if self.close_failure:
                raise RuntimeError("synthetic-cleanup-secret-canary")

    class Metric:
        score = 1.0
        reason = None
        error = None

        async def a_measure(self, *args, **kwargs):
            return self.score

    client = Client()
    factory = Mock(return_value=client)
    monkeypatch.setattr(llm, "get_client", factory)
    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda *args, **kwargs: ("synthetic evidence", [], {}),
    )
    monkeypatch.setattr(
        medical, "create_medical_metrics", lambda: [Metric() for _ in medical.METRIC_SPECS]
    )
    return SimpleNamespace(client=client, factory=factory)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "close_failure"),
    [("success", False), ("failure", False), ("cancellation", False), ("cancellation", True)],
)
async def test_shared_generation_client_cleanup_preserves_primary(
    evaluation_leaves, tmp_path, outcome, close_failure
):
    leaves = evaluation_leaves
    leaves.client.outcome = outcome
    leaves.client.close_failure = close_failure
    cases = [{"query_id": str(i), "query": "synthetic question"} for i in range(2)]
    if outcome == "cancellation":
        with pytest.raises(asyncio.CancelledError) as raised:
            await answer_eval.evaluate_answer_quality_async(cases, 2, cache_dir=tmp_path)
        assert "synthetic-cleanup-secret-canary" not in repr(getattr(raised.value, "__notes__", []))
    else:
        rows, aggregate = await answer_eval.evaluate_answer_quality_async(
            cases, 2, cache_dir=tmp_path
        )
        assert len(rows) == 2
        assert aggregate["query_count"] == 2
        assert aggregate["status"] == ("ok" if outcome == "success" else "degraded")
    leaves.factory.assert_called_once_with()
    assert leaves.client.calls == 2
    assert leaves.client.closed == [asyncio.get_running_loop()]


@pytest.mark.asyncio
async def test_repeated_cancellation_drains_entered_client_cleanup(evaluation_leaves, tmp_path):
    leaves = evaluation_leaves
    leaves.client.close_release = asyncio.Event()
    task = asyncio.create_task(
        answer_eval.evaluate_answer_quality_async(
            [{"query_id": "one", "query": "synthetic question"}],
            2,
            cache_dir=tmp_path,
        )
    )
    try:
        await asyncio.wait_for(leaves.client.close_entered.wait(), 2)
        for _ in range(2):
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
        leaves.client.close_release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
    finally:
        leaves.client.close_release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert leaves.client.closed == [asyncio.get_running_loop()]
