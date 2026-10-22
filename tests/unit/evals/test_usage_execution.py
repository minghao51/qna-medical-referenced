"""Available SDK counts reach per-run summaries, without inventing cash prices."""

import json

from src.evals.schemas import AssessmentRunParams
from src.infra.usage import usage_call
from tests.unit.evals.test_measurement_completeness import _pipeline


def test_pipeline_persists_observed_usage_without_cross_attempt_accumulation(tmp_path):
    pipeline = _pipeline()
    evaluate = pipeline.evaluate_retrieval_fn

    def retrieval(*args, **kwargs):
        with usage_call(role="embedder") as call:
            call.record_response(
                {
                    "usage": {
                        "prompt_tokens": 7,
                        "completion_tokens": 0,
                        "total_tokens": 7,
                    }
                }
            )
        return evaluate(*args, **kwargs)

    pipeline.evaluate_retrieval_fn = retrieval
    params = AssessmentRunParams(
        artifact_dir=tmp_path,
        name="usage",
        skip_ingestion=True,
        disable_llm_generation=True,
        disable_llm_judging=True,
    )
    for _ in range(2):
        result = pipeline.run(params)
        assert result.summary["identity"]["reviewed_evidence_eligible"] is False
        assert result.summary["identity"]["cohort_eligible"] is False
        assert result.summary["identity"]["promotion_eligible"] is False
        usage = result.summary["usage_summary"]
        assert usage["usage_by_role"]["embedder"]["total_tokens"] == 7
        assert usage["cash_actual_usd"] is None
        assert usage["cash_estimate_usd"] is None
        assert usage["quota_value_usd"] is None
        assert usage["cash_status"] == "incomplete"
        manifest = json.loads((result.run_dir / "manifest.json").read_text())
        assert manifest["usage_summary"] == usage
