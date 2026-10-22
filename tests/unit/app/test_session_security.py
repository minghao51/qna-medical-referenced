import hashlib
import hmac
import json

import pytest
from pydantic import SecretStr

from src.app import security, session
from src.config import settings
from src.config.settings import Settings

_SYNTHETIC_SESSION_SECRET = "synthetic-session-signing-secret-for-tests"
_SYNTHETIC_CALLER_KEY = "synthetic-caller-api-key"


@pytest.fixture
def production_security_config(monkeypatch):
    monkeypatch.setattr(settings.app, "environment", "production")
    monkeypatch.setattr(settings.api, "session_signing_secret", None)
    monkeypatch.setattr(settings.api, "api_keys", _SYNTHETIC_CALLER_KEY)
    monkeypatch.setattr(settings.api, "api_keys_json", None)


def test_nested_environment_setting_is_secret_str(monkeypatch):
    monkeypatch.setenv("APP__API__SESSION_SIGNING_SECRET", _SYNTHETIC_SESSION_SECRET)

    configured = Settings(_env_file=None).api.session_signing_secret

    assert isinstance(configured, SecretStr)
    assert configured.get_secret_value() == _SYNTHETIC_SESSION_SECRET


def _configure_caller_auth(monkeypatch, auth_mode):
    if auth_mode == "plain":
        monkeypatch.setattr(settings.api, "api_keys", _SYNTHETIC_CALLER_KEY)
        monkeypatch.setattr(settings.api, "api_keys_json", None)
    else:
        monkeypatch.setattr(settings.api, "api_keys", None)
        monkeypatch.setattr(
            settings.api,
            "api_keys_json",
            json.dumps([{"id": "synthetic-caller", "key": _SYNTHETIC_CALLER_KEY}]),
        )


@pytest.mark.parametrize("auth_mode", ["plain", "json"])
@pytest.mark.parametrize(
    ("configured_secret", "message"),
    [
        (None, "must be configured"),
        (SecretStr("synthetic-short"), "at least 32"),
        (SecretStr("   \t  "), "at least 32"),
    ],
)
def test_production_rejects_missing_or_weak_session_secret_independent_of_caller_auth(
    monkeypatch, production_security_config, auth_mode, configured_secret, message
):
    _configure_caller_auth(monkeypatch, auth_mode)
    monkeypatch.setattr(settings.api, "session_signing_secret", configured_secret)

    with pytest.raises(RuntimeError, match=message) as error:
        security.validate_security_configuration()

    assert _SYNTHETIC_CALLER_KEY not in str(error.value)
    assert "synthetic-short" not in str(error.value)


@pytest.mark.parametrize("auth_mode", ["plain", "json"])
def test_production_accepts_valid_dedicated_secret_with_either_caller_auth_format(
    monkeypatch, production_security_config, auth_mode
):
    _configure_caller_auth(monkeypatch, auth_mode)
    monkeypatch.setattr(
        settings.api, "session_signing_secret", SecretStr(_SYNTHETIC_SESSION_SECRET)
    )

    security.validate_security_configuration()
    assert session._get_signing_key() == _SYNTHETIC_SESSION_SECRET.encode("utf-8")


def test_startup_rejects_weak_raw_secret_when_typed_config_is_bypassed(
    monkeypatch, production_security_config
):
    monkeypatch.setattr(settings.api, "session_signing_secret", _SYNTHETIC_CALLER_KEY)

    with pytest.raises(RuntimeError, match="at least 32") as error:
        security.validate_security_configuration()

    assert _SYNTHETIC_CALLER_KEY not in str(error.value)


def test_session_signatures_are_independent_of_caller_api_keys(monkeypatch):
    monkeypatch.setattr(settings.app, "environment", "production")
    monkeypatch.setattr(
        settings.api, "session_signing_secret", SecretStr(_SYNTHETIC_SESSION_SECRET)
    )
    monkeypatch.setattr(settings.api, "api_keys", _SYNTHETIC_CALLER_KEY)
    monkeypatch.setattr(settings.api, "api_keys_json", None)
    signature = session._sign_session_id("synthetic-session")

    monkeypatch.setattr(settings.api, "api_keys", "synthetic-rotated-caller-key")
    monkeypatch.setattr(
        settings.api,
        "api_keys_json",
        '[{"id":"synthetic","key":"synthetic-json-caller-key"}]',
    )

    assert session._sign_session_id("synthetic-session") == signature
    assert session._verify_signed_session_id(signature) == "synthetic-session"


def test_tampered_and_legacy_signatures_are_rejected_without_sensitive_errors(monkeypatch, caplog):
    monkeypatch.setattr(settings.app, "environment", "development")
    monkeypatch.setattr(settings.api, "session_signing_secret", None)
    monkeypatch.setattr(settings.api, "api_keys", _SYNTHETIC_CALLER_KEY)
    signed = session._sign_session_id("synthetic-session")
    session_id, signature = signed.rsplit(".", 1)
    tampered = f"{session_id}.{signature[:-1]}{'1' if signature[-1] != '1' else '0'}"

    legacy_api_key_signature = hmac.new(
        _SYNTHETIC_CALLER_KEY.encode(), session_id.encode(), hashlib.sha256
    ).hexdigest()
    legacy_environment_signature = hmac.new(
        b"development", session_id.encode(), hashlib.sha256
    ).hexdigest()

    assert session._verify_signed_session_id(signed) == "synthetic-session"
    assert session._verify_signed_session_id(tampered) is None
    assert session._verify_signed_session_id(f"{session_id}.{legacy_api_key_signature}") is None
    assert session._verify_signed_session_id(f"{session_id}.{legacy_environment_signature}") is None
    assert _SYNTHETIC_CALLER_KEY not in caplog.text
    assert signed not in caplog.text


@pytest.mark.parametrize("signature", ["é" * 64, "not-a-signature", "", "g" * 64])
def test_malformed_cookie_signatures_are_rejected(monkeypatch, signature):
    monkeypatch.setattr(settings.app, "environment", "development")
    monkeypatch.setattr(settings.api, "session_signing_secret", None)

    assert session._verify_signed_session_id(f"synthetic-session.{signature}") is None


def test_secret_rotation_invalidates_existing_cookie(monkeypatch):
    monkeypatch.setattr(settings.app, "environment", "production")
    monkeypatch.setattr(
        settings.api, "session_signing_secret", SecretStr(_SYNTHETIC_SESSION_SECRET)
    )
    old_cookie = session._sign_session_id("synthetic-session")

    monkeypatch.setattr(
        settings.api,
        "session_signing_secret",
        SecretStr("synthetic-rotated-session-signing-secret"),
    )

    assert session._verify_signed_session_id(old_cookie) is None
    new_cookie = session._sign_session_id("synthetic-session")
    assert session._verify_signed_session_id(new_cookie) == "synthetic-session"


def test_development_fallback_is_process_random_and_configured_weak_secret_is_rejected(
    monkeypatch,
):
    monkeypatch.setattr(settings.app, "environment", "development")
    monkeypatch.setattr(settings.api, "session_signing_secret", None)
    monkeypatch.setattr(settings.api, "api_keys", _SYNTHETIC_CALLER_KEY)
    fallback = session._get_signing_key()

    monkeypatch.setattr(settings.api, "api_keys", "synthetic-another-caller-key")
    assert len(fallback) >= 32
    assert session._get_signing_key() == fallback
    assert fallback != _SYNTHETIC_CALLER_KEY.encode()

    monkeypatch.setattr(settings.api, "session_signing_secret", SecretStr("synthetic-short"))
    with pytest.raises(RuntimeError, match="at least 32"):
        session._get_signing_key()
