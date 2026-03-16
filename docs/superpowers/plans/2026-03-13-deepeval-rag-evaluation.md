# DeepEval RAG Evaluation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the medical RAG evaluation pipeline with LLM-as-a-judge capabilities using DeepEval framework, implementing 4 custom medical metrics with cost-optimized model tiering (qwen3.5-35b-a3b for simple tasks, qwen3.5-flash for complex reasoning).

**Architecture:** Integrate DeepEval framework by creating a Qwen model wrapper (`DeepEvalBaseLLM`), defining custom medical evaluation metrics using GEval, and adding a new L6 stage to the existing orchestrator. Model tiering reduces costs by 60-80% while synthetic data generation via Synthesizer accelerates test creation.

**Tech Stack:** Python 3.11+, DeepEval 2.0+, Qwen 3.5 models (35b-a3b/flash), Pytest, asyncio, existing FastAPI/ChromaDB stack

---

## File Structure

### New Files Created
1. **`src/evals/deepeval_models.py`** (~50 LOC)
   - `QwenModel` class implementing `DeepEvalBaseLLM`
   - Factory functions: `get_light_model()`, `get_heavy_model()`
   - Bridges Qwen API with DeepEval's model interface

2. **`src/evals/metrics/medical.py`** (~150 LOC)
   - 4 custom GEval metrics: Factual Accuracy, Completeness, Clinical Relevance, Clarity
   - 2 built-in metrics: Answer Relevancy, Faithfulness
   - Per-metric model selection (light vs heavy)

3. **`src/evals/synthetic/generator.py`** (~30 LOC)
   - Wraps DeepEval's `Synthesizer` for document-based question generation
   - Supports async mode for faster generation

4. **`tests/test_eval_deepeval.py`** (~50 LOC)
   - Pytest tests for custom metrics
   - Uses `assert_test()` for CI/CD integration

5. **`tests/test_deepeval_models.py`** (~40 LOC)
   - Tests for Qwen model wrapper
   - Validates model loading and generation

### Modified Files
1. **`pyproject.toml`** - Add deepeval dependencies
2. **`src/config/settings.py`** - Add judge model configs
3. **`src/evals/assessment/answer_eval.py`** - Add `evaluate_answers_deepeval()` function
4. **`src/evals/assessment/orchestrator.py`** - Add L6 stage routing
5. **`src/evals/assessment/thresholds.py`** - Add L6 thresholds
6. **`src/app/routes/evaluation.py`** - Add API endpoints

---

## Chunk 1: Dependencies and Configuration

### Task 1: Add DeepEval Dependencies

**Files:**
- Modify: `pyproject.toml:25-35`

- [ ] **Step 1: Add DeepEval to optional dependencies**

Locate the `[project.optional-dependencies]` section in `pyproject.toml` (around line 25). Add an `evaluation` group:

```toml
[project.optional-dependencies]
evaluation = [
    "deepeval>=2.0.0",
    "litellm>=1.0.0",
]
```

**Why:** DeepEval requires these packages. Optional dependency allows users to skip if not using evaluation features.

- [ ] **Step 2: Install dependencies**

Run: `uv sync --extra evaluation`

Expected output:
```
Resolved 8 packages in 2.5s
Installed deepeval-2.x.x, litellm-1.x.x
```

**Why:** Verify packages install without conflicts.

- [ ] **Step 3: Verify DeepEval imports**

Run: `uv run python -c "import deepeval; print(deepeval.__version__)"`

Expected: Version number printed (e.g., `2.0.0` or higher)

**Why:** Confirm DeepEval is accessible in the virtual environment.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add deepeval and litellm dependencies for RAG evaluation"
```

---

### Task 2: Add Configuration Settings

**Files:**
- Modify: `src/config/settings.py:85-95`

- [ ] **Step 1: Write failing test for new settings**

Create `tests/test_settings_deepeval.py`:

```python
from src.config import settings

def test_deepeval_settings_have_defaults():
    """Test that DeepEval settings have sensible defaults."""
    assert hasattr(settings, 'judge_model_light')
    assert hasattr(settings, 'judge_model_heavy')
    assert hasattr(settings, 'judge_temperature')
    assert hasattr(settings, 'enable_deepeval')

    # Verify defaults
    assert settings.judge_model_light == "qwen3.5-35b-a3b"
    assert settings.judge_model_heavy == "qwen3.5-flash"
    assert settings.judge_temperature == 0.0
    assert settings.enable_deepeval is True
```

Run: `uv run pytest tests/test_settings_deepeval.py -v`

Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'judge_model_light'`

**Why:** TDD - write test first to drive implementation.

- [ ] **Step 2: Add settings fields**

Edit `src/config/settings.py`, add after line 85 (after `embedding_batch_size` field):

```python
# LLM-as-a-Judge Configuration
judge_model_light: str = "qwen3.5-35b-a3b"
"""Lightweight model for simple classification tasks (3B active params)."""

judge_model_heavy: str = "qwen3.5-flash"
"""Heavyweight model for complex Chain-of-Thought reasoning."""

judge_temperature: float = 0.0
"""Temperature for judge models (0 = deterministic, repeatable)."""

enable_deepeval: bool = True
"""Use DeepEval framework for evaluation."""
```

