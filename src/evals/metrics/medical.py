"""Medical-specific evaluation metrics using DeepEval's GEval.

This module defines custom evaluation metrics for medical Q&A systems,
assessing factual accuracy, completeness, clinical relevance, and clarity.
Implements model tiering for cost optimization.
"""

from deepeval.metrics import GEval, AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCaseParams
from src.evals.deepeval_models import get_light_model, get_heavy_model

# =============================================================================
# Custom Medical Metrics (using GEval with LLM-as-a-judge)
# =============================================================================

# Factual Accuracy Judge (Heavyweight model - requires Chain-of-Thought)
factual_accuracy_metric = GEval(
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
        LLMTestCaseParams.RETRIEVAL_CONTEXT
    ],
    threshold=0.8,
    model=get_heavy_model()
)

# Completeness Judge (Heavyweight model - requires Chain-of-Thought)
completeness_metric = GEval(
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
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT
    ],
    threshold=0.75,
    model=get_heavy_model()
)

# Clinical Relevance Judge (Heavyweight model - requires domain expertise)
clinical_relevance_metric = GEval(
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
        LLMTestCaseParams.RETRIEVAL_CONTEXT
    ],
    threshold=0.8,
    model=get_heavy_model()
)

# Clarity Judge (Lightweight model - simpler classification)
clarity_metric = GEval(
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
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT
    ],
    threshold=0.70,
    model=get_light_model()
)

# =============================================================================
# Built-in DeepEval Metrics
# =============================================================================

# Answer Relevancy (Lightweight model)
answer_relevancy_metric = AnswerRelevancyMetric(
    threshold=0.7,
    model=get_light_model()
)

# Faithfulness/Hallucination Detection (Heavyweight model)
faithfulness_metric = FaithfulnessMetric(
    threshold=0.8,
    model=get_heavy_model()
)
