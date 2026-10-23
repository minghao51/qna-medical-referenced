"""DeepEval-compatible judge wrappers for the existing provider routes.

Judge-provider selection is independent of generation when configured, while
``judge_provider=None`` preserves the legacy generation-provider behavior.
"""

from __future__ import annotations

import asyncio
import importlib.util
import math
import os
import re
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlsplit

import httpx
from openai import DEFAULT_MAX_RETRIES, AsyncOpenAI, OpenAI

from src.config.settings import settings
from src.infra.usage import usage_call

try:
    from deepeval.models import DeepEvalBaseLLM
except ModuleNotFoundError:

    class DeepEvalBaseLLM:  # type: ignore[no-redef]
        """Fallback base class when the optional deepeval extra is absent."""


if "DEEPEVAL_TELEMETRY_OPT_OUT" not in os.environ:
    os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"

if TYPE_CHECKING:
    from src.evals.pydantic_ai_judge import PydanticAIJudgeModel

JudgeProvider = Literal["qwen", "gemini", "litellm", "pydantic-ai"]

_SUPPORTED_PROVIDERS = ("qwen", "gemini", "litellm", "pydantic-ai")
_SUPPORTED_TASKS = ("generation", "judge", "retrieval", "answer_eval", "index_build")
_MODEL_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,199}\Z")
_GENERATION_TIMEOUT_SECONDS = 30.0
_GENERATION_TEMPERATURE = 0.7
_GENERATION_MAX_TOKENS = 2048
_EMBEDDING_TIMEOUT_SECONDS = 30.0
_EMBEDDING_DIMENSIONS = 768
_MEDICAL_RUBRIC_SOURCE = "src.evals.metrics.medical.METRIC_SPECS"
_MEDICAL_RUBRIC_METRICS = (
    "factual_accuracy",
    "completeness",
    "clinical_relevance",
    "clarity",
    "answer_relevancy",
    "faithfulness",
)


def _judge_parameters() -> tuple[float, int, float]:
    temperature = settings.llm.judge_temperature
    max_tokens = settings.llm.judge_max_tokens
    timeout_seconds = settings.deepeval.deepeval_metric_timeout_seconds
    if (
        isinstance(temperature, bool)
        or not isinstance(temperature, (int, float))
        or not math.isfinite(temperature)
        or not 0 <= temperature <= 2
    ):
        raise ValueError("Judge temperature must be a finite value from 0 through 2.")
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise ValueError("Judge max tokens must be a positive integer.")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("Judge timeout must be a finite positive number of seconds.")
    return float(temperature), max_tokens, float(timeout_seconds)


def _safe_model_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or "://" in value
        or "@" in value
        or not _MODEL_ID_PATTERN.fullmatch(value)
    ):
        raise ValueError("Configured model identifier is not a safe supported model name.")
    return value


def _safe_qwen_endpoint() -> str:
    """Return only the two known DashScope routes, never arbitrary URL components."""
    try:
        parsed = urlsplit(settings.llm.qwen_base_url)
        host = (parsed.hostname or "").lower()
        path = parsed.path
        if (
            parsed.scheme == "https"
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and "?" not in settings.llm.qwen_base_url
            and "#" not in settings.llm.qwen_base_url
            and path in {"/compatible-mode/v1", "/compatible-mode/v1/"}
            and host in {"dashscope-us.aliyuncs.com", "dashscope-intl.aliyuncs.com"}
        ):
            return f"https://{host}/compatible-mode/v1"
    except ValueError:
        pass
    raise ValueError("Configured Qwen endpoint is not a supported DashScope route.")


def _credential(provider: JudgeProvider) -> tuple[str, bool]:
    if provider == "qwen":
        setting_name, value = "APP__LLM__DASHSCOPE_API_KEY", settings.llm.dashscope_api_key
    elif provider == "gemini":
        setting_name, value = "APP__LLM__GEMINI_API_KEY", settings.llm.gemini_api_key
    elif provider == "pydantic-ai":
        setting_name, value = "APP__LLM__PYDANTIC_AI_API_KEY", settings.llm.pydantic_ai_api_key
    else:
        setting_name, value = "APP__LLM__OPENROUTER_API_KEY", settings.llm.openrouter_api_key
    return setting_name, bool(value.get_secret_value().strip())


