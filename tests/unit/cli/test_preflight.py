import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from src.cli import preflight

# Synthetic format-only fixtures: preflight (and runtime record loading) only
# inspect hash shape, so no real secret is hashed or authenticated here.
_SYNTHETIC_BCRYPT_HASH = "$2b$12$" + "x" * 53
_SYNTHETIC_LEGACY_LOWER = "a" * 64
_SYNTHETIC_LEGACY_UPPER = "A" * 64
_SYNTHETIC_SIGNING_SECRET = SecretStr("synthetic-session-signing-secret-with-32-bytes")


def _config(
    *,
    provider="gemini",
    judge_provider=None,
    dashscope_key="embedding-key",
    gemini_key="generation-key",
    openrouter_key="",
    pydantic_ai_key="",
    environment="development",
    profile="baseline",
    enable_reranking=False,
    index_path="missing-index",
):
    return SimpleNamespace(
        app=SimpleNamespace(environment=environment),
        api=SimpleNamespace(
            api_keys=None,
            api_keys_json=None,
            session_signing_secret=None,
        ),
        llm=SimpleNamespace(
            provider=provider,
            judge_provider=judge_provider,
            model_name="qwen3.5-flash",
            gemini_model_name="gemma-4-31b-it",
            openrouter_model="google/gemma-4-31b-it",
            litellm_model="",
            embedding_model="text-embedding-v4",
            dashscope_api_key=SecretStr(dashscope_key),
            gemini_api_key=SecretStr(gemini_key),
            openrouter_api_key=SecretStr(openrouter_key),
            judge_model_light="qwen-light",
            judge_model_heavy="qwen-heavy",
            judge_model_light_gemini="gemini-light",
            judge_model_heavy_gemini="gemini-heavy",
            judge_model_light_litellm="router-light",
            judge_model_heavy_litellm="router-heavy",
            judge_model_light_pydantic_ai="pydantic-ai-light",
            judge_model_heavy_pydantic_ai="pydantic-ai-heavy",
            pydantic_ai_model="mimo-v2.6-flash",
            pydantic_ai_api_key=SecretStr(pydantic_ai_key),
        ),
        hype=SimpleNamespace(enabled=False),
        enrichment=SimpleNamespace(
            enable_keyword_extraction=False,
            enable_chunk_summaries=False,
        ),
        production=SimpleNamespace(production_profile=profile),
        retrieval=SimpleNamespace(
            enable_reranking=enable_reranking, reranker_model="BAAI/bge-reranker-base"
        ),
        storage=SimpleNamespace(chroma_persist_directory=index_path),
    )


def test_preflight_requires_selected_generation_and_embedding_credentials_only(tmp_path):
    config = _config(
        provider="litellm",
        judge_provider="gemini",
        dashscope_key="embedding-key",
        openrouter_key="",
    )

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is False
    assert "missing_required_credential:APP__LLM__OPENROUTER_API_KEY" in report["errors"]
    assert "missing_required_credential:APP__LLM__GEMINI_API_KEY" not in report["errors"]
    assert report["credentials"]["APP__LLM__OPENROUTER_API_KEY"]["required_by"] == ["generation"]
    assert report["credentials"]["APP__LLM__GEMINI_API_KEY"]["required_by"] == []
    assert report["roles"]["embedding"]["credential_name"] == "APP__LLM__DASHSCOPE_API_KEY"
    assert report["roles"]["judge"]["required_for_serving"] is False


def test_preflight_reports_explicit_qwen_index_time_roles(tmp_path):
    config = _config(dashscope_key="", provider="gemini")
    config.hype.enabled = True

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["roles"]["index_time_qwen"]["selected_for_next_build"] is True
    assert report["roles"]["index_time_qwen"]["configured_features"]["hype"] is True
    assert report["credentials"]["APP__LLM__DASHSCOPE_API_KEY"]["required_by"] == [
        "embedding",
        "index_time_qwen",
    ]
    assert "missing_required_credential:APP__LLM__DASHSCOPE_API_KEY" in report["errors"]


def test_baseline_needs_no_reranker_and_index_readiness_is_not_probed(tmp_path):
    config = _config(index_path="not-created", profile="baseline")

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is True
    assert report["optional_extras"]["reranking"]["required_for_selected_configuration"] is False
    assert report["optional_extras"]["reranking"]["model_assets"] == "not_required"
    assert report["index"]["path_exists"] is False
    assert report["index"]["readiness"] == "unverified"
    assert not (tmp_path / "not-created").exists()


def test_selected_cross_encoder_profile_requires_optional_extra_and_leaves_assets_unverified(
    monkeypatch, tmp_path
):
    config = _config(profile="baseline_cross_encoder")
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _name: None)

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is False
    assert "missing_required_optional_extra:reranking" in report["errors"]
    assert report["optional_extras"]["reranking"]["required_for_selected_configuration"] is True
    assert report["optional_extras"]["reranking"]["model_assets"] == "unverified"


