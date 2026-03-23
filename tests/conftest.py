import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

if "DASHSCOPE_API_KEY" not in os.environ or not os.environ.get("DASHSCOPE_API_KEY"):
    os.environ["DASHSCOPE_API_KEY"] = "test-api-key"


LIVE_QWEN_ENABLED = os.environ.get("RUN_LIVE_QWEN_TESTS") == "1"
_LIVE_QWEN_PRECHECK: str | None = None

# Real API E2E tests flag
REAL_API_TESTS_ENABLED = os.environ.get("ENABLE_REAL_API_TESTS") == "1"

# DeepEval integration tests flag
DEEPEVAL_TESTS_ENABLED = os.environ.get("RUN_DEEPEVAL_TESTS") == "1"


def pytest_collection_modifyitems(config, items):
    # Skip DeepEval tests unless explicitly enabled
    if not DEEPEVAL_TESTS_ENABLED:
        skip_deepeval = pytest.mark.skip(
            reason="Set RUN_DEEPEVAL_TESTS=1 to run DeepEval integration tests"
        )
        for item in items:
            if "deepeval" in item.keywords:
                item.add_marker(skip_deepeval)

    if LIVE_QWEN_ENABLED:
        return

    skip_live = pytest.mark.skip(reason="Set RUN_LIVE_QWEN_TESTS=1 to run live Qwen API tests")
    for item in items:
        if "live_api" in item.keywords:
            item.add_marker(skip_live)

    # Skip real API E2E tests unless explicitly enabled
    if not REAL_API_TESTS_ENABLED:
        skip_real_api = pytest.mark.skip(
            reason="Set ENABLE_REAL_API_TESTS=1 to run real API E2E tests"
        )
        for item in items:
            if "e2e_real_apis" in item.keywords:
                item.add_marker(skip_real_api)


def pytest_runtest_setup(item):
    if "live_api" not in item.keywords or not LIVE_QWEN_ENABLED:
        return

    _ensure_live_qwen_available()


def _ensure_live_qwen_available():
    global _LIVE_QWEN_PRECHECK

    if _LIVE_QWEN_PRECHECK == "ok":
        return
    if _LIVE_QWEN_PRECHECK:
        pytest.skip(_LIVE_QWEN_PRECHECK)

    from openai import OpenAI

    from src.config import settings

    try:
        client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.qwen_base_url)
        # Simple test call to verify API is accessible
        client.embeddings.create(model="text-embedding-v4", input="test")
    except Exception as exc:
        _LIVE_QWEN_PRECHECK = f"Live Qwen API unavailable: {type(exc).__name__}: {exc}"
        pytest.skip(_LIVE_QWEN_PRECHECK)

    _LIVE_QWEN_PRECHECK = "ok"