def _judge_model_name(provider: JudgeProvider, tier: str) -> str:
    if provider == "qwen":
        model_name = getattr(settings.llm, f"judge_model_{tier}")
    else:
        suffix = "pydantic_ai" if provider == "pydantic-ai" else provider
        model_name = getattr(settings.llm, f"judge_model_{tier}_{suffix}")
    if provider == "litellm" and not model_name.startswith("openrouter/"):
        model_name = f"openrouter/{model_name}"
    return _safe_model_name(model_name)


def _safe_pydantic_ai_endpoint() -> str:
    """Return the configured OpenCode Go route only when it is a plain HTTPS /v1 URL."""
    try:
        parsed = urlsplit(settings.llm.pydantic_ai_base_url)
        host = (parsed.hostname or "").lower()
        path = parsed.path.rstrip("/")
        if (
            parsed.scheme == "https"
            and host
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and not parsed.query
            and not parsed.fragment
            and path.endswith("/v1")
        ):
            return f"https://{host}{path}"
    except ValueError:
        pass
    raise ValueError("Configured Pydantic AI endpoint is not a supported HTTPS /v1 route.")


def _raise_cleanup_errors(label: str, errors: list[BaseException]) -> None:
    if not errors:
        return
    cancellation = next(
        (error for error in errors if isinstance(error, asyncio.CancelledError)), None
    )
    if cancellation is not None:
        for error in errors:
            if error is not cancellation:
                cancellation.add_note(f"Additional {label} cleanup failure: {type(error).__name__}")
        raise cancellation
    if len(errors) == 1:
        raise errors[0]
    raise BaseExceptionGroup(f"{label} cleanup failed", errors)


class QwenModel(DeepEvalBaseLLM):
    """DeepEval judge wrapper using the OpenAI-compatible DashScope route."""

    def __init__(self, model: str):
        self.usage_role = "judge"
        self.model_name = _safe_model_name(model)
        self.name = self.model_name
        self.model = self
        self.temperature, self.max_tokens, self.timeout_seconds = _judge_parameters()
        _safe_qwen_endpoint()
        api_key = settings.llm.dashscope_api_key.get_secret_value()
        self.client = OpenAI(
            api_key=api_key,
            base_url=settings.llm.qwen_base_url,
            timeout=self.timeout_seconds,
            max_retries=0,
        )
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=settings.llm.qwen_base_url,
            timeout=self.timeout_seconds,
            max_retries=0,
        )

    def load_model(self) -> QwenModel:
        return self

    def generate(self, prompt: str) -> str:
        with usage_call(role=self.usage_role, provider="openai") as usage:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout_seconds,
            )
            if usage is not None:
                usage.record_response(response)
        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return ""

    async def a_generate(self, prompt: str) -> str:
        async with asyncio.timeout(self.timeout_seconds):
            with usage_call(role=self.usage_role, provider="openai") as usage:
                response = await self.async_client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout_seconds,
                )
                if usage is not None:
                    usage.record_response(response)
        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return ""

    def close(self) -> None:
        """Close the sync transport; use ``aclose`` to also close the async one."""
        self.client.close()

    async def aclose(self) -> None:
        """Close the async transport on its owning loop and the sync transport."""
        errors: list[BaseException] = []
        try:
            await self.async_client.close()
        except BaseException as exc:
            errors.append(exc)
        try:
            self.client.close()
        except BaseException as exc:
            errors.append(exc)
        _raise_cleanup_errors("Qwen judge", errors)

    def get_model_name(self) -> str:
        return self.model_name

    def supports_json_mode(self) -> bool:
        return False

    def supports_structured_outputs(self) -> bool:
        return False

    def supports_temperature(self) -> bool:
        return True


