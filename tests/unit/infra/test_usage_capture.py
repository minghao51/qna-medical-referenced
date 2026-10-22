"""Provider usage capture is metadata-only and scoped independently of tracing."""

import asyncio
from types import SimpleNamespace

import pytest

from src.infra.usage import (
    begin_usage_call,
    capture_usage,
    finish_usage_call,
    usage_call,
    usage_role,
)


@pytest.mark.parametrize("provider", ["openai", "litellm", "gemini"])
def test_public_sdk_counts_and_real_zeroes(provider):
    values = (
        {"prompt_token_count": 3, "candidates_token_count": 0, "total_token_count": 3}
        if provider == "gemini"
        else {"prompt_tokens": 3, "completion_tokens": 0, "total_tokens": 3}
    )
    response = {"usage_metadata" if provider == "gemini" else "usage": values}
    with capture_usage() as captured:
        with usage_call(provider=provider) as call:
            call.record_response(response)
    assert captured.usage_by_role["generation"] == {
        "input_tokens": 3,
        "output_tokens": 0,
        "total_tokens": 3,
        "status": "reported",
        "source": "provider_sdk",
    }
    assert captured.unknowns == []


@pytest.mark.parametrize("invalid", [True, -1, "patient-secret-canary", float("nan")])
def test_invalid_counts_remain_unknown_without_retaining_values(invalid):
    with capture_usage() as captured:
        with usage_call() as call:
            call.record_response({"usage": {"prompt_tokens": invalid}})
    snapshot = captured.snapshot()
    assert snapshot["usage_by_role"]["generation"]["input_tokens"] is None
    assert snapshot["usage_by_role"]["generation"]["status"] == "incomplete"
    assert "provider_sdk_usage_invalid" in snapshot["unknowns"]
    assert "patient-secret-canary" not in repr(snapshot)


def test_retry_failure_keeps_success_subtotal_incomplete():
    with capture_usage() as captured:
        with pytest.raises(RuntimeError):
            with usage_call():
                raise RuntimeError("synthetic-sdk-secret-canary")
        with usage_call() as call:
            call.record_response(
                {
                    "usage": {
                        "prompt_tokens": 2,
                        "completion_tokens": 4,
                        "total_tokens": 6,
                    }
                }
            )
    assert captured.usage_by_role["generation"]["total_tokens"] == 6
    assert captured.usage_by_role["generation"]["status"] == "incomplete"
    assert "provider_call_failed" in captured.unknowns
    assert "synthetic-sdk-secret-canary" not in repr(captured.snapshot())


def test_stream_cumulative_usage_is_not_summed_per_chunk_or_finished_twice():
    with capture_usage() as captured:
        call = begin_usage_call()
        call.record_response({"usage": {"prompt_tokens": 2}})
        call.record_response(
            {
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 5,
                    "total_tokens": 8,
                }
            }
        )
        finish_usage_call(call)
        finish_usage_call(call)
    assert captured.usage_by_role["generation"]["total_tokens"] == 8
    assert captured.usage_by_role["generation"]["input_tokens"] == 3


def test_missing_and_cancelled_stream_usage_is_not_zero():
    with capture_usage() as captured:
        call = begin_usage_call()
        finish_usage_call(call, failed=True)
    usage = captured.usage_by_role["generation"]
    assert usage["total_tokens"] is None
    assert usage["status"] == "incomplete"


@pytest.mark.asyncio
async def test_worker_context_nested_scopes_and_roles_do_not_cross_runs():
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
        )
    )

    def worker():
        with usage_call() as call:
            call.record_response(response)

    with capture_usage() as outer:
        with usage_role("embedder"):
            await asyncio.gather(*(asyncio.to_thread(worker) for _ in range(8)))
        with capture_usage() as inner:
            with usage_role("judge_light"):
                worker()
        worker()
    assert outer.usage_by_role["embedder"]["total_tokens"] == 24
    assert outer.usage_by_role["generation"]["total_tokens"] == 3
    assert set(inner.usage_by_role) == {"judge_light"}
    assert begin_usage_call() is None
    with capture_usage() as next_run:
        assert next_run.snapshot() == {"usage_by_role": {}, "unknowns": []}


def test_sdk_body_serialization_is_never_used():
    class Response:
        usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3)

        def model_dump(self):
            pytest.fail("usage capture must not serialize SDK bodies")

    with capture_usage() as captured:
        with usage_call() as call:
            call.record_response(Response())
    assert captured.usage_by_role["generation"]["total_tokens"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["qwen", "gemini", "litellm"])
@pytest.mark.parametrize(
    "method", ["generate", "a_generate", "generate_structured", "a_generate_structured"]
)
async def test_generation_adapter_records_public_sdk_usage(provider, method, monkeypatch):
    from pydantic import BaseModel

    from src.infra.llm import gemini_client, litellm_client, qwen_client

    class Answer(BaseModel):
        answer: str

    text = '{"answer":"ok"}'
    response = SimpleNamespace(
        text=text,
        parsed=Answer(answer="ok"),
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=5, total_tokens=7),
        usage_metadata=SimpleNamespace(
            prompt_token_count=2, candidates_token_count=5, total_token_count=7
        ),
    )

    def create(**kwargs):
        return response

    async def create_async(**kwargs):
        return response

    module = {"qwen": qwen_client, "gemini": gemini_client, "litellm": litellm_client}[provider]
    monkeypatch.setattr(
        module, "settings", SimpleNamespace(retry=SimpleNamespace(max_retries=1, retry_delay=0.0))
    )
    if provider == "qwen":
        client = qwen_client.QwenClient.__new__(qwen_client.QwenClient)
        sync_sdk = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        async_sdk = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_async))
        )
        sync_sdk.with_options = lambda **kwargs: sync_sdk
        async_sdk.with_options = lambda **kwargs: async_sdk
        client.client, client.async_client = sync_sdk, async_sdk
    elif provider == "gemini":
        client = gemini_client.GeminiClient.__new__(gemini_client.GeminiClient)
        client.client = SimpleNamespace(
            models=SimpleNamespace(generate_content=create),
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=create_async)),
        )
    else:
        client = litellm_client.LiteLLMClient.__new__(litellm_client.LiteLLMClient)
        client._api_key = None
        monkeypatch.setattr(litellm_client.litellm, "completion", create)
        monkeypatch.setattr(litellm_client.litellm, "acompletion", create_async)
    client.model = "synthetic-model"
    args = ("synthetic prompt", Answer) if "structured" in method else ("synthetic prompt",)
    with capture_usage() as captured:
        result = getattr(client, method)(*args)
        if method.startswith("a_"):
            await result
    assert captured.usage_by_role["generation"]["total_tokens"] == 7
    assert captured.unknowns == []
