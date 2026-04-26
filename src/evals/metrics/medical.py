"""Medical-specific DeepEval metric definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCaseParams

from src.config import settings
from src.evals.deepeval_models import get_heavy_model, get_light_model

MetricFactory = GEval | AnswerRelevancyMetric | FaithfulnessMetric


@dataclass(frozen=True)
class MetricSpec:
    key: str
    display_name: str
    judge_tier: str
    factory: Any

    def create(self) -> MetricFactory:
        return self.factory()  # type: ignore[no-any-return]


def _build_factual_accuracy() -> GEval:
    return GEval(
        name="Factual Accuracy",
        criteria="""You are a medical information evaluator. Assess the factual accuracy of the answer.

Step-by-step evaluation:
1. Identify all factual claims in the answer
2. Verify each claim against the retrieved context
3. Flag any claims not supported by context (hallucinations)
4. Check for contradictions to medical principles

Rate from 1-5:
- 5: All claims fully grounded in context
- 4: Minor issues, no hallucinations
- 3: Some ungrounded claims, mostly accurate
- 2: Multiple ungrounded claims
- 1: Major hallucinations, contradicts context""",
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.RETRIEVAL_CONTEXT,
        ],
        threshold=0.8,
        model=get_heavy_model(),
        async_mode=True,
    )


def _build_completeness() -> GEval:
    return GEval(
        name="Completeness",
        criteria="""Assess if the answer completely addresses the medical question.

Evaluation criteria:
- Does it answer the specific question asked?
- Does it cover all aspects of multi-part questions?
- Are there missing key details?
- Does it provide appropriate context/background?

Rate from 1-5:
- 5: Fully complete, covers all aspects
- 4: Mostly complete, minor omissions
- 3: Adequate, some missing aspects
- 2: Incomplete, missing key details
- 1: Fails to address the question""",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.75,
        model=get_heavy_model(),
        async_mode=True,
    )


def _build_clinical_relevance() -> GEval:
    return GEval(
        name="Clinical Relevance",
        criteria="""Evaluate clinical relevance and appropriateness for medical practice.

Criteria:
- Is information consistent with current clinical guidelines?
- Are recommendations appropriate for the context?
- Does it mention relevant contraindications/warnings?
- Is it suitable for clinical decision-making support?

Rate from 1-5:
- 5: Clinically excellent, guideline-consistent
- 4: Good clinical relevance
- 3: Adequate, minor concerns
- 2: Potentially misleading, deviations from practice
- 1: Clinically inappropriate, dangerous""",
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.RETRIEVAL_CONTEXT,
        ],
        threshold=0.8,
        model=get_heavy_model(),
        async_mode=True,
    )


def _build_clarity() -> GEval:
    return GEval(
        name="Clarity",
        criteria="""Assess answer clarity for healthcare professionals.

Criteria:
- Is the explanation clear and understandable?
- Is the information well-structured?
- Is medical terminology used appropriately?
- Is the tone professional yet accessible?

Rate from 1-5:
- 5: Very clear, well-structured
- 4: Clear, minor organization issues
- 3: Understandable, could be clearer
- 2: Confusing in parts
- 1: Very unclear, poorly structured""",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.70,
        model=get_light_model(),
        async_mode=True,
    )


def _build_answer_relevancy() -> AnswerRelevancyMetric:
    return AnswerRelevancyMetric(
        threshold=0.7,
        model=get_light_model(),
        async_mode=True,
        include_reason=False,
    )


def _build_faithfulness() -> FaithfulnessMetric:
    return FaithfulnessMetric(
        threshold=0.8,
        model=get_heavy_model(),
        async_mode=True,
        include_reason=False,
        truths_extraction_limit=settings.deepeval.deepeval_faithfulness_truths_limit,
    )


METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        key="factual_accuracy",
        display_name="Factual Accuracy",
        judge_tier="heavy",
        factory=_build_factual_accuracy,
    ),
    MetricSpec(
        key="completeness",
        display_name="Completeness",
        judge_tier="heavy",
        factory=_build_completeness,
    ),
    MetricSpec(
        key="clinical_relevance",
        display_name="Clinical Relevance",
        judge_tier="heavy",
        factory=_build_clinical_relevance,
    ),
    MetricSpec(
        key="clarity",
        display_name="Clarity",
        judge_tier="light",
        factory=_build_clarity,
    ),
    MetricSpec(
        key="answer_relevancy",
        display_name="AnswerRelevancyMetric",
        judge_tier="light",
        factory=_build_answer_relevancy,
    ),
    MetricSpec(
        key="faithfulness",
        display_name="FaithfulnessMetric",
        judge_tier="heavy",
        factory=_build_faithfulness,
    ),
)


def create_medical_metrics() -> list[MetricFactory]:
    """Return fresh metric instances for each evaluation run."""
    return [spec.create() for spec in METRIC_SPECS]


__all__ = ["METRIC_SPECS", "MetricSpec", "create_medical_metrics"]