class LiteLLMJudgeModel(DeepEvalBaseLLM):
    """DeepEval judge wrapper using the configured LiteLLM route."""

    def __init__(self, model: str):
        self.usage_role = "judge"
        self.model_name = _safe_model_name(model)
        self.name = self.model_name
        self.model = self
        self._api_key = settings.llm.openrouter_api_key.get_secret_value()
        self.temperature, self.max_tokens, self.timeout_seconds = _judge_parameters()

    def load_model(self) -> LiteLLMJudgeModel:
        return self

    @staticmethod
    def _require_bounded_policy(litellm: Any) -> None:
        if litellm.model_fallbacks is not None or litellm.num_retries:
            raise RuntimeError("Global LiteLLM retries/fallbacks are unsupported for judge calls")

    def generate(self, prompt: str) -> str:
        import litellm

        self._require_bounded_policy(litellm)
        with usage_call(role=self.usage_role, provider="litellm") as usage:
            response: Any = litellm.completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout_seconds,
                max_retries=0,
                num_retries=0,
                api_key=self._api_key,
            )
            if usage is not None:
                usage.record_response(response)
        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return ""

    async def a_generate(self, prompt: str) -> str:
        import litellm

        self._require_bounded_policy(litellm)
        async with asyncio.timeout(self.timeout_seconds):
            with usage_call(role=self.usage_role, provider="litellm") as usage:
                response: Any = await litellm.acompletion(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout_seconds,
                    max_retries=0,
                    num_retries=0,
                    api_key=self._api_key,
                )
                if usage is not None:
                    usage.record_response(response)
        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return ""

    def close(self) -> None:
        """LiteLLM sessions are library-global and are not owned by this wrapper."""

    async def aclose(self) -> None:
        """Do not close LiteLLM's shared process-global session."""

    def get_model_name(self) -> str:
        return self.model_name

    def supports_json_mode(self) -> bool:
        return False

    def supports_structured_outputs(self) -> bool:
        return False

    def supports_temperature(self) -> bool:
        return True


class GeminiJudgeModel(DeepEvalBaseLLM):
    """DeepEval judge wrapper using Gemini's public async HTTPX transport."""

    def __init__(self, model: str):
        from google import genai
        from google.genai import types

        self.usage_role = "judge"
        self.model_name = _safe_model_name(model)
        self.name = self.model_name
        self.model = self
        self.temperature, self.max_tokens, self.timeout_seconds = _judge_parameters()
        self._owned_async_http_client = httpx.AsyncClient(follow_redirects=True)
        self.client = genai.Client(
            api_key=settings.llm.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(
                httpx_async_client=self._owned_async_http_client,
                timeout=int(self.timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    def load_model(self) -> GeminiJudgeModel:
        return self

    def generate(self, prompt: str) -> str:
        from google.genai import types

        with usage_call(role=self.usage_role, provider="gemini") as usage:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                    http_options=types.HttpOptions(
                        timeout=int(self.timeout_seconds * 1000),
                        retry_options=types.HttpRetryOptions(attempts=1),
                    ),
                ),
            )
            if usage is not None:
                usage.record_response(response)
        if response.text:
            return str(response.text)
        return ""

    async def a_generate(self, prompt: str) -> str:
        from google.genai import types

        async with asyncio.timeout(self.timeout_seconds):
            with usage_call(role=self.usage_role, provider="gemini") as usage:
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_tokens,
                        http_options=types.HttpOptions(
                            timeout=int(self.timeout_seconds * 1000),
                            retry_options=types.HttpRetryOptions(attempts=1),
                        ),
                    ),
                )
                if usage is not None:
                    usage.record_response(response)
        if response.text:
            return str(response.text)
        return ""

    def close(self) -> None:
        """Close the sync SDK transport; use ``aclose`` for the owned async pool."""
        self.client.close()

    async def aclose(self) -> None:
        """Close SDK and owned HTTPX transports without creating a worker event loop."""
        errors: list[BaseException] = []
        try:
            await self.client.aio.aclose()
        except BaseException as exc:
            errors.append(exc)
        try:
            await self._owned_async_http_client.aclose()
        except BaseException as exc:
            errors.append(exc)
        try:
            self.client.close()
        except BaseException as exc:
            errors.append(exc)
        _raise_cleanup_errors("Gemini judge", errors)

    def get_model_name(self) -> str:
        return self.model_name

    def supports_json_mode(self) -> bool:
        return True

    def supports_structured_outputs(self) -> bool:
        return True

    def supports_temperature(self) -> bool:
        return True


