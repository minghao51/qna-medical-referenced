from pathlib import Path
from types import SimpleNamespace

import pytest

from src.experiments.addition_config import (
    ExperimentConfig,
    ExperimentMetrics,
    ExperimentVariant,
)
from src.experiments.feature_ablation_runner import run_feature_family, select_best_variant
from src.experiments.feature_addition_runner import (
    ExperimentSummary,
    VariantResult,
    run_variant,
)


def _addition_config() -> ExperimentConfig:
    return ExperimentConfig(
        name="synthetic",
        baseline=ExperimentVariant(name="baseline"),
        variants=[ExperimentVariant(name="candidate")],
        metrics=ExperimentMetrics(primary="ndcg@5", target_improvement=0.03),
    )


def _addition_result(
    name: str,
    metrics: dict,
    *,
    status: str = "ok",
    summary_status: str = "ok",
    version: int | None = 1,
    execution_status: str = "completed",
    measurement_status: str = "complete",
    quality_gate: str = "passed",
    identity_status: str = "verified",
) -> VariantResult:
    return VariantResult(
        variant_name=name,
        run_dir=f"/synthetic/{name}",
        metrics=metrics,
        config={},
        timestamp="synthetic",
        measurement_contract_version=version,
        status=status,
        summary_status=summary_status,
        execution_status=execution_status,
        measurement_status=measurement_status,
        quality_gate=quality_gate,
        identity_status=identity_status,
    )


def _summary(baseline: VariantResult, *variants: VariantResult) -> ExperimentSummary:
    return ExperimentSummary(
        experiment_name="synthetic",
        baseline_result=baseline,
        variant_results=list(variants),
        failed_variants=[],
        timestamp="synthetic",
        config=_addition_config(),
    )


def test_addition_winner_ignores_legacy_results():
    legacy = VariantResult(
        variant_name="legacy_high_score",
        run_dir="/synthetic/legacy",
        metrics={"ndcg_at_k": 0.99},
        config={},
        timestamp="legacy",
    )
    summary = _summary(_addition_result("baseline", {"ndcg_at_k": 0.2}), legacy)

    winner_name, _ = summary.get_winner()

    assert winner_name == "baseline"


def test_addition_unverified_identity_cannot_win():
    summary = _summary(
        _addition_result("baseline", {"ndcg_at_k": 0.99}, identity_status="unverified")
    )

    with pytest.raises(ValueError, match="No eligible winner"):
        summary.get_winner()


def test_addition_legacy_only_cohort_has_no_winner():
    legacy_baseline = VariantResult(
        variant_name="baseline",
        run_dir="/synthetic/legacy",
        metrics={"ndcg_at_k": 0.99},
        config={},
        timestamp="legacy",
    )

    with pytest.raises(ValueError, match="No eligible winner"):
        _summary(legacy_baseline).get_winner()


def test_addition_winner_ignores_failed_variant_with_high_score():
    summary = _summary(
        _addition_result("baseline", {"ndcg_at_k": 0.5}),
        _addition_result("failed", {"ndcg_at_k": 0.99}, status="failed"),
    )

    winner_name, _ = summary.get_winner()

    assert winner_name == "baseline"


@pytest.mark.parametrize(
    "metrics",
    [
        {},
        {"ndcg_at_k": float("nan")},
        {"ndcg_at_k": float("inf")},
        {"ndcg_at_k": float("-inf")},
    ],
)
def test_addition_no_winner_for_unavailable_or_nonfinite_primary_metric(metrics):
    summary = _summary(_addition_result("baseline", metrics))

    with pytest.raises(ValueError, match="No eligible winner"):
        summary.get_winner()


def test_addition_measured_zero_is_a_valid_metric_but_not_an_improvement():
    summary = _summary(
        _addition_result("baseline", {"ndcg_at_k": 0.0}),
        _addition_result("candidate", {"ndcg_at_k": 0.5}),
    )

    assert summary.get_winner()[0] == "candidate"
    assert summary.meets_target_improvement("candidate") is False


def test_addition_target_improvement_requires_eligible_baseline_and_variant():
    ineligible_baseline = _summary(
        _addition_result("baseline", {"ndcg_at_k": 0.5}, quality_gate="failed"),
        _addition_result("candidate", {"ndcg_at_k": 0.9}),
    )
    ineligible_variant = _summary(
        _addition_result("baseline", {"ndcg_at_k": 0.5}),
        _addition_result("candidate", {"ndcg_at_k": 0.9}, status="incomplete"),
    )
    failed_summary_status = _summary(
        _addition_result("baseline", {"ndcg_at_k": 0.5}, summary_status="failed"),
        _addition_result("candidate", {"ndcg_at_k": 0.9}),
    )

    assert ineligible_baseline.meets_target_improvement("candidate") is False
    assert ineligible_variant.meets_target_improvement("candidate") is False
    assert failed_summary_status.meets_target_improvement("candidate") is False
    assert failed_summary_status.get_winner()[0] == "candidate"


