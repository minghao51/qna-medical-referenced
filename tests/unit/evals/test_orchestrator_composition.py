"""Default-composition contract of run_assessment (P2.4 regression guard).

The boolean kwargs of run_assessment() (run_retrieval_ablations=True, ...)
once shadowed the identically-named imported runners, so the default
composition injected ``False`` into the AssessmentPipeline fn fields and the
ablation stages crashed with TypeError. This pins that every fn field of the
defaultly-composed pipeline is a callable (and the monkeypatch surface —
module attributes resolved at call time — keeps working).
"""

import pytest

from src.evals.assessment import orchestrator as pa
from src.experiments.ablations import (
    run_diversity_sweep,
    run_hype_ablations,
    run_keyword_ablations,
    run_reranking_ablations,
    run_retrieval_ablations,
)


class _StopRun(Exception):
    """Raised by the capturing pipeline to short-circuit run_assessment."""


def test_run_assessment_default_composition_injects_ablation_runners(
    monkeypatch, tmp_path
):
    captured: dict[str, object] = {}

    class CapturingPipeline(pa.AssessmentPipeline):
        def run(self, params):
            captured["pipeline"] = self
            raise _StopRun

    monkeypatch.setattr(pa, "AssessmentPipeline", CapturingPipeline)

    with pytest.raises(_StopRun):
        pa.run_assessment(artifact_dir=tmp_path / "evals")

    pipeline = captured["pipeline"]
    assert pipeline.run_retrieval_ablations_fn is run_retrieval_ablations
    assert pipeline.run_hype_ablations_fn is run_hype_ablations
    assert pipeline.run_keyword_ablations_fn is run_keyword_ablations
    assert pipeline.run_reranking_ablations_fn is run_reranking_ablations
    assert pipeline.run_diversity_sweep_fn is run_diversity_sweep
    assert callable(pipeline.run_hype_ablations_with_reingest_fn)
    assert callable(pipeline.run_keyword_ablations_with_reingest_fn)


def test_run_assessment_composition_prefers_explicit_override(monkeypatch):
    """Explicit *_fn overrides still win over the default runners."""
    sentinel = dict
    captured: dict[str, object] = {}

    class CapturingPipeline(pa.AssessmentPipeline):
        def run(self, params):
            captured["pipeline"] = self
            raise _StopRun

    monkeypatch.setattr(pa, "AssessmentPipeline", CapturingPipeline)

    with pytest.raises(_StopRun):
        pa.run_assessment(
            artifact_dir="unused",
            run_retrieval_ablations=True,
            run_retrieval_ablations_fn=sentinel,
        )

    pipeline = captured["pipeline"]
    assert pipeline.run_retrieval_ablations_fn is sentinel