def test_production_preflight_rejects_empty_or_malformed_json_auth_records(tmp_path):
    config = _config(environment="production")
    config.api.session_signing_secret = SecretStr("synthetic-session-signing-secret-with-32-bytes")
    config.api.api_keys_json = "[]"

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["credentials"]["APP__API__API_KEYS"]["ready"] is False
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["ready"] is False
    assert "missing_required_api_auth_credentials" in report["errors"]


def test_production_preflight_requires_auth_and_never_serializes_secret_values(tmp_path):
    secret = "synthetic-session-signing-secret-with-32-bytes"
    config = _config(environment="production")
    config.api.session_signing_secret = SecretStr(secret)
    config.api.api_keys = "synthetic-caller-key"

    report = preflight.build_preflight_report(config, root=tmp_path)
    serialized = json.dumps(report)

    assert report["credentials"]["APP__API__SESSION_SIGNING_SECRET"]["ready"] is True
    assert report["credentials"]["APP__API__API_KEYS"]["ready"] is True
    assert report["deployment"]["supported_workers"] == 1
    assert report["deployment"]["session_history_topology"] == "single_process_only"
    assert secret not in serialized
    assert "synthetic-caller-key" not in serialized


@pytest.mark.parametrize("environment", ["production", "staging"])
@pytest.mark.parametrize("legacy_hash", [_SYNTHETIC_LEGACY_LOWER, _SYNTHETIC_LEGACY_UPPER])
def test_preflight_outside_development_rejects_legacy_sha256_only_records(
    environment, legacy_hash, tmp_path
):
    config = _config(environment=environment)
    config.api.session_signing_secret = _SYNTHETIC_SIGNING_SECRET
    config.api.api_keys_json = json.dumps([{"id": "synthetic-key", "hash": legacy_hash}])

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is False
    assert "missing_required_api_auth_credentials" in report["errors"]
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["ready"] is False
    assert legacy_hash not in json.dumps(report)


@pytest.mark.parametrize("legacy_hash", [_SYNTHETIC_LEGACY_LOWER, _SYNTHETIC_LEGACY_UPPER])
def test_preflight_development_counts_case_normalized_legacy_hashes_ready(legacy_hash):
    config = _config(environment="development")
    config.api.api_keys_json = json.dumps([{"id": "synthetic-key", "hash": legacy_hash}])

    plain_ready, json_ready = preflight._api_credentials_ready(config, is_development=True)

    assert plain_ready is False
    assert json_ready is True


@pytest.mark.parametrize("status", ["disabled", "revoked"])
def test_preflight_production_rejects_inactive_auth_records(status, tmp_path):
    config = _config(environment="production")
    config.api.session_signing_secret = _SYNTHETIC_SIGNING_SECRET
    config.api.api_keys_json = json.dumps(
        [{"id": "synthetic-key", "key": "synthetic-caller-key", "status": status}]
    )

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is False
    assert "missing_required_api_auth_credentials" in report["errors"]
    assert "synthetic-caller-key" not in json.dumps(report)


def test_preflight_production_accepts_mixed_bcrypt_and_plaintext_with_legacy_record(tmp_path):
    config = _config(environment="production")
    config.api.session_signing_secret = _SYNTHETIC_SIGNING_SECRET
    config.api.api_keys_json = json.dumps(
        [
            {"id": "synthetic-admin", "hash": _SYNTHETIC_BCRYPT_HASH},
            {"id": "synthetic-legacy", "hash": _SYNTHETIC_LEGACY_UPPER},
            {"id": "synthetic-service", "key": "synthetic-caller-key"},
        ]
    )

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is True
    assert report["errors"] == []
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["ready"] is True
    serialized = json.dumps(report)
    assert "synthetic-caller-key" not in serialized
    assert _SYNTHETIC_BCRYPT_HASH not in serialized
    assert _SYNTHETIC_LEGACY_UPPER not in serialized


def test_preflight_production_plain_api_keys_do_not_mask_unusable_json_records(tmp_path):
    config = _config(environment="production")
    config.api.session_signing_secret = _SYNTHETIC_SIGNING_SECRET
    config.api.api_keys = "synthetic-caller-key"
    config.api.api_keys_json = json.dumps(
        [{"id": "synthetic-key", "hash": _SYNTHETIC_LEGACY_UPPER}]
    )

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is False
    assert "missing_required_api_auth_credentials" in report["errors"]


