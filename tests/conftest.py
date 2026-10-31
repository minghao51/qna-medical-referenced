import json
import os
from pathlib import Path

import pytest


def _ensure_nltk_stopwords_available() -> None:
    """Ensure the NLTK 'stopwords' corpus resolves without network access.

    src/ingestion/indexing/text_utils.py loads English stopwords at import
    time. On machines without ``nltk.download('stopwords')`` (e.g. CI
    runners), fall back to the vendored copy under
    tests/integration/fixtures/nltk_data. Must run before any module that
    imports src.ingestion.indexing (i.e. at conftest import time).
    """
    try:
        from nltk.corpus import stopwords

        stopwords.words("english")
        return
    except LookupError:
        pass

    import nltk.data

    nltk.data.path.append(str(Path(__file__).parent / "integration" / "fixtures" / "nltk_data"))
    from nltk.corpus import stopwords as vendored_stopwords

    vendored_stopwords.words("english")  # fail fast if the vendored copy is broken


_ensure_nltk_stopwords_available()


if "APP__LLM__DASHSCOPE_API_KEY" not in os.environ or not os.environ.get(
    "APP__LLM__DASHSCOPE_API_KEY"
):
    os.environ["APP__LLM__DASHSCOPE_API_KEY"] = "test-api-key"


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

    skip_live = pytest.mark.skip(reason="Set RUN_LIVE_QWEN_TESTS=1 to run live Qwen API tests")
    if not LIVE_QWEN_ENABLED:
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
        client = OpenAI(
            api_key=settings.llm.dashscope_api_key.get_secret_value(),
            base_url=settings.llm.qwen_base_url,
        )
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
        _openrouter_key = settings.llm.openrouter_api_key.get_secret_value()
        if _openrouter_key:
            os.environ.setdefault("OPENROUTER_API_KEY", _openrouter_key)
        litellm.completion(
            model=f"openrouter/{settings.llm.openrouter_model}",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1,
        )
    except Exception as exc:
        _LIVE_OPENROUTER_PRECHECK = f"Live OpenRouter API unavailable: {type(exc).__name__}: {exc}"
        pytest.skip(_LIVE_OPENROUTER_PRECHECK)

    _LIVE_OPENROUTER_PRECHECK = "ok"


# =============================================================================
# Project-data mutation guard
# =============================================================================
#
# Tests must isolate project data explicitly: they may read `data/` fixtures but
# must never write it. The frozen index is synced as an immutable artifact and
# the rest (processed/evals artifacts, chat history, rate-limit DB, raw corpus,
# silver/gold layers) is runtime state, so a test that writes any of it has
# silently changed project data.
#
# The guard fingerprints the whole `data/` tree at session start and fails the
# session if anything was created, modified or removed. It never reads file
# contents and never deletes anything. Deliberate data work (live provider
# runs, fixture regeneration) disables it with QNA_TEST_DATA_GUARD=0 or an
# opt-in flag.

_DATA_GUARD_BASELINE: dict[str, tuple[int, int]] = {}


def _data_guard_active(config) -> bool:
    if os.environ.get("QNA_TEST_DATA_GUARD") == "0":
        return False
    if LIVE_QWEN_ENABLED or LIVE_OPENROUTER_ENABLED or REAL_API_TESTS_ENABLED:
        return False
    # Under xdist the controller observes every worker's writes; workers would
    # only report their peers' mutations.
    return not hasattr(config, "workerinput")


def _data_fingerprint() -> dict[str, tuple[int, int]]:
    from src.config.paths import DATA_DIR

    fingerprint: dict[str, tuple[int, int]] = {}
    if not DATA_DIR.exists():
        return fingerprint
    for path in DATA_DIR.rglob("*"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if path.is_file():
            fingerprint[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return fingerprint


def _data_changes(
    before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]
) -> list[str]:
    changes = [f"created {path}" for path in sorted(after.keys() - before.keys())]
    changes += [f"removed {path}" for path in sorted(before.keys() - after.keys())]
    changes += [
        f"modified {path}"
        for path in sorted(before.keys() & after.keys())
        if before[path] != after[path]
    ]
    return changes


def pytest_sessionstart(session) -> None:
    if not _data_guard_active(session.config):
        return
    _DATA_GUARD_BASELINE.clear()
    _DATA_GUARD_BASELINE.update(_data_fingerprint())


def pytest_sessionfinish(session, exitstatus):
    if not _DATA_GUARD_BASELINE:
        return None
    before = dict(_DATA_GUARD_BASELINE)
    _DATA_GUARD_BASELINE.clear()
    changes = _data_changes(before, _data_fingerprint())
    if not changes:
        return None

    shown = changes[:10]
    message = [
        "PROJECT DATA MUTATED BY TESTS: the offline suite must not write "
        "project data under data/ (frozen index, processed/evals artifacts, "
        "chat history, rate-limit DB, raw corpus, silver/gold layers).",
        f"{len(changes)} change(s); first {len(shown)}:",
    ]
    message += [f"  - {change}" for change in shown]
    message.append(
        "Isolate the offending test: pass persist_directory=tmp_path / 'chroma' (or patch "
        "settings.storage.chroma_persist_directory), and patch "
        "src.ingestion.artifacts.DATA_PROCESSED_DIR for artifact writes. "
        "Set QNA_TEST_DATA_GUARD=0 only for deliberate data work."
    )
    text = "\n".join(message)

    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(text, red=True)
    else:  # pragma: no cover - non-terminal runs
        print(text)

    if session.exitstatus == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    return session.exitstatus