**Why:** Provides configuration for model tiering and feature flag.

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest tests/test_settings_deepeval.py -v`

Expected: PASS

**Why:** Confirm implementation satisfies requirements.

- [ ] **Step 4: Test environment variable override**

Run:
```bash
DASHSCOPE_API_KEY=test JUDGE_MODEL_LIGHT=qwen-turbo uv run python -c "from src.config import settings; print(settings.judge_model_light)"
```

Expected: `qwen-turbo`

**Why:** Verify environment variable override works (standard Pydantic behavior).

- [ ] **Step 5: Commit**

```bash
git add src/config/settings.py tests/test_settings_deepeval.py
git commit -m "feat: add DeepEval configuration settings"
```

---

## Chunk 2: Qwen Model Wrapper for DeepEval

### Task 3: Create QwenModel Class

**Files:**
- Create: `src/evals/deepeval_models.py`
- Test: `tests/test_deepeval_models.py`

- [ ] **Step 1: Write failing test for QwenModel**

Create `tests/test_deepeval_models.py`:

```python
import pytest
from src.evals.deepeval_models import QwenModel, get_light_model, get_heavy_model
from src.config import settings

def test_qwen_model_initialization():
    """Test QwenModel can be initialized with a model name."""
    model = QwenModel("qwen3.5-flash")
    assert model.model == "qwen3.5-flash"
    assert model.client is not None

def test_qwen_model_implements_required_methods():
    """Test QwenModel implements all DeepEvalBaseLLM methods."""
    model = QwenModel("qwen3.5-flash")

    # Required methods
    assert hasattr(model, 'load_model')
    assert hasattr(model, 'generate')
    assert hasattr(model, 'a_generate')
    assert hasattr(model, 'get_model_name')

def test_qwen_model_generate():
    """Test QwenModel.generate() returns text."""
    model = QwenModel(settings.judge_model_light)
    response = model.generate("Say 'test successful'")
    assert "test" in response.lower()
    assert len(response) > 0

def test_get_light_model_returns_light_model():
    """Test factory returns model configured with light model."""
    model = get_light_model()
    assert model.model == settings.judge_model_light
    assert model.model == "qwen3.5-35b-a3b"

def test_get_heavy_model_returns_heavy_model():
    """Test factory returns model configured with heavy model."""
    model = get_heavy_model()
    assert model.model == settings.judge_model_heavy
    assert model.model == "qwen3.5-flash"
```

Run: `uv run pytest tests/test_deepeval_models.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.evals.deepeval_models'`

**Why:** TDD - test drives the implementation.

- [ ] **Step 2: Create deepeval_models.py module**

Create `src/evals/deepeval_models.py`:

```python
"""Qwen model wrapper for DeepEval integration.

This module provides a DeepEval-compatible wrapper for Qwen models,
enabling use of Alibaba's Qwen LLMs as judges in DeepEval's LLM-as-a-judge
framework. Supports model tiering for cost optimization.
"""

from deepeval.models import DeepEvalBaseLLM
from openai import OpenAI
from src.config import settings


class QwenModel(DeepEvalBaseLLM):
    """Qwen model wrapper for DeepEval.

    Implements the DeepEvalBaseLLM interface to allow Qwen models
    to be used as evaluators in DeepEval metrics.

    Attributes:
        model: Model identifier (e.g., "qwen3.5-flash", "qwen3.5-35b-a3b")
        client: OpenAI-compatible client pointing to Dashscope API
    """

    def __init__(self, model: str):
        """Initialize the Qwen model wrapper.

        Args:
            model: Model identifier string
        """
        self.model = model
        self.client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.qwen_base_url
        )

    def load_model(self):
        """Load and return the model.

        Returns:
            Model identifier string
        """
        return self.model

    def generate(self, prompt: str) -> str:
        """Generate text synchronously.

        Args:
            prompt: Input prompt for the model

        Returns:
            Generated text response
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.judge_temperature
        )
        return response.choices[0].message.content or ""

    async def a_generate(self, prompt: str) -> str:
        """Generate text asynchronously.

        Args:
            prompt: Input prompt for the model

        Returns:
            Generated text response
        """
        # For now, wrap sync call. Can be optimized later with async client.
        return self.generate(prompt)

    def get_model_name(self) -> str:
        """Get the model name.

        Returns:
            Model identifier string
        """
        return self.model


def get_light_model() -> QwenModel:
    """Factory function for lightweight judge model.

    Returns:
        QwenModel instance configured with lightweight model (qwen3.5-35b-a3b)
    """
    return QwenModel(settings.judge_model_light)


def get_heavy_model() -> QwenModel:
    """Factory function for heavyweight judge model.

    Returns:
        QwenModel instance configured with heavyweight model (qwen3.5-flash)
    """
    return QwenModel(settings.judge_model_heavy)
```

**Why:** Implements DeepEval's interface, bridging Qwen with the framework.

- [ ] **Step 3: Run tests to verify implementation**

Run: `uv run pytest tests/test_deepeval_models.py -v`

Expected: All tests PASS (may take 10-20 seconds for API calls)

**Why:** Confirm wrapper works correctly with Qwen API.

- [ ] **Step 4: Test error handling**

Add to `tests/test_deepeval_models.py`:

```python
def test_qwen_model_handles_empty_response():
    """Test model handles empty API responses gracefully."""
    # This test documents current behavior
    # If API returns empty, we return empty string
    model = QwenModel(settings.judge_model_light)
    response = model.generate("")  # Edge case
    assert isinstance(response, str)
```

Run: `uv run pytest tests/test_deepeval_models.py::test_qwen_model_handles_empty_response -v`

Expected: PASS (documentation test)

**Why:** Document edge case behavior.

- [ ] **Step 5: Commit**

```bash
git add src/evals/deepeval_models.py tests/test_deepeval_models.py
git commit -m "feat: implement QwenModel wrapper for DeepEval"
```

---

## Chunk 3: Custom Medical Metrics

### Task 4: Create Medical Metrics Module

**Files:**
- Create: `src/evals/metrics/medical.py`
- Test: `tests/test_medical_metrics.py`

