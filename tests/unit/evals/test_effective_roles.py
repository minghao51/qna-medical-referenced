"""Tests for the non-secret effective role snapshot."""

import pytest
from pydantic import SecretStr

from src.config import settings
from src.evals.deepeval_models import effective_roles


def _set_credentials(monkeypatch, *, qwen: str = "", gemini: str = "", litellm_key: str = ""):
    monkeypatch.setattr(settings.llm, "dashscope_api_key", SecretStr(qwen))
    monkeypatch.setattr(settings.llm, "gemini_api_key", SecretStr(gemini))
    monkeypatch.setattr(settings.llm, "openrouter_api_key", SecretStr(litellm_key))


def test_effective_roles_reports_independent_generator_and_judge_settings(monkeypatch):
    qwen_secret = "qwen-secret-canary"
    gemini_secret = "gemini-secret-canary"
    _set_credentials(monkeypatch, qwen=qwen_secret, gemini=gemini_secret)
    monkeypatch.setattr(settings.llm, "provider", "gemini")
    monkeypatch.setattr(settings.llm, "judge_provider", "qwen")
    monkeypatch.setattr(settings.llm, "gemini_model_name", "models/gemini-3-flash-preview")
    monkeypatch.setattr(settings.llm, "judge_temperature", 0.25)
    monkeypatch.setattr(settings.llm, "judge_max_tokens", 456)

    roles = effective_roles(task="answer_eval")

    assert roles["implementation"] == "existing"
    assert roles["harness"] == "deterministic_rag"
    assert roles["generator"]["provider"] == "gemini"
    assert roles["generator"]["model"] == "models/gemini-3-flash-preview"
    assert roles["generator"]["endpoint"] == "google-genai"
    assert roles["generator"]["temperature"] == 0.7
    assert roles["generator"]["max_tokens"] == 2048
    assert roles["judge"]["provider"] == "qwen"
    assert roles["judge"]["temperature"] == 0.25
    assert roles["judge"]["max_tokens"] == 456
    assert roles["judge"]["max_tokens_parameter"] == "max_tokens"
    assert roles["judge"]["request_attempts"] == 1
    assert roles["judge"]["sdk_retries"] == 0
    assert roles["judge"]["rubric"]["source"] == "src.evals.metrics.medical.METRIC_SPECS"
    assert roles["judge"]["rubric"]["metric_keys"] == [
        "factual_accuracy",
        "completeness",
        "clinical_relevance",
        "clarity",
        "answer_relevancy",
        "faithfulness",
    ]
    assert roles["embedder"]["provider"] == "qwen"
    assert roles["enrichment"] == {"status": "not_required"}
    assert effective_roles(task="index_build")["enrichment"]["provider"] == "qwen"
    serialized = repr(roles)
    assert qwen_secret not in serialized
    assert gemini_secret not in serialized


def test_judge_task_requires_only_the_independently_selected_judge(monkeypatch):
    judge_secret = "selected-gemini-secret"
    _set_credentials(monkeypatch, gemini=judge_secret)
    monkeypatch.setattr(settings.llm, "provider", "qwen")
    monkeypatch.setattr(settings.llm, "judge_provider", "gemini")

    roles = effective_roles(task="judge")

    assert roles["generator"] == {"status": "not_required"}
    assert roles["embedder"] == {"status": "not_required"}
    assert roles["judge"]["provider"] == "gemini"
    assert roles["judge"]["credential"]["required"] is True
    assert roles["required_credentials"] == []
    assert "deepeval" in roles["required_dependencies"]
    assert judge_secret not in repr(roles)


def test_generation_task_reports_explicit_provider_and_model_selection(monkeypatch):
    _set_credentials(monkeypatch, gemini="selected-generator-secret")
    monkeypatch.setattr(settings.llm, "provider", "qwen")

    roles = effective_roles(
        task="generation",
        generator_provider="gemini",
        generator_model="models/gemini-explicit",
    )

    assert roles["generator"]["provider"] == "gemini"
    assert roles["generator"]["model"] == "models/gemini-explicit"
    assert roles["generator"]["endpoint"] == "google-genai"
    assert roles["generator"]["credential"]["setting"] == "APP__LLM__GEMINI_API_KEY"


def test_generation_task_does_not_validate_or_require_unused_judge(monkeypatch):
    _set_credentials(monkeypatch, gemini="generator-secret")
    monkeypatch.setattr(settings.llm, "provider", "gemini")
    monkeypatch.setattr(settings.llm, "judge_provider", "unsupported-unused-provider")

    roles = effective_roles(task="generation")

    assert roles["generator"]["provider"] == "gemini"
    assert roles["judge"] == {"status": "not_required"}
    assert roles["required_credentials"] == []
    assert roles["required_dependencies"] == []