def resolve_judge_provider() -> JudgeProvider:
    """Resolve the selected judge provider, inheriting the generator for legacy config."""
    provider = (
        settings.llm.provider
        if settings.llm.judge_provider is None
        else settings.llm.judge_provider
    )
    if provider == "qwen":
        return "qwen"
    if provider == "gemini":
        return "gemini"
    if provider == "litellm":
        return "litellm"
    if provider == "pydantic-ai":
        return "pydantic-ai"
    raise ValueError(
        "Unsupported judge provider; supported providers are qwen, gemini, litellm, and "
        "pydantic-ai."
    )


def _require_judge_credential(provider: JudgeProvider) -> None:
    setting_name, configured = _credential(provider)
    if not configured:
        raise ValueError(f"Missing credential for judge provider '{provider}'; set {setting_name}.")


def get_light_model() -> QwenModel | LiteLLMJudgeModel | GeminiJudgeModel | PydanticAIJudgeModel:
    provider = resolve_judge_provider()
    _require_judge_credential(provider)
    model_name = _judge_model_name(provider, "light")
    model: QwenModel | LiteLLMJudgeModel | GeminiJudgeModel | PydanticAIJudgeModel
    if provider == "litellm":
        model = LiteLLMJudgeModel(model_name)
    elif provider == "gemini":
        model = GeminiJudgeModel(model_name)
    elif provider == "pydantic-ai":
        from src.evals.pydantic_ai_judge import PydanticAIJudgeModel

        model = PydanticAIJudgeModel(model_name)
    else:
        model = QwenModel(model_name)
    model.usage_role = "judge_light"
    return model


def get_heavy_model() -> QwenModel | LiteLLMJudgeModel | GeminiJudgeModel | PydanticAIJudgeModel:
    provider = resolve_judge_provider()
    _require_judge_credential(provider)
    model_name = _judge_model_name(provider, "heavy")
    model: QwenModel | LiteLLMJudgeModel | GeminiJudgeModel | PydanticAIJudgeModel
    if provider == "litellm":
        model = LiteLLMJudgeModel(model_name)
    elif provider == "gemini":
        model = GeminiJudgeModel(model_name)
    elif provider == "pydantic-ai":
        from src.evals.pydantic_ai_judge import PydanticAIJudgeModel

        model = PydanticAIJudgeModel(model_name)
    else:
        model = QwenModel(model_name)
    model.usage_role = "judge_heavy"
    return model


def _generation_details(
    provider_override: str | None = None, model_override: str | None = None
) -> tuple[Literal["qwen", "gemini", "litellm"], str, str]:
    provider = settings.llm.provider if provider_override is None else provider_override
    if provider == "qwen":
        model = settings.llm.model_name if model_override is None else model_override
        return "qwen", _safe_model_name(model), _safe_qwen_endpoint()
    if provider == "gemini":
        model = settings.llm.gemini_model_name if model_override is None else model_override
        return "gemini", _safe_model_name(model), "google-genai"
    if provider == "litellm":
        model = (
            settings.llm.litellm_model or f"openrouter/{settings.llm.openrouter_model}"
            if model_override is None
            else model_override
        )
        safe_model = _safe_model_name(model)
        endpoint = "openrouter" if safe_model.startswith("openrouter/") else "litellm"
        return "litellm", safe_model, endpoint
    raise ValueError(
        "Unsupported generation provider; supported providers are qwen, gemini, and litellm."
    )


def _effective_embedder_config() -> tuple[str, int]:
    from src.ingestion.indexing.factory import get_vector_store_runtime_config

    config = get_vector_store_runtime_config()
    model = config.get("embedding_model", settings.llm.embedding_model)
    batch_size = config.get("embedding_batch_size", settings.llm.embedding_batch_size)
    return _safe_model_name(model), int(batch_size)