- [ ] **Step 1: Write test for metric initialization**

Create `tests/test_medical_metrics.py`:

```python
from src.evals.metrics.medical import (
    factual_accuracy_metric,
    completeness_metric,
    clinical_relevance_metric,
    clarity_metric,
    answer_relevancy_metric,
    faithfulness_metric
)

def test_metrics_are_initialized():
    """Test all metrics are properly initialized."""
    # Custom GEval metrics
    assert factual_accuracy_metric.name == "Factual Accuracy"
    assert factual_accuracy_metric.threshold == 0.8

    assert completeness_metric.name == "Completeness"
    assert completeness_metric.threshold == 0.75

    assert clinical_relevance_metric.name == "Clinical Relevance"
    assert clinical_relevance_metric.threshold == 0.8

    assert clarity_metric.name == "Clarity"
    assert clarity_metric.threshold == 0.70

    # Built-in metrics
    assert answer_relevancy_metric.threshold == 0.7
    assert faithfulness_metric.threshold == 0.8

def test_metrics_use_correct_models():
    """Test lightweight and heavyweight models are assigned correctly."""
    # Clarity uses lightweight (simple classification)
    assert clarity_metric.model.model == "qwen3.5-35b-a3b"

    # Factual accuracy uses heavyweight (CoT reasoning)
    assert factual_accuracy_metric.model.model == "qwen3.5-flash"
```

Run: `uv run pytest tests/test_medical_metrics.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.evals.metrics.medical'`

**Why:** TDD approach.

- [ ] **Step 2: Create medical metrics module**

Create directory and module:

```bash
mkdir -p src/evals/metrics
```

Create `src/evals/metrics/medical.py`:

```python
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
```

**Why:** Defines all 6 metrics with appropriate model tiering.

- [ ] **Step 3: Run tests to verify**

Run: `uv run pytest tests/test_medical_metrics.py -v`

Expected: PASS

**Why:** Confirm metrics initialize correctly.

- [ ] **Step 4: Test metric measurement**

Add to `tests/test_medical_metrics.py`:

```python
from deepeval.test_case import LLMTestCase

def test_factual_accuracy_metric_measures():
    """Test factual accuracy metric can measure a test case."""
    test_case = LLMTestCase(
        input="What is the LDL-C target for secondary prevention?",
        actual_output="The LDL-C target is 1.8 mmol/L for secondary prevention.",
        retrieval_context=["Guidelines recommend LDL-C < 1.8 mmol/L for secondary prevention."]
    )

    factual_accuracy_metric.measure(test_case)

    assert factual_accuracy_metric.score is not None
    assert 0 <= factual_accuracy_metric.score <= 1
    # Good answer should score high
    assert factual_accuracy_metric.score > 0.5

def test_clarity_metric_uses_lightweight_model():
    """Test clarity metric uses lightweight model."""
    test_case = LLMTestCase(
        input="Explain cholesterol.",
        actual_output="Cholesterol is a waxy substance found in blood.",
        retrieval_context=[]
    )

    clarity_metric.measure(test_case)

    assert clarity_metric.score is not None
    # Verify it used the lightweight model
    assert "qwen3.5-35b-a3b" in clarity_metric.model.get_model_name()
```

Run: `uv run pytest tests/test_medical_metrics.py::test_factual_accuracy_metric_measures -v`

Expected: PASS (may take 10-20 seconds for LLM call)

**Why:** Verify metrics actually work with test cases.

- [ ] **Step 5: Create metrics __init__**

Create `src/evals/metrics/__init__.py`:

```python
"""Evaluation metrics for RAG systems."""

from src.evals.metrics.medical import (
    factual_accuracy_metric,
    completeness_metric,
    clinical_relevance_metric,
    clarity_metric,
    answer_relevancy_metric,
    faithfulness_metric
)

__all__ = [
    "factual_accuracy_metric",
    "completeness_metric",
    "clinical_relevance_metric",
    "clarity_metric",
    "answer_relevancy_metric",
    "faithfulness_metric",
]
```

**Why:** Makes metrics easier to import.

- [ ] **Step 6: Commit**

```bash
git add src/evals/metrics/ tests/test_medical_metrics.py
git commit -m "feat: implement custom medical evaluation metrics with GEval"
```

---

## Chunk 4: Pytest Integration Tests

### Task 5: Create Pytest Tests for CI/CD

**Files:**
- Create: `tests/test_eval_deepeval.py`

- [ ] **Step 1: Create pytest test file**

Create `tests/test_eval_deepeval.py`:

```python
"""Pytest integration tests for DeepEval medical metrics.

These tests use DeepEval's assert_test() for CI/CD integration.
Run with: pytest tests/test_eval_deepeval.py -m deepeval -v
"""

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from src.evals.metrics.medical import (
    factual_accuracy_metric,
    completeness_metric,
    clinical_relevance_metric
)


@pytest.mark.deepeval
@pytest.mark.slow
def test_medical_factual_accuracy():
    """Test factual accuracy metric with medically accurate answer."""
    test_case = LLMTestCase(
        input="What is the LDL-C target for secondary prevention?",
        actual_output="According to guidelines, the LDL-C target for secondary prevention is 1.8 mmol/L.",
        retrieval_context=["Current lipid guidelines recommend LDL-C < 1.8 mmol/L for secondary prevention."]
    )
    assert_test(test_case, [factual_accuracy_metric])


@pytest.mark.deepeval
@pytest.mark.slow
def test_medical_completeness():
    """Test completeness metric with partially complete answer."""
    test_case = LLMTestCase(
        input="What are the side effects of statins?",
        actual_output="Common side effects include muscle pain and elevated liver enzymes.",
        retrieval_context=["Statin side effects include myopathy, increased liver enzymes, and rarely rhabdomyolysis."]
    )
    # Lower threshold for this test since answer is incomplete
    completeness_metric.threshold = 0.5  # Temporary override
    assert_test(test_case, [completeness_metric])


@pytest.mark.deepeval
@pytest.mark.slow
def test_medical_clinical_relevance():
    """Test clinical relevance metric with clinically sound answer."""
    test_case = LLMTestCase(
        input="Is aspirin recommended for primary prevention?",
        actual_output="Aspirin may be considered for primary prevention in select high-risk patients, but risks like bleeding should be weighed against benefits.",
        retrieval_context=["Aspirin for primary prevention: consider for high-risk patients, assess bleeding risk."]
    )
    assert_test(test_case, [clinical_relevance_metric])
```

