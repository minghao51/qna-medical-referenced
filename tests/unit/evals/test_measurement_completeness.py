"""Synthetic regressions for required measurements, never provider-quality evidence."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from src.evals.assessment import answer_eval
from src.evals.assessment.orchestrator import AssessmentPipeline
from src.evals.assessment.thresholds import evaluate_thresholds, is_threshold_pass
from src.evals.schemas import AssessmentRunParams

ANSWER_KEYS = (
    "factual_accuracy",
    "completeness",
    "clinical_relevance",
    "clarity",
    "answer_relevancy",
    "faithfulness",
)


def _answers(count=1):
    return {
        "status": "ok",
        "query_count": count,
        "query_count_scored": count,
        "query_count_complete": count,
        "metric_error_rate": 0.0,
        **{key: {"mean": 1.0, "count": count, "error_count": 0} for key in ANSWER_KEYS},
    }


def _pipeline(dataset=None, answer_metrics=None):
    dataset = (
        [{"query_id": "synthetic-1", "query": "synthetic question"}] if dataset is None else dataset
    )

    def step(aggregate=None):
        return {"aggregate": aggregate or {}, "records": [], "findings": []}

    retrieval = {
        "query_count": len(dataset),
        "exact_chunk_hit_rate_high_conf": 1.0,
        "evidence_hit_rate_high_conf": 1.0,
        "hit_rate_at_k_high_conf": 1.0,
        "mrr_high_conf": 1.0,
        "topic_false_positive_rate": 0.0,
        "duplicate_source_ratio_mean": 0.0,
    }
    return AssessmentPipeline(
        audit_l0_download_fn=lambda: step(),
        assess_l1_html_markdown_quality_fn=lambda: step({"markdown_empty_rate": 0.0}),
        assess_l2_pdf_quality_fn=lambda: step({"empty_page_rate": 0.0}),
        assess_l3_chunking_quality_fn=lambda: step({"duplicate_chunk_rate": 0.0}),
        assess_l4_reference_quality_fn=lambda: step(),
        assess_l5_index_quality_fn=lambda **kwargs: step({"embedding_dim_consistent": True}),
        build_retrieval_dataset_fn=lambda **kwargs: {"dataset": dataset, "stats": {}},
        evaluate_retrieval_fn=lambda *args, **kwargs: ([], retrieval),
        evaluate_answers_fn=lambda *args, **kwargs: (
            [],
            _answers() if answer_metrics is None else answer_metrics,
        ),
        git_head_fn=lambda: "synthetic-revision",
        configure_runtime_for_experiment_fn=lambda config: {},
        initialize_runtime_index_fn=lambda **kwargs: {"status": "ready"},
        log_assessment_to_wandb_fn=lambda **kwargs: {"enabled": False},
        render_summary_fn=lambda **kwargs: "synthetic summary",
        sha256_file_fn=lambda path: None,
    )


def test_missing_required_threshold_is_not_a_pass():
    failures = evaluate_thresholds(
        {}, {}, {}, {"l6.faithfulness_mean": {"op": "min", "value": 0.8}}
    )
    assert failures[0]["reason"] == "missing_required_metric"
    assert failures[0]["value"] is None


@pytest.mark.parametrize(
    "value", [float("inf"), float("-inf"), float("nan"), None, "not-a-score", True, False]
)
@pytest.mark.parametrize("op", ["min", "max"])
def test_nonfinite_or_invalid_metric_cannot_pass(value, op):
    assert is_threshold_pass(value, {"op": op, "value": 0.5})[0] is False


@pytest.mark.parametrize("spec", [{"op": "typo", "value": 1}, {"op": "min", "value": float("nan")}])
def test_invalid_threshold_spec_fails_explicitly(spec):
    with pytest.raises(ValueError):
        is_threshold_pass(1, spec)


def test_boolean_index_dimension_check_is_supported_explicitly():
    spec = {"l5.embedding_dim_consistent": {"op": "min", "value": 1.0}}
    assert (
        evaluate_thresholds({"l5": {"aggregate": {"embedding_dim_consistent": True}}}, {}, {}, spec)
        == []
    )
    failures = evaluate_thresholds(
        {"l5": {"aggregate": {"embedding_dim_consistent": False}}}, {}, {}, spec
    )
    assert failures[0]["value"] == 0.0
    assert failures[0]["reason"] == "quality_threshold"


def test_optional_missing_threshold_is_explicitly_optional():
    assert evaluate_thresholds({}, {}, {}, {"diagnostic": {"value": 1, "required": False}}) == []


def test_credentials_do_not_implicitly_enable_answer_suite(tmp_path):
    config = _pipeline()._resolve_config(AssessmentRunParams(artifact_dir=tmp_path))[0]
    assert config.include_answer_eval is False


def test_role_snapshot_records_independent_judge_without_secrets(monkeypatch, tmp_path):
    from src.config import settings

    monkeypatch.setattr(settings.llm, "provider", "gemini")
    monkeypatch.setattr(settings.llm, "judge_provider", "qwen")
    pipeline = _pipeline()
    config, payload, _, provenance, run_identity, _ = pipeline._resolve_config(
        AssessmentRunParams(artifact_dir=tmp_path, include_answer_eval=True)
    )
    pipeline._update_execution_identity(
        config,
        payload,
        provenance,
        {"status": "unverified", "fingerprint": None},
        run_identity,
    )
    assert payload["roles"]["generator"] == "gemini"
    assert {"light", "heavy", "selected_judge_roles"}.issubset(payload["roles"])
    assert payload["roles"]["selected_judge_roles"]["provider"] == "qwen"
    assert payload["effective_roles"]["answer_eval"]["generator"]["provider"] == "gemini"
    assert payload["effective_roles"]["answer_eval"]["judge"]["provider"] == "qwen"
    assert "api_key" not in json.dumps(payload["effective_roles"])


def test_independent_judge_selection_invalidates_answer_runtime_signature(monkeypatch):
    from src.config import settings

    monkeypatch.setattr(settings.llm, "judge_provider", "gemini")
    before = answer_eval._runtime_signature(5)
    monkeypatch.setattr(settings.llm, "judge_provider", "qwen")
    assert before != answer_eval._runtime_signature(5)


@pytest.mark.parametrize("strict", [False, True])
def test_retrieval_only_run_can_complete_without_answer_metrics(tmp_path, strict):
    pipeline = _pipeline()
    pipeline.render_summary_fn = lambda **kwargs: (
        f"synthetic summary; usage={kwargs['usage_summary']['status']}"
    )
    result = pipeline.run(
        AssessmentRunParams(
            artifact_dir=tmp_path,
            include_answer_eval=False,
            fail_on_thresholds=strict,
            disable_llm_generation=True,
        )
    )
    assert result.status == "ok"
    assert result.summary["measurement"]["status"] == "complete"
    assert result.summary["measurement"]["suites"]["answer"]["status"] == "not_applicable"
    assert result.summary["quality_gate"] == "passed"
    from src.evals.assessment.l6_contract import MEASUREMENT_CONTRACT_VERSION

    assert result.summary["measurement_contract_version"] == MEASUREMENT_CONTRACT_VERSION
    usage = result.summary["usage_summary"]
    manifest = json.loads((result.run_dir / "manifest.json").read_text())
    assert usage == manifest["usage_summary"]
    assert usage["status"] == "incomplete"
    assert usage["cash_actual_usd"] is None
    assert usage["usage_by_role"]["embedder"]["total_tokens"] is None
    assert "embedder_usage_unknown" in usage["unknowns"]
    assert "usage=incomplete" in (result.run_dir / "summary.md").read_text()


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "skipped", "reason": "missing_dependency"},
        {"status": "error", "reason": "missing_role_credentials"},
        {"status": "ok", "query_count": 1, "query_count_scored": 0},
        {**_answers(), "faithfulness": {"mean": 1.0, "count": 0, "error_count": 1}},
        {**_answers(), "faithfulness": {"mean": float("inf"), "count": 1}},
        {**_answers(), "faithfulness": {"mean": True, "count": 1}},
        {**_answers(), "faithfulness": {"mean": False, "count": 1}},
    ],
)
def test_requested_answer_suite_cannot_pass_incomplete_measurement(tmp_path, payload):
    result = _pipeline(answer_metrics=payload).run(
        AssessmentRunParams(
            artifact_dir=tmp_path,
            include_answer_eval=True,
            disable_llm_generation=True,
        )
    )
    assert result.status == "incomplete"
    assert result.summary["measurement"]["status"] == "incomplete"
    assert result.summary["quality_gate"] == "incomplete"


def test_empty_selected_dataset_is_incomplete_not_zero_quality_pass(tmp_path):
    result = _pipeline(dataset=[]).run(
        AssessmentRunParams(artifact_dir=tmp_path, include_answer_eval=False)
    )
    assert result.status == "incomplete"
    assert result.summary["measurement"]["suites"]["retrieval"]["expected"] == 0


def test_quality_failure_stays_failed_in_exploratory_mode(tmp_path):
    payload = _answers()
    payload["faithfulness"]["mean"] = 0.1
    result = _pipeline(answer_metrics=payload).run(
        AssessmentRunParams(
            artifact_dir=tmp_path,
            include_answer_eval=True,
            fail_on_thresholds=False,
        )
    )
    assert result.status == "failed"
    assert result.summary["measurement"]["status"] == "complete"
    assert result.summary["quality_gate"] == "failed"


@pytest.mark.asyncio
async def test_generation_failure_preserves_other_case_and_denominators(monkeypatch, tmp_path):
    from pydantic import SecretStr

    from src.config import settings
    from src.evals.metrics import medical

    # Fake Gemini generation/judging must not depend on a DashScope generation key.
    monkeypatch.setattr(settings.llm, "provider", "gemini")
    monkeypatch.setattr(settings.llm, "judge_provider", "gemini")
    monkeypatch.setattr(settings.llm, "dashscope_api_key", SecretStr(""))
    monkeypatch.setattr(settings.llm, "gemini_api_key", SecretStr("synthetic-only"))

    async def prepare(item, **kwargs):
        if item["query_id"] == "bad":
            raise RuntimeError("synthetic-secret-canary")
        return answer_eval.AnswerQualityCase(
            query_id=item["query_id"],
            query=item["query"],
            context="synthetic evidence",
            sources=[],
            trace={},
            answer="synthetic answer",
            timings={},
            cache={},
        )

    class Metric:
        score = 1.0
        error = None
        reason = "synthetic reason"

        async def a_measure(self, case):
            return self.score

    monkeypatch.setattr(answer_eval, "_prepare_answer_case", prepare)
    monkeypatch.setattr(answer_eval, "safe_a_measure", None)
    monkeypatch.setattr(
        medical, "create_medical_metrics", lambda: [Metric() for _ in medical.METRIC_SPECS]
    )
    rows, aggregate = await answer_eval.evaluate_answer_quality_async(
        [{"query_id": "bad", "query": "bad"}, {"query_id": "good", "query": "good"}],
        5,
        cache_dir=tmp_path,
    )
    assert len(rows) == 2
    assert aggregate["query_count"] == 2
    assert aggregate["query_count_complete"] == 1
    assert aggregate["query_count_failed"] == 1
    for key in ANSWER_KEYS:
        assert aggregate[key]["count"] == 1
        assert aggregate[key]["error_count"] == 1
    assert "synthetic-secret-canary" not in json.dumps(rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("metric_score", [float("inf"), True, False])
async def test_nonfinite_metric_is_error_and_not_reused(monkeypatch, metric_score):
    monkeypatch.setattr(answer_eval, "safe_a_measure", None)

    class Metric:
        score = metric_score
        error = None
        reason = None

        async def a_measure(self, case):
            return self.score

    result = await answer_eval._evaluate_metric(
        Metric(), SimpleNamespace(), semaphore=asyncio.Semaphore(1)
    )
    assert result["status"] == "error"
    assert result["score"] is None


@pytest.mark.asyncio
async def test_case_cancellation_propagates_without_publishing_cache(monkeypatch, tmp_path):
    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(answer_eval, "_prepare_answer_case", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await answer_eval.evaluate_answer_quality_async(
            [{"query": "synthetic question"}],
            5,
            cache_dir=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_incomplete_run_is_not_reused(tmp_path):
    pipeline = _pipeline(answer_metrics={"status": "skipped"})
    params = AssessmentRunParams(artifact_dir=tmp_path, include_answer_eval=True)
    first = pipeline.run(params)
    second = pipeline.run(params)
    assert first.status == second.status == "incomplete"
    assert first.run_dir != second.run_dir
    assert second.summary["dedup"]["reused_existing_run"] is False


def test_existing_reader_loads_new_incomplete_and_unchanged_legacy_results(tmp_path):
    from src.evals.artifact_service import EvaluationService

    legacy = tmp_path / "20200101T000000_legacy"
    legacy.mkdir()
    original = '{"status":"ok","legacy_note":"synthetic historical result"}'
    (legacy / "summary.json").write_text(original)
    (legacy / "retrieval_metrics.json").write_text('{"query_count":1}')
    result = _pipeline(answer_metrics={"status": "skipped"}).run(
        AssessmentRunParams(artifact_dir=tmp_path, include_answer_eval=True),
    )
    service = EvaluationService(tmp_path, tmp_path / "latest_run.txt")
    rows = {row["run_dir"]: row for row in service.get_all_runs()}
    assert rows[result.run_dir.name]["status"] == "incomplete"
    assert rows[legacy.name]["status"] == "ok"
    assert service.read_summary(result.run_dir)["quality_gate"] == "incomplete"
    assert "measurement_contract_version" not in service.read_summary(legacy)
    assert (legacy / "summary.json").read_text() == original


def test_fresh_attempts_have_separate_answer_cache_directories(tmp_path):
    pipeline = _pipeline()
    paths = []

    def evaluate(*args, **kwargs):
        paths.append(kwargs["cache_dir"])
        return [], _answers()

    pipeline.evaluate_answers_fn = evaluate
    params = AssessmentRunParams(artifact_dir=tmp_path, include_answer_eval=True, force_rerun=True)
    first = pipeline.run(params)
    second = pipeline.run(params)
    assert paths == [first.run_dir / "cache", second.run_dir / "cache"]
    assert paths[0] != paths[1]


@pytest.mark.asyncio
async def test_failed_metric_cache_entry_is_not_reused(monkeypatch):
    spec = SimpleNamespace(key="faithfulness")
    case = answer_eval.AnswerQualityCase(
        query_id="synthetic",
        query="question",
        context="evidence",
        sources=[],
        trace={},
        answer="answer",
        timings={},
        cache={},
    )
    cache_key = answer_eval._metric_cache_key(case, {})
    cache = {
        cache_key: {
            "metrics": {"faithfulness": {"status": "error", "score": None}},
            "score_updates": {"faithfulness": None},
        }
    }
    called = []

    def missing_dependency():
        called.append(True)
        raise ModuleNotFoundError("synthetic-secret-canary")

    result, scores, cached = await answer_eval._evaluate_case_metrics(
        case,
        metric_specs=[spec],
        metric_builder=missing_dependency,
        runtime_signature={},
        metric_cache=cache,
        metric_cache_enabled=True,
        metric_concurrency=1,
    )
    assert called == [True]
    assert cached is False
    assert scores == {"faithfulness": None}
    assert result["faithfulness"]["error"] == "missing_evaluation_dependency"


@pytest.mark.asyncio
async def test_missing_selected_judge_key_reports_only_credential_name(monkeypatch, tmp_path):
    from pydantic import SecretStr

    from src.config import settings

    monkeypatch.setattr(settings.llm, "provider", "gemini")
    monkeypatch.setattr(settings.llm, "judge_provider", "qwen")
    monkeypatch.setattr(settings.llm, "dashscope_api_key", SecretStr(""))
    rows, metrics = await answer_eval.evaluate_answer_quality_async(
        [{"query": "synthetic question"}],
        5,
        cache_dir=tmp_path,
    )
    assert rows == []
    assert metrics["status"] == "error"
    assert metrics["missing_credentials"] == [
        {"role": "judge", "setting": "APP__LLM__DASHSCOPE_API_KEY"}
    ]
    assert metrics["query_count_failed"] == 1


@pytest.mark.asyncio
async def test_empty_answer_suite_never_reports_ok(tmp_path):
    rows, metrics = await answer_eval.evaluate_answer_quality_async([], 5, cache_dir=tmp_path)
    assert rows == []
    assert metrics["status"] == "incomplete"
    assert metrics["query_count"] == 0
