"""DeepEval judge wrapper for the opt-in ``pydantic-ai`` judge provider.

Reuses :class:`src.infra.llm.pydantic_ai_client.PydanticAIClient` for transport,
timeouts, identity headers, retries, and usage accounting, so the judge path
adds no second retry layer and no duplicate request assembly. The judge
factories in :mod:`src.evals.deepeval_models` are expected to construct this
class through a lazy import (no import cycle): this module imports only the
``_safe_model_name``/``_judge_parameters`` helpers from that module.

Known confounds and limitations (every claim below is offline-only verified):

- Prompt shape: the DeepEval metric prompt is sent verbatim as a single raw user
  message (``raw_prompt=True``) — no chat system prompt, no
  ``USER_PROMPT_TEMPLATE``, no instructions message. DeepEval metrics expect
  their own prompt text to carry rubrics and output-format instructions; this
  wrapper never rewrites, repairs, or parses that output, mirroring the
  Qwen/LiteLLM judge wrappers. ``supports_json_mode`` and
  ``supports_structured_outputs`` are ``False`` for the same reason, so DeepEval
  must fall back to plain text instead of a structured mode the route may not
  honor.
- Route/family overlap: ``pydantic-ai`` judges use the same OpenCode Go base URL
  (``settings.llm.pydantic_ai_base_url``) and, by default, the same model
  identifier as the ``pydantic-ai`` generator (``mimo-v2.6-flash``). Nothing
  here enforces judge/generator family independence, so a matched run can score
  a generator with a same-family judge over the same route; independent-judge
  pinning remains a D17/P4-D configuration decision.
- ``max_completion_tokens`` mapping: the adapter's ``max_tokens`` model setting
  (here ``settings.llm.judge_max_tokens``) is sent as the framework's
  ``max_completion_tokens`` wire field for models without a known profile. The
  limit value is the judge limit, but the field name differs from the
  Qwen/LiteLLM ``max_tokens`` and OpenCode Go acceptance is unverified.
- Empty output: the adapter raises on a falsy run output; that documented guard
  is translated back to ``""`` so DeepEval sees an empty judge completion
  instead of an exception, matching ``LiteLLMJudgeModel``. A provider response
  that pydantic-ai itself rejects as empty (internally retried, then raised)
  still surfaces as an error.
- Sync restriction: the adapter's sync methods raise ``RuntimeError`` inside a
  running event loop; async metrics must use ``a_generate``. Only the async
  transport exists, so ``close`` is a documented no-op and ``aclose`` performs
  the real cleanup.
- No live route validation: no request to OpenCode Go has been made. Auth,
  latency, usage accuracy, judge quality, and route acceptance of the judge
  settings remain untested until the separately approved P4-D live smoke.

Retries stay owned by the adapter (``settings.retry``-bounded loop, SDK
``max_retries=0``); DeepEval's outer metric retries are separate and unchanged.
Judge token usage is attributed through :func:`src.infra.usage.usage_role` to
the configured ``usage_role`` (``judge``/``judge_light``/``judge_heavy``).
"""

from src.evals.deepeval_models import _judge_parameters, _safe_model_name
from src.infra.llm.pydantic_ai_client import PydanticAIClient
from src.infra.usage import usage_role

try:
    from deepeval.models import DeepEvalBaseLLM
except ModuleNotFoundError:

    class DeepEvalBaseLLM:  # type: ignore[no-redef]
        """Fallback base class when the optional deepeval extra is absent."""


# Mirrors the adapter's documented empty-output guard so a falsy judge
# completion reaches DeepEval as "" instead of an exception.
_EMPTY_OUTPUT_ERROR = "Empty response from Pydantic AI adapter"


class PydanticAIJudgeModel(DeepEvalBaseLLM):
    """DeepEval judge wrapper for the opt-in ``pydantic-ai`` provider."""

    def __init__(self, model: str):
        self.usage_role = "judge"
        self.model_name = _safe_model_name(model)
        self.name = self.model_name
        self.model = self
        self.temperature, self.max_tokens, self.timeout_seconds = _judge_parameters()
        # Judge settings, not generation settings, and a verbatim prompt: the
        # metric text must reach the model unchanged.
        self.client = PydanticAIClient(
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout_seconds=self.timeout_seconds,
            raw_prompt=True,
        )

    def load_model(self) -> "PydanticAIJudgeModel":
        return self

    def generate(self, prompt: str) -> str:
        with usage_role(self.usage_role):
            try:
                return self.client.generate(prompt)
            except ValueError as exc:
                if str(exc) != _EMPTY_OUTPUT_ERROR:
                    raise
                return ""

    async def a_generate(self, prompt: str) -> str:
        with usage_role(self.usage_role):
            try:
                return await self.client.a_generate(prompt)
            except ValueError as exc:
                if str(exc) != _EMPTY_OUTPUT_ERROR:
                    raise
                return ""

    def close(self) -> None:
        """No-op: the adapter owns only an async transport; use ``aclose``."""

    async def aclose(self) -> None:
        """Close the adapter's owned async transport on its owning loop.

        The underlying ``httpx.AsyncClient.aclose`` is idempotent, so repeated
        or nested cleanup is safe and closes the transport exactly once.
        """
        await self.client.aclose()

    def get_model_name(self) -> str:
        return self.model_name

    def supports_json_mode(self) -> bool:
        return False

    def supports_structured_outputs(self) -> bool:
        return False

    def supports_temperature(self) -> bool:
        return True