def test_retrieval_task_requires_its_qwen_embedder_even_for_gemini_generation(monkeypatch):
    _set_credentials(monkeypatch, gemini="unused-generator-secret")
    monkeypatch.setattr(settings.llm, "provider", "gemini")

    roles = effective_roles(task="retrieval")

    assert roles["generator"] == {"status": "not_required"}
    assert roles["judge"] == {"status": "not_required"}
    assert roles["embedder"]["provider"] == "qwen"
    assert roles["embedder"]["dimensions"] == 768
    assert roles["required_credentials"] == ["APP__LLM__DASHSCOPE_API_KEY"]
    assert roles["missing_dependencies"] == []


def test_answer_eval_requires_embedding_credential_separately_from_generator_and_judge(
    monkeypatch,
):
    _set_credentials(monkeypatch, gemini="gemini-secret")
    monkeypatch.setattr(settings.llm, "provider", "gemini")
    monkeypatch.setattr(settings.llm, "judge_provider", "gemini")

    roles = effective_roles(task="answer_eval")

    assert roles["generator"]["credential"]["configured"] is True
    assert roles["judge"]["credential"]["configured"] is True
    assert roles["embedder"]["credential"]["configured"] is False
    assert roles["required_credentials"] == ["APP__LLM__DASHSCOPE_API_KEY"]


def test_index_build_reports_qwen_enrichment_as_separate_enabled_role(monkeypatch):
    _set_credentials(monkeypatch)
    monkeypatch.setattr(settings.llm, "provider", "gemini")
    monkeypatch.setattr(settings.llm, "model_name", "qwen-enrichment-model")
    from src.config.context import get_runtime_state

    monkeypatch.setattr(
        get_runtime_state(),
        "indexing_features",
        {
            "enable_hype": True,
            "hype_sample_rate": 0.4,
            "hype_max_chunks": 12,
            "hype_questions_per_chunk": 3,
            "enable_keyword_extraction": True,
            "enable_chunk_summaries": False,
            "keyword_extraction_sample_rate": 0.6,
            "keyword_extraction_max_chunks": 14,
        },
    )

    roles = effective_roles(task="index_build")

    assert roles["generator"] == {"status": "not_required"}
    assert roles["enrichment"]["provider"] == "qwen"
    assert roles["enrichment"]["model"] == "qwen-enrichment-model"
    assert roles["enrichment"]["enabled"] is True
    assert roles["enrichment"]["hype_enabled"] is True
    assert roles["enrichment"]["keyword_extraction_enabled"] is True
    assert roles["enrichment"]["hype_sample_rate"] == 0.4
    assert roles["enrichment"]["hype_max_chunks"] == 12
    assert roles["enrichment"]["hype_questions_per_chunk"] == 3
    assert roles["enrichment"]["keyword_extraction_sample_rate"] == 0.6
    assert roles["enrichment"]["keyword_extraction_max_chunks"] == 14
    assert roles["required_credentials"] == ["APP__LLM__DASHSCOPE_API_KEY"]


@pytest.mark.parametrize(
    ("setting_name", "value"),
    [("judge_temperature", -0.1), ("judge_max_tokens", 0)],
)
def test_effective_roles_rejects_unsupported_judge_request_settings(
    monkeypatch, setting_name, value
):
    monkeypatch.setattr(settings.llm, setting_name, value)

    with pytest.raises(ValueError, match="Judge"):
        effective_roles(task="judge")


def test_effective_roles_rejects_nonpositive_judge_timeout(monkeypatch):
    monkeypatch.setattr(settings.deepeval, "deepeval_metric_timeout_seconds", 0)

    with pytest.raises(ValueError, match="Judge timeout"):
        effective_roles(task="judge")


def test_effective_roles_rejects_unknown_qwen_endpoint_without_echoing_it(monkeypatch):
    canary_url = "https://user:secret@untrusted.invalid/compatible-mode/v1?token=url-canary"
    monkeypatch.setattr(settings.llm, "qwen_base_url", canary_url)

    with pytest.raises(ValueError, match="not a supported DashScope route") as exc_info:
        effective_roles(task="retrieval")

    assert "secret" not in str(exc_info.value)
    assert "url-canary" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"implementation": "pydantic_ai"}, "implementation"),
        ({"harness": "agentic"}, "harness"),
        ({"task": "unsupported"}, "task"),
        (
            {"task": "answer_eval", "generator_provider": "gemini"},
            "generator override",
        ),
    ],
)
def test_effective_roles_rejects_unimplemented_axes(kwargs, message):
    with pytest.raises(ValueError, match=f"Unsupported.*{message}"):
        effective_roles(**kwargs)