def _effective_enrichment_config() -> dict[str, Any]:
    from src.config.context import get_runtime_state

    features = dict(get_runtime_state().indexing_features)
    return {
        "hype_enabled": bool(features.get("enable_hype", settings.hype.enabled)),
        "hype_sample_rate": float(features.get("hype_sample_rate", settings.hype.sample_rate)),
        "hype_max_chunks": int(features.get("hype_max_chunks", settings.hype.max_chunks)),
        "hype_questions_per_chunk": int(
            features.get("hype_questions_per_chunk", settings.hype.questions_per_chunk)
        ),
        "keyword_extraction_enabled": bool(
            features.get("enable_keyword_extraction", settings.enrichment.enable_keyword_extraction)
        ),
        "chunk_summaries_enabled": bool(
            features.get("enable_chunk_summaries", settings.enrichment.enable_chunk_summaries)
        ),
        "keyword_extraction_sample_rate": float(
            features.get(
                "keyword_extraction_sample_rate",
                settings.enrichment.keyword_extraction_sample_rate,
            )
        ),
        "keyword_extraction_max_chunks": int(
            features.get(
                "keyword_extraction_max_chunks", settings.enrichment.keyword_extraction_max_chunks
            )
        ),
    }


def effective_roles(
    *,
    task: str = "answer_eval",
    implementation: str = "existing",
    harness: str = "deterministic_rag",
    generator_provider: str | None = None,
    generator_model: str | None = None,
) -> dict[str, Any]:
    """Return an allowlisted task snapshot without credential values.

    Supported task names describe existing execution paths only. Unimplemented
    adapters and harnesses fail instead of being recorded as effective.
    """
    if implementation != "existing":
        raise ValueError("Unsupported generation implementation; only 'existing' is available.")
    if harness != "deterministic_rag":
        raise ValueError("Unsupported chat harness; only 'deterministic_rag' is available.")
    if task not in _SUPPORTED_TASKS:
        raise ValueError(
            f"Unsupported role task; supported tasks are {', '.join(_SUPPORTED_TASKS)}."
        )
    if task != "generation" and (generator_provider is not None or generator_model is not None):
        raise ValueError(
            "Unsupported generator override; explicit overrides are only valid for generation."
        )

    enrichment_config = _effective_enrichment_config() if task == "index_build" else {}
    enrichment_enabled = any(
        enrichment_config.get(key, False)
        for key in (
            "hype_enabled",
            "keyword_extraction_enabled",
            "chunk_summaries_enabled",
        )
    )
    task_roles = {
        "generation": {"generator"},
        "judge": {"judge"},
        "retrieval": {"embedder"},
        "answer_eval": {"generator", "judge", "embedder"},
        "index_build": {"embedder"} | ({"enrichment"} if enrichment_enabled else set()),
    }[task]
    generation_attempts = max(1, int(settings.retry.max_retries))
    roles: dict[str, Any] = {
        "generator": {"status": "not_required"},
        "judge": {"status": "not_required"},
        "embedder": {"status": "not_required"},
        "enrichment": {"status": "not_required"},
    }
    credentials: dict[str, dict[str, Any]] = {}
    required_credentials: list[str] = []

    if "generator" in task_roles:
        provider, model, endpoint = _generation_details(generator_provider, generator_model)
        setting_name, configured = _credential(provider)
        credentials["generator"] = {
            "setting": setting_name,
            "configured": configured,
            "required": True,
        }
        roles["generator"] = {
            "provider": provider,
            "model": model,
            "endpoint": endpoint,
            "temperature": _GENERATION_TEMPERATURE,
            "max_tokens": _GENERATION_MAX_TOKENS,
            "timeout_seconds": _GENERATION_TIMEOUT_SECONDS,
            "retry_attempts": generation_attempts,
            "sdk_retries": 0,
            "retry_delay_seconds": max(0.0, settings.retry.retry_delay),
            "credential": credentials["generator"],
        }
        if not configured:
            required_credentials.append(setting_name)

    if "judge" in task_roles:
        judge_provider = resolve_judge_provider()
        setting_name, configured = _credential(judge_provider)
        temperature, max_tokens, timeout_seconds = _judge_parameters()
        credentials["judge"] = {
            "setting": setting_name,
            "configured": configured,
            "required": True,
        }
        endpoint = {
            "qwen": _safe_qwen_endpoint(),
            "gemini": "google-genai",
            "litellm": "openrouter",
            "pydantic-ai": _safe_pydantic_ai_endpoint(),
        }[judge_provider]
        roles["judge"] = {
            "provider": judge_provider,
            "light_model": _judge_model_name(judge_provider, "light"),
            "heavy_model": _judge_model_name(judge_provider, "heavy"),
            "endpoint": endpoint,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "max_tokens_parameter": (
                "max_completion_tokens"
                if judge_provider == "pydantic-ai"
                else ("max_output_tokens" if judge_provider == "gemini" else "max_tokens")
            ),
            "timeout_seconds": timeout_seconds,
            # The adapter owns its own settings.retry-bounded loop, so one direct
            # call can reach the wire more than once; other wrappers call once.
            "request_attempts": generation_attempts if judge_provider == "pydantic-ai" else 1,
            "sdk_retries": 0,
            "outer_metric_max_attempts": 2,
            "retry_scope": (
                "adapter settings.retry loop per direct model call; "
                "outer metric retries are separate"
                if judge_provider == "pydantic-ai"
                else "one direct model call; outer metric retries are separate"
            ),
            "rubric": {
                "source": _MEDICAL_RUBRIC_SOURCE,
                "metric_keys": list(_MEDICAL_RUBRIC_METRICS),
            },
            "credential": credentials["judge"],
        }
        if not configured:
            required_credentials.append(setting_name)

    qwen_endpoint = _safe_qwen_endpoint() if task_roles & {"embedder", "enrichment"} else None
    if task == "index_build" and not enrichment_enabled:
        roles["enrichment"] = {
            "provider": "qwen",
            "model": _safe_model_name(settings.llm.model_name),
            "endpoint": qwen_endpoint,
            "enabled": False,
            **enrichment_config,
            "credential": {
                "setting": "APP__LLM__DASHSCOPE_API_KEY",
                "configured": _credential("qwen")[1],
                "required": False,
            },
        }
    if "embedder" in task_roles:
        embedder_model, embedding_batch_size = _effective_embedder_config()
        setting_name, configured = _credential("qwen")
        credentials["embedder"] = {
            "setting": setting_name,
            "configured": configured,
            "required": True,
        }
        roles["embedder"] = {
            "provider": "qwen",
            "model": embedder_model,
            "endpoint": qwen_endpoint,
            "dimensions": _EMBEDDING_DIMENSIONS,
            "batch_size": embedding_batch_size,
            "timeout_seconds": _EMBEDDING_TIMEOUT_SECONDS,
            "retry_attempts": generation_attempts,
            "retry_delay_seconds": max(0.0, settings.retry.retry_delay),
            "sdk_retries_per_attempt": DEFAULT_MAX_RETRIES,
            "maximum_wire_attempts": generation_attempts * (DEFAULT_MAX_RETRIES + 1),
            "credential": credentials["embedder"],
        }
        if not configured:
            required_credentials.append(setting_name)

    if "enrichment" in task_roles:
        setting_name, configured = _credential("qwen")
        credentials["enrichment"] = {
            "setting": setting_name,
            "configured": configured,
            "required": True,
        }
        roles["enrichment"] = {
            "provider": "qwen",
            "model": _safe_model_name(settings.llm.model_name),
            "endpoint": qwen_endpoint,
            "enabled": True,
            **enrichment_config,
            "temperature": _GENERATION_TEMPERATURE,
            "max_tokens": _GENERATION_MAX_TOKENS,
            "timeout_seconds": _GENERATION_TIMEOUT_SECONDS,
            "retry_attempts": generation_attempts,
            "sdk_retries": 0,
            "retry_delay_seconds": max(0.0, settings.retry.retry_delay),
            "credential": credentials["enrichment"],
        }
        if not configured and setting_name not in required_credentials:
            required_credentials.append(setting_name)

    needs_deepeval = task in {"judge", "answer_eval"}
    try:
        deepeval_available = importlib.util.find_spec("deepeval") is not None
    except (ImportError, ValueError):
        deepeval_available = False
    required_dependencies = ["deepeval"] if needs_deepeval else []
    missing_dependencies = ["deepeval"] if needs_deepeval and not deepeval_available else []
    return {
        "task": task,
        "implementation": implementation,
        "harness": harness,
        **roles,
        "required_credentials": required_credentials,
        "required_dependencies": required_dependencies,
        "missing_dependencies": missing_dependencies,
    }