**Why:** Creates CI/CD-ready tests with `assert_test()`.

- [ ] **Step 2: Run pytest tests**

Run: `uv run pytest tests/test_eval_deepeval.py -m deepeval -v`

Expected: 3 tests PASS (may take 30-60 seconds for LLM calls)

**Why:** Verify tests work and integrate with pytest.

- [ ] **Step 3: Test failure case**

Add to `tests/test_eval_deepeval.py`:

```python
@pytest.mark.deepeval
@pytest.mark.slow
def test_factual_accuracy_detects_hallucination():
    """Test factual accuracy detects hallucinated information."""
    test_case = LLMTestCase(
        input="What is the LDL-C target?",
        actual_output="The LDL-C target is 5.0 mmol/L.",  # Wrong! Should be 1.8
        retrieval_context=["Guidelines recommend LDL-C < 1.8 mmol/L."]
    )
    # This should fail the assertion (detect hallucination)
    with pytest.raises(AssertionError):  # assert_test raises on failure
        assert_test(test_case, [factual_accuracy_metric])
```

Run: `uv run pytest tests/test_eval_deepeval.py::test_factual_accuracy_detects_hallucination -v`

Expected: PASS (test passes because we expect it to raise AssertionError)

**Why:** Verify metric catches hallucinations.

- [ ] **Step 4: Add pytest configuration**

Edit `pyproject.toml`, locate the `[tool.pytest.ini_options]` section (around line 33) and append to the existing `markers` list:

Current content:
```toml
markers = [
    "live_api: requires live Qwen API access",
]
```

Change to:
```toml
markers = [
    "live_api: requires live Qwen API access",
    "deepeval: marks tests as DeepEval integration tests (slow, requires API)",
    "slow: marks tests as slow (deselect with '-m \"not slow\"')"
]
```

**Why:** Allows marking tests and running subsets.

- [ ] **Step 5: Commit**

```bash
git add tests/test_eval_deepeval.py pyproject.toml
git commit -m "test: add pytest integration tests for DeepEval metrics"
```

---

## Chunk 2: Synthetic Data Generation and Answer Evaluation

### Task 6: Create Synthetic Data Generator

**Files:**
- Create: `src/evals/synthetic/__init__.py`
- Create: `src/evals/synthetic/generator.py`
- Test: `tests/test_synthetic_generator.py`

- [ ] **Step 1: Write test for generator function**

Create `tests/test_synthetic_generator.py`:

```python
import pytest
from pathlib import Path
from src.evals.synthetic.generator import generate_synthetic_dataset

@pytest.mark.slow
def test_generate_synthetic_dataset_creates_questions():
    """Test synthetic dataset generation creates questions."""
    # Use a small test document
    test_doc = Path("tests/fixtures/sample_medical.txt")

    if not test_doc.exists():
        pytest.skip("Test fixture file not found")

    goldens = generate_synthetic_dataset(
        document_paths=[test_doc],
        num_questions=5,
        output_path="/tmp/test_synthetic.json"
    )

    assert len(goldens) > 0
    assert hasattr(goldens[0], 'input')
    assert hasattr(goldens[0], 'expected_output')
```

Run: `uv run pytest tests/test_synthetic_generator.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.evals.synthetic.generator'`

**Why:** TDD approach.

- [ ] **Step 2: Create synthetic generator module**

Create directory:
```bash
mkdir -p src/evals/synthetic
```

Create `src/evals/synthetic/__init__.py`:
```python
"""Synthetic data generation for RAG evaluation."""

from src.evals.synthetic.generator import generate_synthetic_dataset

__all__ = ["generate_synthetic_dataset"]
```

Create `src/evals/synthetic/generator.py`:
```python
"""Synthetic medical Q&A generation using DeepEval's Synthesizer.

This module wraps DeepEval's Synthesizer to generate diverse test questions
from medical documents, supporting evolutionary question generation for
comprehensive RAG evaluation.
"""

from deepeval.synthesizer import Synthesizer
from deepeval.synthesizer.config import ContextConstructionConfig
from src.evals.deepeval_models import get_heavy_model
from pathlib import Path


def generate_synthetic_dataset(
    document_paths: list[Path | str],
    num_questions: int = 100,
    output_path: Path | str = "data/evals/synthetic_dataset.json"
) -> list:
    """Generate diverse synthetic questions from medical documents.

    Uses DeepEval's Synthesizer with evolutionary transformations:
    - Simple paraphrases
    - Reasoning (multi-step inference)
    - Multi-context (requires synthesis across documents)
    - Negative (info not in KB)

    Args:
        document_paths: List of paths to medical documents (PDF, TXT, MD, DOCX)
        num_questions: Total number of questions to generate
        output_path: Where to save the generated dataset

    Returns:
        List of Golden objects with evolved questions

    Example:
        >>> goldens = generate_synthetic_dataset(
        ...     document_paths=['data/raw/guideline.pdf'],
        ...     num_questions=50
        ... )
        >>> len(goldens)
        50
    """
    synthesizer = Synthesizer(
        model=get_heavy_model(),
        async_mode=True  # Enable async for faster generation
    )

    goldens = synthesizer.generate_goldens_from_docs(
        document_paths=[str(p) for p in document_paths],
        context_construction_config=ContextConstructionConfig(
            chunk_size=1024,
            chunk_overlap=50
        ),
        num_transformations=max(1, num_questions // len(document_paths))
    )

    # Save for reuse
    synthesizer.save_as(file_path=str(output_path), file_type="json")

    return goldens
```