def test_preflight_production_rejects_whitespace_only_id_plaintext_record(tmp_path):
    # Runtime _normalize_record() drops records whose effective id strips to empty;
    # a whitespace-only id is the ONLY defect in this fixture, so readiness stays false.
    config = _config(environment="production")
    config.api.session_signing_secret = _SYNTHETIC_SIGNING_SECRET
    config.api.api_keys_json = json.dumps([{"id": "  ", "key": "synthetic-caller-key"}])

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is False
    assert "missing_required_api_auth_credentials" in report["errors"]
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["ready"] is False
    assert "synthetic-caller-key" not in json.dumps(report)


def test_preflight_production_accepts_whitespace_padded_bcrypt_hash(tmp_path):
    # Runtime strips hash values before the bcrypt-prefix check, matching preflight.
    config = _config(environment="production")
    config.api.session_signing_secret = _SYNTHETIC_SIGNING_SECRET
    config.api.api_keys_json = json.dumps(
        [{"id": "synthetic-padded", "hash": f"  {_SYNTHETIC_BCRYPT_HASH}  "}]
    )

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is True
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["ready"] is True
    assert _SYNTHETIC_BCRYPT_HASH not in json.dumps(report)


def test_preflight_production_bcrypt_hash_only_record_reports_ready(tmp_path):
    # Readiness here only proves the $2b$/$2a$/$2y$ hash SHAPE passes preflight's
    # static format check, not that any secret authenticates against it.
    config = _config(environment="production")
    config.api.session_signing_secret = _SYNTHETIC_SIGNING_SECRET
    config.api.api_keys_json = json.dumps([{"id": "synthetic-key", "hash": _SYNTHETIC_BCRYPT_HASH}])

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is True
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["ready"] is True
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["required_by"] == ["api_auth"]


def test_preflight_production_report_prefers_json_records_over_ignored_plain_keys(tmp_path):
    # Runtime load_api_key_records() ignores plain API_KEYS whenever API_KEYS_JSON is
    # set, so the report must not present the ignored source as ready or required for
    # api_auth — otherwise operators would misread the effective auth source.
    config = _config(environment="production")
    config.api.session_signing_secret = _SYNTHETIC_SIGNING_SECRET
    config.api.api_keys = "synthetic-caller-key"
    config.api.api_keys_json = json.dumps([{"id": "synthetic-key", "hash": _SYNTHETIC_BCRYPT_HASH}])

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["ok"] is True
    assert "missing_required_api_auth_credentials" not in report["errors"]
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["ready"] is True
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["required_by"] == ["api_auth"]
    assert report["credentials"]["APP__API__API_KEYS"]["ready"] is False
    assert report["credentials"]["APP__API__API_KEYS"]["required_by"] == []


@pytest.mark.parametrize("environment", ["development", "dev", "local", "test"])
def test_preflight_development_aliases_report_without_auth_requirements(environment, tmp_path):
    # Development reporting contract: the runtime validator returns early and no auth
    # source is required, so the public report contains no auth credential entries.
    config = _config(environment=environment)

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["deployment"]["environment"] == environment
    assert report["ok"] is True
    assert "missing_required_api_auth_credentials" not in report["errors"]
    assert "APP__API__API_KEYS" not in report["credentials"]
    assert "APP__API__API_KEYS_JSON" not in report["credentials"]
    assert "APP__API__SESSION_SIGNING_SECRET" not in report["credentials"]


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_preflight_outside_development_aliases_report_api_auth_requirements(environment, tmp_path):
    config = _config(environment=environment)
    config.api.session_signing_secret = _SYNTHETIC_SIGNING_SECRET

    report = preflight.build_preflight_report(config, root=tmp_path)

    assert report["deployment"]["production_entrypoint_allowed"] == (environment == "production")
    assert "missing_required_api_auth_credentials" in report["errors"]
    assert report["credentials"]["APP__API__API_KEYS"]["ready"] is False
    assert report["credentials"]["APP__API__API_KEYS"]["required_by"] == ["api_auth"]
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["ready"] is False
    assert report["credentials"]["APP__API__API_KEYS_JSON"]["required_by"] == ["api_auth"]


def test_pydantic_ai_judge_provider_is_supported_and_reported():
    report = preflight.build_preflight_report(
        _config(judge_provider="pydantic-ai", pydantic_ai_key="synthetic-judge-key")
    )

    assert "unsupported_judge_provider" not in report["errors"]
    judge = report["roles"]["judge"]
    assert judge["provider"] == "pydantic-ai"
    assert judge["models"] == {"light": "pydantic-ai-light", "heavy": "pydantic-ai-heavy"}
    assert judge["credential_name"] == "APP__LLM__PYDANTIC_AI_API_KEY"
    assert judge["credential_ready"] is True
    assert "synthetic-judge-key" not in json.dumps(report)


def test_pydantic_ai_generation_provider_stays_fail_closed():
    report = preflight.build_preflight_report(_config(provider="pydantic-ai"))

    assert "unsupported_generation_provider" in report["errors"]
    assert report["roles"]["generation"]["credential_name"] is None
