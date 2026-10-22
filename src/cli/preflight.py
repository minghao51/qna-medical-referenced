"""Offline deployment diagnostics without initializing providers or storage."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SETTINGS_MODULE = "_qna_preflight_settings"


def _load_settings() -> Any:
    """Load the existing settings model without config package directory creation."""
    loaded_package = sys.modules.get("src.config")
    if loaded_package is not None:
        return loaded_package.settings

    settings_path = PROJECT_ROOT / "src" / "config" / "settings.py"
    spec = importlib.util.spec_from_file_location(_SETTINGS_MODULE, settings_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load application settings for preflight")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_SETTINGS_MODULE] = module
    spec.loader.exec_module(module)
    return module.settings


_PROVIDER_CREDENTIALS = {
    "qwen": "APP__LLM__DASHSCOPE_API_KEY",
    "gemini": "APP__LLM__GEMINI_API_KEY",
    "litellm": "APP__LLM__OPENROUTER_API_KEY",
}
_PROVIDER_MODELS = {
    "qwen": "model_name",
    "gemini": "gemini_model_name",
    "litellm": "litellm_model",
}
_OPTIONAL_PACKAGES = {
    "evaluation": "deepeval",
    "chunkers": "chonkie",
    "extraction": "camelot",
    "reranking": "sentence_transformers",
    "medical": "spacy",
}


def _secret_value(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if getter else value or "")


def _provider_model(config: Any, provider: str) -> str | None:
    if provider == "litellm":
        value = config.llm.litellm_model or config.llm.openrouter_model
    else:
        field = _PROVIDER_MODELS.get(provider)
        value = getattr(config.llm, field) if field else None
    return value if isinstance(value, str) else None


def _credential_ready(config: Any, provider: str) -> bool:
    if provider == "qwen":
        value = config.llm.dashscope_api_key
    elif provider == "gemini":
        value = config.llm.gemini_api_key
    elif provider == "litellm":
        value = config.llm.openrouter_api_key
    else:
        return False
    return bool(_secret_value(value).strip())


def _api_credentials_ready(config: Any, is_development: bool) -> tuple[bool, bool]:
    plain_keys = _secret_value(config.api.api_keys)
    plain_keys_ready = any(key.strip() for key in plain_keys.split(","))

    serialized = _secret_value(config.api.api_keys_json).strip()
    try:
        records = json.loads(serialized) if serialized else []
    except json.JSONDecodeError:
        records = []

    def _hash_ready(hashed: str) -> bool:
        hashed = hashed.strip()
        if hashed.startswith(("$2b$", "$2a$", "$2y$")):
            return True
        # Runtime normalizes legacy SHA256 hashes to lowercase at load, then
        # _verify_secret() rejects them outside development.
        return (
            is_development
            and len(hashed) == 64
            and all(ch in "0123456789abcdefABCDEF" for ch in hashed)
        )

    json_keys_ready = isinstance(records, list) and any(
        isinstance(record, dict)
        and bool(str(record.get("id") or f"key-{index + 1}").strip())
        and str(record.get("status", "active")).strip().lower() not in {"disabled", "revoked"}
        and (bool(str(record.get("key", "")).strip()) or _hash_ready(str(record.get("hash", ""))))
        for index, record in enumerate(records)
    )
    return plain_keys_ready, json_keys_ready


def _index_time_features(config: Any) -> dict[str, bool]:
    return {
        "hype": bool(config.hype.enabled),
        "keyword_extraction": bool(config.enrichment.enable_keyword_extraction),
        "chunk_summaries": bool(config.enrichment.enable_chunk_summaries),
    }


def _index_path_info(config: Any, root: Path) -> dict[str, Any]:
    configured_path = Path(config.storage.chroma_persist_directory).expanduser()
    path = configured_path if configured_path.is_absolute() else root / configured_path
    try:
        exists: bool | None = path.exists()
    except OSError:
        exists = None
    return {
        "configured_path": str(path),
        "path_exists": exists,
        "readiness": "unverified",
    }


def build_preflight_report(
    config: Any | None = None, *, root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Return non-secret static diagnostics; never opens an index or contacts a provider."""
    if config is None:
        try:
            config = _load_settings()
        except Exception:
            return {"ok": False, "errors": ["configuration_load_failed"]}
    errors: list[str] = []
    credential_requirements: dict[str, set[str]] = {}

    def require_credential(name: str, role: str) -> None:
        credential_requirements.setdefault(name, set()).add(role)

    generation_provider = str(config.llm.provider)
    generation_credential = _PROVIDER_CREDENTIALS.get(generation_provider)
    generation_model = _provider_model(config, generation_provider)
    if generation_credential is None:
        errors.append("unsupported_generation_provider")
    else:
        require_credential(generation_credential, "generation")

    embedding_credential = _PROVIDER_CREDENTIALS["qwen"]
    require_credential(embedding_credential, "embedding")

    judge_provider = str(config.llm.judge_provider or generation_provider)
    judge_credential = _PROVIDER_CREDENTIALS.get(judge_provider)
    if judge_credential is None:
        errors.append("unsupported_judge_provider")

    index_features = _index_time_features(config)
    index_time_selected = any(index_features.values())
    if index_time_selected:
        require_credential(embedding_credential, "index_time_qwen")

    environment = str(config.app.environment).strip().lower()
    is_development = environment in {"development", "dev", "local", "test"}
    auth_keys_ready, auth_json_ready = _api_credentials_ready(config, is_development)
    signing_secret = _secret_value(config.api.session_signing_secret).strip()
    signing_secret_ready = len(signing_secret.encode("utf-8")) >= 32
    # Runtime load_api_key_records() uses plain API_KEYS only when API_KEYS_JSON is unset
    # (raw string truthiness); JSON records are used exclusively otherwise.
    json_configured = bool(_secret_value(config.api.api_keys_json))
    if not is_development:
        require_credential("APP__API__SESSION_SIGNING_SECRET", "session_signing")
        auth_ready = auth_json_ready if json_configured else auth_keys_ready
        if not auth_ready:
            errors.append("missing_required_api_auth_credentials")

    profile = config.production.production_profile
    profile_name = str(profile).strip() if profile else None
    # The built-in cross-encoder profile explicitly enables reranking over static settings.
    reranking_selected = bool(config.retrieval.enable_reranking) or (
        profile_name == "baseline_cross_encoder"
    )
    optional_extras: dict[str, dict[str, Any]] = {}
    for extra, package in _OPTIONAL_PACKAGES.items():
        try:
            installed = importlib.util.find_spec(package) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            installed = False
        required = extra == "reranking" and reranking_selected
        optional_extras[extra] = {
            "package": package,
            "installed": installed,
            "required_for_selected_configuration": required,
        }
        if required and not installed:
            errors.append("missing_required_optional_extra:reranking")
    optional_extras["reranking"]["model_assets"] = (
        "unverified" if reranking_selected else "not_required"
    )

    credentials: dict[str, dict[str, Any]] = {}
    for name, roles in credential_requirements.items():
        if name == "APP__API__SESSION_SIGNING_SECRET":
            ready = signing_secret_ready
        elif name == "APP__API__API_KEYS":
            ready = auth_keys_ready
        elif name == "APP__API__API_KEYS_JSON":
            ready = auth_json_ready
        else:
            provider = next(
                (
                    provider
                    for provider, setting in _PROVIDER_CREDENTIALS.items()
                    if setting == name
                ),
                "",
            )
            ready = _credential_ready(config, provider)
        credentials[name] = {
            "ready": ready,
            "required_by": sorted(roles),
        }
        if not ready:
            errors.append(f"missing_required_credential:{name}")

    # In development the runtime validator returns early and requires no auth source,
    # so the per-credential report intentionally omits APP__API__API_KEYS and
    # APP__API__API_KEYS_JSON entries; do not add them for development environments.
    if not is_development:
        # Report fields mirror the effective auth source at runtime, not raw presence:
        # when API_KEYS_JSON is set, plain API_KEYS is ignored entirely, so it is
        # reported as neither ready nor required for api_auth.
        if json_configured:
            credentials["APP__API__API_KEYS_JSON"] = {
                "ready": auth_json_ready,
                "required_by": ["api_auth"],
            }
            credentials["APP__API__API_KEYS"] = {
                "ready": False,
                "required_by": [],
            }
        else:
            credentials["APP__API__API_KEYS"] = {
                "ready": auth_keys_ready,
                "required_by": ["api_auth"],
            }
            credentials["APP__API__API_KEYS_JSON"] = {
                "ready": auth_json_ready,
                "required_by": ["api_auth"],
            }

    judge_model_suffix = {"qwen": "", "gemini": "_gemini", "litellm": "_litellm"}.get(
        judge_provider
    )
    judge_models = None
    if judge_model_suffix is not None:
        judge_models = {
            "light": getattr(config.llm, f"judge_model_light{judge_model_suffix}"),
            "heavy": getattr(config.llm, f"judge_model_heavy{judge_model_suffix}"),
        }

    if judge_credential:
        credentials.setdefault(
            judge_credential,
            {
                "ready": _credential_ready(config, judge_provider),
                "required_by": [],
            },
        )

    if signing_secret and not signing_secret_ready and not is_development:
        errors.append("weak_session_signing_secret")

    return {
        "ok": not errors,
        "deployment": {
            "environment": environment,
            "production_entrypoint_allowed": environment == "production",
            "supported_workers": 1,
            "session_history_topology": "single_process_only",
        },
        "roles": {
            "generation": {
                "provider": generation_provider,
                "model": generation_model,
                "credential_name": generation_credential,
                "credential_ready": (
                    _credential_ready(config, generation_provider)
                    if generation_credential
                    else False
                ),
            },
            "judge": {
                "provider": judge_provider,
                "models": judge_models,
                "credential_name": judge_credential,
                "credential_ready": (
                    _credential_ready(config, judge_provider) if judge_credential else False
                ),
                "required_for_serving": False,
            },
            "embedding": {
                "provider": "qwen",
                "model": config.llm.embedding_model,
                "dimensions": 768,
                "credential_name": embedding_credential,
                "credential_ready": _credential_ready(config, "qwen"),
            },
            "index_time_qwen": {
                "provider": "qwen",
                "model": config.llm.model_name,
                "configured_features": index_features,
                "selected_for_next_build": index_time_selected,
                "credential_name": embedding_credential,
                "credential_ready": _credential_ready(config, "qwen"),
            },
        },
        "credentials": credentials,
        "optional_extras": optional_extras,
        "retrieval": {
            "production_profile": profile_name,
            "reranking_selected": reranking_selected,
            "reranker_model": config.retrieval.reranker_model if reranking_selected else None,
        },
        "index": _index_path_info(config, root),
        "errors": errors,
    }


def main() -> int:
    argparse.ArgumentParser(
        description="Report non-secret configuration readiness without network or storage access"
    ).parse_args()
    report = build_preflight_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