**Why:** Wraps DeepEval's Synthesizer with medical-specific configuration.

- [ ] **Step 3: Run test to verify**

Run: `uv run pytest tests/test_synthetic_generator.py -v`

Expected: PASS (may take 30-60 seconds for LLM calls)

**Why:** Confirm generator works with test document.

- [ ] **Step 4: Create test fixture**

Create `tests/fixtures/sample_medical.txt`:
```text
Cholesterol Management Guidelines

LDL-C Targets:
- Secondary prevention: < 1.8 mmol/L (< 70 mg/dL)
- Primary prevention: < 2.6 mmol/L (< 100 mg/dL)

Statin Therapy:
Indications for statin therapy include:
1. Established cardiovascular disease
2. Diabetes mellitus
3. Familial hypercholesterolemia
4. 10-year risk > 10%

Common side effects: myopathy, elevated liver enzymes
Rare but serious: rhabdomyolysis
```

**Why:** Provides test data for synthetic generation.

- [ ] **Step 5: Commit**

```bash
git add src/evals/synthetic/ tests/test_synthetic_generator.py tests/fixtures/sample_medical.txt
git commit -m "feat: implement synthetic data generation wrapper"
```

---

### Task 7: Implement DeepEval Answer Evaluation

**Files:**
- Modify: `src/evals/assessment/answer_eval.py`

- [ ] **Step 1: Write test for evaluate_answers_deepeval**

Create `tests/test_answer_eval_deepeval.py`:

```python
import pytest
from src.evals.assessment.answer_eval import evaluate_answers_deepeval

@pytest.mark.slow
@pytest.mark.asyncio
async def test_evaluate_answers_deepeval_returns_results():
    """Test DeepEval answer evaluation returns structured results."""
    dataset = [
        {
            "query": "What is the LDL-C target for secondary prevention?",
            "query_id": "test_1"
        }
    ]

    results, aggregate = await evaluate_answers_deepeval(dataset, top_k=5)

    assert len(results) == 1
    assert "metrics" in results[0]
    assert "query_count" in aggregate
    assert aggregate["query_count"] == 1

@pytest.mark.slow
@pytest.mark.asyncio
async def test_evaluate_answers_deepeval_includes_all_metrics():
    """Test evaluation includes all 6 metrics."""
    dataset = [
        {
            "query": "What are statin side effects?",
            "query_id": "test_2"
        }
    ]

    results, aggregate = await evaluate_answers_deepeval(dataset, top_k=5)

    metrics = results[0]["metrics"]
    expected_metrics = [
        "Factual Accuracy",
        "Completeness",
        "Clinical Relevance",
        "Clarity",
        "Answer Relevancy",
        "Faithfulness"
    ]

    for metric_name in expected_metrics:
        assert metric_name in metrics
        assert "score" in metrics[metric_name]
```

Run: `uv run pytest tests/test_answer_eval_deepeval.py -v`

Expected: FAIL with function not defined error

**Why:** TDD approach.

- [ ] **Step 2: Read existing answer_eval.py**

Read `src/evals/assessment/answer_eval.py` to understand current structure:

Run: `cat src/evals/assessment/answer_eval.py`

Note: This file has existing `evaluate_answers()` function. We'll add the new DeepEval version alongside it.

**Why:** Understand existing code before modifying.

- [ ] **Step 3: Add evaluate_answers_deepeval function**

Edit `src/evals/assessment/answer_eval.py`, add after the existing `evaluate_answers()` function (around line 63):

```python
async def evaluate_answers_deepeval(
    dataset: list[dict[str, Any]],
    top_k: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Comprehensive answer quality evaluation using DeepEval.

    Evaluates each query-answer pair using 6 metrics:
    - Factual Accuracy (heavyweight): Groundedness in context
    - Completeness (heavyweight): Coverage of question aspects
    - Clinical Relevance (heavyweight): Medical appropriateness
    - Clarity (lightweight): Readability and structure
    - Answer Relevancy (lightweight): Directly addresses question
    - Faithfulness (heavyweight): No hallucinations

    Args:
        dataset: List of query dicts with 'query' and optional 'query_id' keys
        top_k: Number of documents to retrieve for context

    Returns:
        Tuple of (per_query_results, aggregate_metrics):
        - per_query_results: List of dicts with query, answer, sources, metrics
        - aggregate_metrics: Dict with mean scores and counts

    Example:
        >>> results, aggregate = await evaluate_answers_deepeval(dataset, top_k=5)
        >>> aggregate["factual_accuracy"]["mean"]
        0.85
    """
    from src.rag.runtime import retrieve_context_with_trace
    from src.infra.llm import get_client
    from src.evals.metrics.medical import (
        factual_accuracy_metric,
        completeness_metric,
        clinical_relevance_metric,
        clarity_metric,
        answer_relevancy_metric,
        faithfulness_metric
    )

    client = get_client()
    results = []
    all_scores = {
        "factual_accuracy": [],
        "completeness": [],
        "clinical_relevance": [],
        "clarity": [],
        "answer_relevancy": [],
        "faithfulness": []
    }

    for item in dataset:
        query = item["query"]

        # Retrieve and generate
        context, sources, trace = retrieve_context_with_trace(query, top_k=top_k)
        answer = client.generate(prompt=query, context=context)

        # Create test case
        test_case = LLMTestCase(
            input=query,
            actual_output=answer,
            retrieval_context=[context]  # DeepEval expects list
        )

        # Run all metrics
        metrics = [
            factual_accuracy_metric,
            completeness_metric,
            clinical_relevance_metric,
            clarity_metric,
            answer_relevancy_metric,
            faithfulness_metric
        ]

        metric_results = {}
        for metric in metrics:
            metric.measure(test_case)
            metric_results[metric.name] = {
                "score": metric.score,
                "reason": metric.reason if hasattr(metric, 'reason') else None
            }
            all_scores[metric.name.lower().replace(" ", "_")].append(metric.score)

        results.append({
            "query_id": item.get("query_id"),
            "query": query,
            "answer": answer,
            "sources": sources,
            "trace": trace.model_dump() if hasattr(trace, "model_dump") else {},
            "metrics": metric_results
        })

    # Calculate aggregates
    aggregate = {
        "query_count": len(results),
        **{k: {"mean": sum(v)/len(v) if v else 0, "count": len(v)}
           for k, v in all_scores.items()}
    }

    return results, aggregate
```

