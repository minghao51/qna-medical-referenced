import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

if "DASHSCOPE_API_KEY" not in os.environ or not os.environ.get("DASHSCOPE_API_KEY"):
    os.environ["DASHSCOPE_API_KEY"] = "test-api-key"


LIVE_QWEN_ENABLED = os.environ.get("RUN_LIVE_QWEN_TESTS") == "1"
LIVE_OPENROUTER_ENABLED = os.environ.get("RUN_LIVE_OPENROUTER_TESTS") == "1"


@pytest.fixture
def golden_conversations_fixture() -> list[dict]:
    """Load golden conversations from fixture file.

    Returns:
        List of normalized conversation records from golden_conversations.json
    """
    from src.evals.dataset_builder import normalize_golden_conversations

    fixture_path = Path(__file__).parent / "fixtures" / "golden_conversations.json"
    return normalize_golden_conversations(fixture_path)


@pytest.fixture
def golden_conversations_raw() -> dict[str, object]:
    """Load raw golden conversations fixture without normalization.

    Returns:
        Raw dictionary from golden_conversations.json
    """
    fixture_path = Path(__file__).parent / "fixtures" / "golden_conversations.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture
def multi_turn_categories() -> list[str]:
    """List of valid multi-turn conversation categories."""
    return ["contextual_followup", "clarification", "topic_shift", "cross_document"]


@pytest.fixture
def multi_turn_difficulties() -> list[str]:
    """List of valid difficulty levels."""
    return ["easy", "medium", "hard"]


@pytest.fixture
def multi_turn_splits() -> list[str]:
    """List of valid dataset splits."""
    return ["dev", "test", "regression"]


_LIVE_QWEN_PRECHECK: str | None = None

# Real API E2E tests flag
REAL_API_TESTS_ENABLED = os.environ.get("ENABLE_REAL_API_TESTS") == "1"


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "/unit/" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        elif "/e2e/" in item.nodeid:
            item.add_marker(pytest.mark.e2e)

    if LIVE_QWEN_ENABLED:
        return

    skip_live = pytest.mark.skip(reason="Set RUN_LIVE_QWEN_TESTS=1 to run live Qwen API tests")
    for item in items:
        if "live_api" in item.keywords:
            item.add_marker(skip_live)

    if not REAL_API_TESTS_ENABLED:
        skip_real_api = pytest.mark.skip(
            reason="Set ENABLE_REAL_API_TESTS=1 to run real API E2E tests"
        )
        for item in items:
            if "e2e_real_apis" in item.keywords:
                item.add_marker(skip_real_api)

    if not LIVE_OPENROUTER_ENABLED:
        skip_openrouter = pytest.mark.skip(
            reason="Set RUN_LIVE_OPENROUTER_TESTS=1 to run live OpenRouter tests"
        )
        for item in items:
            if "live_openrouter" in item.keywords:
                item.add_marker(skip_openrouter)


def pytest_runtest_setup(item):
    if "live_api" in item.keywords and LIVE_QWEN_ENABLED:
        _ensure_live_qwen_available()
    if "live_openrouter" in item.keywords and LIVE_OPENROUTER_ENABLED:
        _ensure_live_openrouter_available()


def _ensure_live_qwen_available():
    global _LIVE_QWEN_PRECHECK

    if _LIVE_QWEN_PRECHECK == "ok":
        return
    if _LIVE_QWEN_PRECHECK:
        pytest.skip(_LIVE_QWEN_PRECHECK)

    from openai import OpenAI

    from src.config import settings

    try:
        client = OpenAI(api_key=settings.llm.dashscope_api_key, base_url=settings.llm.qwen_base_url)
        # Simple test call to verify API is accessible
        client.embeddings.create(model="text-embedding-v4", input="test")
    except Exception as exc:
        _LIVE_QWEN_PRECHECK = f"Live Qwen API unavailable: {type(exc).__name__}: {exc}"
        pytest.skip(_LIVE_QWEN_PRECHECK)

    _LIVE_QWEN_PRECHECK = "ok"


_LIVE_OPENROUTER_PRECHECK: str | None = None


def _ensure_live_openrouter_available():
    global _LIVE_OPENROUTER_PRECHECK

    if _LIVE_OPENROUTER_PRECHECK == "ok":
        return
    if _LIVE_OPENROUTER_PRECHECK:
        pytest.skip(_LIVE_OPENROUTER_PRECHECK)

    import litellm

    from src.config import settings

    try:
        if settings.openrouter_api_key:
            os.environ.setdefault("OPENROUTER_API_KEY", settings.openrouter_api_key)
        litellm.completion(
            model=f"openrouter/{settings.openrouter_model}",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1,
        )
    except Exception as exc:
        _LIVE_OPENROUTER_PRECHECK = f"Live OpenRouter API unavailable: {type(exc).__name__}: {exc}"
        pytest.skip(_LIVE_OPENROUTER_PRECHECK)

    _LIVE_OPENROUTER_PRECHECK = "ok"