def test_run_variant_captures_assessment_measurement_contract():
    base_experiment = {
        "metadata": {"name": "synthetic"},
        "dataset": {
            "path": None,
            "max_synthetic_questions": 1,
            "sample_docs_per_source_type": 1,
            "seed": 42,
            "min_label_confidence": "low",
        },
        "evaluation": {"artifact_dir": "unused"},
        "retrieval": {"top_k": 5, "search_mode": "rrf_hybrid"},
        "ingestion": {},
    }

    result = run_variant(
        base_experiment,
        ExperimentVariant(name="candidate"),
        "unused",
        run_assessment_fn=lambda **_: SimpleNamespace(
            run_dir=Path("/synthetic/run"),
            status="incomplete",
            summary={
                "measurement_contract_version": 1,
                "execution_status": "completed",
                "measurement": {"status": "incomplete"},
                "quality_gate": "incomplete",
                "status": "incomplete",
                "retrieval_metrics": {"ndcg_at_k": 0.9},
            },
        ),
    )

    assert result.measurement_contract_version == 1
    assert result.status == "incomplete"
    assert result.summary_status == "incomplete"
    assert result.execution_status == "completed"
    assert result.measurement_status == "incomplete"
    assert result.quality_gate == "incomplete"


def _ablation_metrics(**overrides):
    metrics = {
        "query_count": 7,
        "ndcg_at_k": 0.0,
        "identity_status": "verified",
        "measurement_contract_version": 1,
        "status": "ok",
        "execution_status": "completed",
        "measurement_status": "complete",
        "quality_gate": "passed",
        "exact_chunk_hit_rate": 0.0,
        "evidence_hit_rate": 0.0,
        "latency_p50_ms": 0.0,
    }
    metrics.update(overrides)
    return metrics


def test_ablation_selection_preserves_valid_zero_scores_and_excludes_failed_high_score():
    winner_name, metrics = select_best_variant(
        {
            "measured_zero": _ablation_metrics(),
            "failed_high": _ablation_metrics(ndcg_at_k=0.99, status="failed"),
        }
    )

    assert winner_name == "measured_zero"
    assert metrics["ndcg_at_k"] == 0.0


@pytest.mark.parametrize(
    "metrics",
    [
        {},
        {"query_count": 0, "ndcg_at_k": 0.9},
        {"query_count": 2.5, "ndcg_at_k": 0.9},
        {"query_count": 7},
        _ablation_metrics(query_count=float("inf")),
        _ablation_metrics(ndcg_at_k=float("nan")),
        _ablation_metrics(ndcg_at_k=float("inf")),
        _ablation_metrics(exact_chunk_hit_rate=float("nan")),
        _ablation_metrics(latency_p50_ms=float("inf")),
        _ablation_metrics(status="incomplete"),
        _ablation_metrics(status="unknown"),
        _ablation_metrics(quality_gate=None),
        _ablation_metrics(measurement={"status": "incomplete"}),
        _ablation_metrics(ndcg_at_k=True),
        _ablation_metrics(error="synthetic failure"),
        _ablation_metrics(identity_status="unverified"),
    ],
)
def test_ablation_selection_rejects_incomplete_or_unavailable_metrics(metrics):
    with pytest.raises(ValueError, match="No eligible ablation variant"):
        select_best_variant({"unavailable": metrics})


def test_ablation_selection_rejects_empty_cohort():
    with pytest.raises(ValueError, match="No eligible ablation variant"):
        select_best_variant({})


@pytest.mark.parametrize(
    ("result_status", "summary_overrides"),
    [
        ("incomplete", {}),
        ("ok", {"status": "failed"}),
        ("ok", {"measurement_contract_version": None}),
        ("ok", {"execution_status": "failed"}),
        ("ok", {"measurement": {"status": "incomplete"}}),
        ("ok", {"quality_gate": "failed"}),
    ],
)
def test_ablation_runner_excludes_incomplete_variants_from_leader_selection(
    result_status, summary_overrides
):
    calls: list[dict] = []
    experiment = {
        "metadata": {"name": "synthetic"},
        "dataset": {
            "path": None,
            "max_synthetic_questions": 1,
            "sample_docs_per_source_type": 1,
            "seed": 42,
            "min_label_confidence": "low",
        },
        "evaluation": {"artifact_dir": "unused"},
        "retrieval": {"top_k": 5, "search_mode": "rrf_hybrid"},
        "embedding_index": {"collection_name": "synthetic", "collection_name_suffix": ""},
        "ingestion": {},
    }

    def failed_assessment(**kwargs):
        calls.append(kwargs)
        summary = {
            "measurement_contract_version": 1,
            "execution_status": "completed",
            "measurement": {"status": "complete"},
            "quality_gate": "passed",
            "status": "ok",
            "identity": {"status": "verified"},
            "retrieval_metrics": _ablation_metrics(),
        }
        summary.update(summary_overrides)
        return SimpleNamespace(
            run_dir=Path(f"/synthetic/run-{len(calls)}"),
            status=result_status,
            summary=summary,
        )

    result = run_feature_family(
        experiment,
        "keyword",
        include_answer_eval_for_winner=True,
        run_assessment_fn=failed_assessment,
    )

    assert len(calls) == 4
    assert result["winner_variant"] is None
    assert result["answer_eval_status"] == "not run"
    assert all(call["include_answer_eval"] is False for call in calls)
    assert all(call["run_keyword_ablations"] is False for call in calls)