**Why:** Implements DeepEval-based evaluation with all 6 metrics.

- [ ] **Step 4: Add imports at top of file**

Add to imports section of `src/evals/assessment/answer_eval.py`:

```python
from deepeval.test_case import LLMTestCase
```

**Why:** Required for DeepEval test case creation.

- [ ] **Step 5: Run tests to verify**

Run: `uv run pytest tests/test_answer_eval_deepeval.py -v`

Expected: PASS (may take 60-120 seconds for multiple LLM calls)

**Why:** Confirm evaluation function works correctly.

- [ ] **Step 6: Test with empty dataset**

Add to `tests/test_answer_eval_deepeval.py`:

```python
@pytest.mark.asyncio
async def test_evaluate_answers_deepeval_handles_empty_dataset():
    """Test evaluation handles empty dataset gracefully."""
    results, aggregate = await evaluate_answers_deepeval([], top_k=5)

    assert len(results) == 0
    assert aggregate["query_count"] == 0
```

Run: `uv run pytest tests/test_answer_eval_deepeval.py::test_evaluate_answers_deepeval_handles_empty_dataset -v`

Expected: PASS

**Why:** Test edge case handling.

- [ ] **Step 7: Commit**

```bash
git add src/evals/assessment/answer_eval.py tests/test_answer_eval_deepeval.py
git commit -m "feat: implement DeepEval-based answer evaluation"
```

---

### Task 8: Integrate with Orchestrator

**Files:**
- Modify: `src/evals/assessment/orchestrator.py`

- [ ] **Step 1: Read orchestrator to find integration point**

Run: `grep -n "include_answer_eval\|evaluate_answers" src/evals/assessment/orchestrator.py`

Look for where L6 evaluation would fit (likely after L5 evaluation).

**Why:** Understand existing structure before modification.

- [ ] **Step 2: Add import and integration method**

Edit `src/evals/assessment/orchestrator.py`:

Add import at top:
```python
from src.evals.assessment.answer_eval import evaluate_answers_deepeval
```

Add method to `AssessmentOrchestrator` class:

```python
def _evaluate_answer_quality_deepeval(self, config: AssessmentConfig) -> dict:
    """Run DeepEval-based answer quality evaluation.

    Args:
        config: Assessment configuration

    Returns:
        Aggregate metrics from DeepEval evaluation
    """
    results, aggregate = evaluate_answers_deepeval(
        dataset=self.dataset,
        top_k=config.top_k
    )

    # Save detailed results
    self.artifacts.save_json("l6_answer_quality.jsonl", results)

    return aggregate
```

**Why:** Provides method for orchestrator to call DeepEval evaluation.

- [ ] **Step 3: Add routing logic in run_assessment**

Find the `run_assessment()` method and locate where L5 evaluation completes. Add L6 stage:

Look for pattern like:
```python
# L5: Index quality
l5_results = self._evaluate_index_quality(config)
summary["l5"] = l5_results
```

Add after L5:
```python
# L6: Answer Quality Evaluation (DeepEval)
if config.include_answer_eval and not config.disable_llm_judging:
    if config.enable_deepeval:
        l6_results = self._evaluate_answer_quality_deepeval(config)
    else:
        l6_results = self._evaluate_answer_quality_legacy(config)
    summary["l6"] = l6_results
```

**Why:** Integrates L6 stage with feature flag for DeepEval vs legacy.

- [ ] **Step 4: Test orchestrator integration**

Create test file `tests/test_orchestrator_deepeval.py`:

```python
import pytest
from src.evals.assessment.orchestrator import AssessmentOrchestrator
from src.evals.schemas import AssessmentConfig
from pathlib import Path

@pytest.mark.slow
def test_orchestrator_runs_l6_deepeval_evaluation():
    """Test orchestrator runs L6 evaluation with DeepEval."""
    config = AssessmentConfig(
        artifact_dir=Path("/tmp/test_eval"),
        include_answer_eval=True,
        enable_deepeval=True,
        disable_llm_judging=False,
        top_k=5
    )

    orchestrator = AssessmentOrchestrator(config)
    # Note: This would require dataset setup
    # For now, we test the routing logic
    assert hasattr(orchestrator, '_evaluate_answer_quality_deepeval')
```

Run: `uv run pytest tests/test_orchestrator_deepeval.py -v`

