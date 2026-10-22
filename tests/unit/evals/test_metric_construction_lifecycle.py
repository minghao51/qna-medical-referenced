"""Judge ownership includes partial construction and independently cancelled metrics."""

import asyncio
from types import SimpleNamespace

import pytest

from src.evals.assessment import answer_eval
from src.evals.metrics import medical


def _case():
    return answer_eval.AnswerQualityCase(
        query_id="synthetic",
        query="synthetic question",
        context="synthetic context",
        sources=[],
        trace={},
        answer="synthetic answer",
        timings={},
        cache={},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_first", [True, False])
async def test_partial_default_metric_construction_closes_every_registered_judge(
    monkeypatch, fail_first
):
    models, closed = [], []

    class Judge:
        async def aclose(self):
            closed.append((self, asyncio.get_running_loop()))

    def new_model():
        model = Judge()
        models.append(model)
        return model

    def fail(*, model):
        raise ValueError("synthetic metric construction failure")

    good = medical.MetricSpec("one", "one", "heavy", lambda *, model: SimpleNamespace(model=model))
    bad = medical.MetricSpec("two", "two", "heavy", fail)
    specs = (bad,) if fail_first else (good, bad)
    monkeypatch.setattr(medical, "METRIC_SPECS", specs)
    monkeypatch.setattr(medical, "get_heavy_model", new_model)
    with pytest.raises(ValueError, match="synthetic metric construction failure"):
        await answer_eval._evaluate_case_metrics(
            _case(),
            metric_specs=list(specs),
            metric_builder=medical.create_medical_metrics,
            runtime_signature={},
            metric_cache={},
            metric_cache_enabled=False,
            metric_concurrency=2,
            close_factory_owned_judges=True,
        )
    assert len(models) == (1 if fail_first else 2)
    assert closed == [(model, asyncio.get_running_loop()) for model in models]


@pytest.mark.asyncio
async def test_independent_metric_cancellation_drains_sibling_before_closing_judges():
    entered, release, sibling_done = asyncio.Event(), asyncio.Event(), asyncio.Event()
    closed = []

    class Judge:
        async def aclose(self):
            assert sibling_done.is_set()
            closed.append(self)

    class Metric:
        score = 1.0
        reason = None
        error = None

        def __init__(self, cancelled):
            self.model = Judge()
            self.cancelled = cancelled

        async def a_measure(self, *args, **kwargs):
            if self.cancelled:
                await entered.wait()
                raise asyncio.CancelledError
            entered.set()
            await release.wait()
            sibling_done.set()
            return 1.0

    metrics = [Metric(True), Metric(False)]
    task = asyncio.create_task(
        answer_eval._evaluate_case_metrics(
            _case(),
            metric_specs=[SimpleNamespace(key="one"), SimpleNamespace(key="two")],
            metric_builder=lambda: metrics,
            runtime_signature={},
            metric_cache={},
            metric_cache_enabled=False,
            metric_concurrency=2,
            close_factory_owned_judges=True,
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 2)
        for _ in range(4):
            await asyncio.sleep(0)
        assert not task.done()
        assert closed == []
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert closed == [metric.model for metric in metrics]