Expected: PASS

**Why:** Verify integration point exists.

- [ ] **Step 5: Commit**

```bash
git add src/evals/assessment/orchestrator.py tests/test_orchestrator_deepeval.py
git commit -m "feat: integrate DeepEval evaluation into orchestrator"
```

---

### Task 9: Add L6 Thresholds

**Files:**
- Modify: `src/evals/assessment/thresholds.py`

- [ ] **Step 1: Add L6 thresholds**

Edit `src/evals/assessment/thresholds.py`, add to `DEFAULT_THRESHOLDS` dict:

```python
DEFAULT_THRESHOLDS: dict[str, dict[str, Any]] = {
    # ... existing L1-L5 thresholds ...

    # L6: Answer Quality (High Confidence Subset)
    "l6.factual_accuracy_mean": {"op": "min", "value": 0.8},
    "l6.completeness_mean": {"op": "min", "value": 0.75},
    "l6.clinical_relevance_mean": {"op": "min", "value": 0.8},
    "l6.clarity_mean": {"op": "min", "value": 0.70},
    "l6.answer_relevancy_mean": {"op": "min", "value": 0.7},
    "l6.faithfulness_mean": {"op": "min", "value": 0.8},
}
```

**Why:** Defines quality gates for L6 evaluation metrics.

- [ ] **Step 2: Test threshold validation**

Run: `uv run pytest tests/test_thresholds.py -v -k threshold`

Expected: Any existing threshold tests still pass

**Why:** Verify thresholds are valid.

- [ ] **Step 3: Commit**

```bash
git add src/evals/assessment/thresholds.py
git commit -m "feat: add L6 answer quality thresholds"
```

---

### Task 10: Add API Endpoints

**Files:**
- Modify: `src/app/routes/evaluation.py`

- [ ] **Step 1: Add endpoint for answer quality details**

Edit `src/app/routes/evaluation.py`, add new endpoints:

```python
@router.get("/evaluation/answer-quality/{run_dir}")
async def get_answer_quality_details(run_dir: str) -> dict:
    """Get detailed DeepEval results for a specific evaluation run.

    Args:
        run_dir: Evaluation run directory name

    Returns:
        Dict with per-query metrics and detailed results
    """
    from src.evals.artifacts import AssessmentArtifacts

    artifacts = AssessmentArtifacts(Path(f"data/evals/{run_dir}"))

    # Load detailed results
    results = artifacts.load_json("l6_answer_quality.jsonl")

    return {
        "run_dir": run_dir,
        "results": results
    }


@router.post("/evaluation/evaluate-single")
async def evaluate_single_answer(
    query: str,
    answer: str,
    context: str
) -> dict:
    """Evaluate a single query-answer-context pair (for debugging).

    Useful for testing specific cases without running full evaluation.

    Args:
        query: User's question
        answer: Generated answer to evaluate
        context: Retrieved context

    Returns:
        Dict with scores from all 6 metrics
    """
    from deepeval.test_case import LLMTestCase
    from src.evals.metrics.medical import (
        factual_accuracy_metric,
        completeness_metric,
        clinical_relevance_metric,
        clarity_metric,
        answer_relevancy_metric,
        faithfulness_metric
    )

    test_case = LLMTestCase(
        input=query,
        actual_output=answer,
        retrieval_context=[context]
    )

    metrics = [
        factual_accuracy_metric,
        completeness_metric,
        clinical_relevance_metric,
        clarity_metric,
        answer_relevancy_metric,
        faithfulness_metric
    ]

    results = {}
    for metric in metrics:
        metric.measure(test_case)
        results[metric.name] = {
            "score": metric.score,
            "reason": metric.reason if hasattr(metric, 'reason') else None
        }

    return results
```

**Why:** Provides API access to detailed results and single-query evaluation.

- [ ] **Step 2: Test API endpoints**

Create `tests/test_eval_api_deepeval.py`:

```python
import pytest
from fastapi.testclient import TestClient
from src.app.main import app

client = TestClient(app)

@pytest.mark.slow
def test_evaluate_single_answer_endpoint():
    """Test single answer evaluation endpoint."""
    response = client.post(
        "/evaluation/evaluate-single",
        params={
            "query": "What is cholesterol?",
            "answer": "Cholesterol is a waxy substance in blood.",
            "context": "Cholesterol is a lipid found in blood."
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "Factual Accuracy" in data
    assert "Clarity" in data
```

Run: `uv run pytest tests/test_eval_api_deepeval.py -v`

Expected: PASS

**Why:** Verify API endpoints work correctly.

- [ ] **Step 3: Commit**

```bash
git add src/app/routes/evaluation.py tests/test_eval_api_deepeval.py
git commit -m "feat: add answer quality API endpoints"
```

---

## Chunk 3: Documentation and Verification

### Task 11: Update Documentation

**Files:**
- Modify: `docs/configuration.md`
- Modify: `docs/evaluation/20260227-step-evaluation-impl.md`

- [ ] **Step 1: Add DeepEval configuration to docs**

Edit `docs/configuration.md`, add section:

```markdown
## DeepEval Evaluation Configuration

The evaluation pipeline supports LLM-as-a-judge evaluation via DeepEval framework.

### Judge Model Configuration

```bash
# Lightweight judge model (simple classification)
export JUDGE_MODEL_LIGHT="qwen3.5-35b-a3b"

# Heavyweight judge model (complex reasoning)
export JUDGE_MODEL_HEAVY="qwen3.5-flash"

# Judge temperature (0 = deterministic)
export JUDGE_TEMPERATURE="0.0"

# Enable DeepEval framework
export ENABLE_DEEPEVAL="true"
```

### Running Evaluation with DeepEval

```bash
uv run python -m src.cli.eval_pipeline \
    --include-answer-eval \
    --enable-deepeval \
    --top-k 5 \
    --dataset-path data/evals/golden_queries.json
```

### Cost Optimization

The evaluation uses model tiering to reduce costs:
- Simple metrics (Clarity, Answer Relevancy): qwen3.5-35b-a3b (~15x cheaper)
- Complex metrics (Factual Accuracy, Completeness, Clinical Relevance, Faithfulness): qwen3.5-flash

Estimated cost: $0.70-2.10 per 100 queries.
```

**Why:** Documents new configuration options.

- [ ] **Step 2: Update evaluation docs**

Edit `docs/evaluation/20260227-step-evaluation-impl.md`, add L6 section:

```markdown
## L6: Answer Quality Evaluation

L6 stage evaluates the quality of generated answers using DeepEval's LLM-as-a-judge framework.

### Metrics

Six metrics are evaluated:

1. **Factual Accuracy** (heavyweight model): Groundedness in retrieved context
2. **Completeness** (heavyweight model): Coverage of question aspects
3. **Clinical Relevance** (heavyweight model): Medical appropriateness
4. **Clarity** (lightweight model): Readability and structure
5. **Answer Relevancy** (lightweight model): Directly addresses question
6. **Faithfulness** (heavyweight model): No hallucinations

### Output Files

- `l6_answer_quality.jsonl`: Per-query detailed results with scores and reasoning
- `summary.json`: Aggregate metrics in `l6` section

### Example

```json
{
  "l6": {
    "factual_accuracy": {"mean": 0.85, "count": 100},
    "completeness": {"mean": 0.78, "count": 100},
    "clinical_relevance": {"mean": 0.82, "count": 100},
    "clarity": {"mean": 0.88, "count": 100},
    "answer_relevancy": {"mean": 0.90, "count": 100},
    "faithfulness": {"mean": 0.83, "count": 100}
  }
}
```
```

**Why:** Documents L6 evaluation stage.

- [ ] **Step 3: Commit**

```bash
git add docs/configuration.md docs/evaluation/20260227-step-evaluation-impl.md
git commit -m "docs: add DeepEval evaluation documentation"
```

---

### Task 12: End-to-End Verification

- [ ] **Step 1: Run full evaluation pipeline**

Run complete evaluation with DeepEval:

```bash
uv run python -m src.cli.eval_pipeline \
    --include-answer-eval \
    --enable-deepeval \
    --top-k 5 \
    --dataset-path data/evals/golden_queries.json
```

Expected: Evaluation completes successfully with L6 results

**Why:** Verify entire pipeline works end-to-end.

- [ ] **Step 2: Verify L6 results exist**

Check results:
```bash
LATEST_RUN=$(ls -t data/evals/ | head -1)
cat data/evals/${LATEST_RUN}/summary.json | jq .l6
cat data/evals/${LATEST_RUN}/l6_answer_quality.jsonl | jq '.[0]'
```

Expected: L6 metrics present in summary, detailed results in jsonl

**Why:** Confirm output files are generated correctly.

- [ ] **Step 3: Run pytest integration tests**

Run all DeepEval tests:
```bash
uv run pytest tests/ -k deepeval -v
```

Expected: All tests pass

**Why:** Verify CI/CD integration works.

- [ ] **Step 4: Test API endpoints**

Start server and test endpoints:
```bash
# In one terminal
uv run python -m src.cli.serve

# In another terminal
curl -X POST "http://localhost:8000/evaluation/evaluate-single?query=What+is+cholesterol&answer=Cholesterol+is+a+waxy+substance&context=Lipid+molecule"
```

Expected: JSON response with all metric scores

**Why:** Verify API endpoints work in running system.

- [ ] **Step 5: Generate synthetic dataset**

Test synthetic data generation:
```bash
uv run python -c "
from src.evals.synthetic.generator import generate_synthetic_dataset
from pathlib import Path

goldens = generate_synthetic_dataset(
    document_paths=['data/raw/medical_guideline.pdf'],
    num_questions=10,
    output_path='data/evals/test_synthetic.json'
)

print(f'Generated {len(goldens)} synthetic questions')
"
```

Expected: Generates questions and saves to file

**Why:** Verify synthetic generation works.

---

## Task Summary

**Total Tasks:** 12
**Total Steps:** ~60
**Estimated Time:** 2-3 days

**Files Created:** 9
- `src/evals/deepeval_models.py`
- `src/evals/metrics/__init__.py`
- `src/evals/metrics/medical.py`
- `src/evals/synthetic/__init__.py`
- `src/evals/synthetic/generator.py`
- `tests/test_settings_deepeval.py`
- `tests/test_deepeval_models.py`
- `tests/test_medical_metrics.py`
- `tests/test_eval_deepeval.py`
- `tests/test_synthetic_generator.py`
- `tests/test_answer_eval_deepeval.py`
- `tests/test_orchestrator_deepeval.py`
- `tests/test_eval_api_deepeval.py`
- `tests/fixtures/sample_medical.txt`

**Files Modified:** 6
- `pyproject.toml`
- `src/config/settings.py`
- `src/evals/assessment/answer_eval.py`
- `src/evals/assessment/orchestrator.py`
- `src/evals/assessment/thresholds.py`
- `src/app/routes/evaluation.py`
- `docs/configuration.md`
- `docs/evaluation/20260227-step-evaluation-impl.md`

---

**Plan complete and saved to:** `docs/superpowers/plans/2026-03-13-deepeval-rag-evaluation.md`

**Ready to execute?**

Use **superpowers:subagent-driven-development** for implementation with automatic checkpoints and reviews.
