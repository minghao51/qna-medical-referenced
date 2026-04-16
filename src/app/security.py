"""Security configuration helpers for auth and deployment defaults."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass

import bcrypt

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class APIKeyRecord:
    key_id: str
    secret_hash: str
    owner: str | None = None
    role: str | None = None
    status: str = "active"

    def matches(self, presented_key: str) -> bool:
        """Compare presented key against stored hash using constant-time comparison.

        Supports both bcrypt hashes and legacy SHA256 hashes for backward compatibility.
        """
        return _verify_secret(presented_key, self.secret_hash)


@dataclass(frozen=True)
class AuthContext:
    key_id: str
    owner: str | None = None
    role: str | None = None


def _hash_secret(secret: str) -> str:
    """Hash a secret using bcrypt with automatic salt generation.

    Returns a bcrypt hash string that includes the salt and cost factor.
    Format: $2b$12$<22-char-salt><31-char-hash>
    """
    return _hash_secret_bcrypt(secret)


def _hash_secret_bcrypt(secret: str, rounds: int = 12) -> str:
    """Hash a secret using bcrypt with the specified cost factor.

    Args:
        secret: The plaintext secret to hash
        rounds: Cost factor (default 12, range 4-31)

    Returns:
        Bcrypt hash string
    """
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(secret.encode("utf-8"), salt).decode("utf-8")


def _hash_secret_legacy(secret: str) -> str:
    """Legacy SHA256 hashing (NO SALT) kept only for backward compatibility.

    DEPRECATED: Unsalted SHA256 is cryptographically insecure. This function exists
    only to verify existing legacy hashes. All new keys must use bcrypt.

    Migration path:
        1. Re-hash all keys using _hash_secret_bcrypt()
        2. Update API_KEYS_JSON with new bcrypt hashes
        3. Remove this function after all keys are migrated

    Timeline: Legacy hash support will be removed in a future release.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _verify_secret(secret: str, hashed: str) -> bool:
    """Verify a secret against a hash, supporting both bcrypt and legacy SHA256.

    Automatically detects hash format and uses appropriate verification.
    Bcrypt hashes start with "$2b$", "$2a$", or "$2y$".
    Legacy SHA256 hashes are 64 hex characters.

    Args:
        secret: The plaintext secret to verify
        hashed: The stored hash string

    Returns:
        True if the secret matches the hash

    Note:
        Logs a deprecation warning when legacy SHA256 hashes are used.
        Migrate to bcrypt for improved security.
    """
    if hashed.startswith(("$2b$", "$2a$", "$2y$")):
        try:
            return bcrypt.checkpw(secret.encode("utf-8"), hashed.encode("utf-8"))
        except (ValueError, TypeError):
            return False
    if len(hashed) == 64 and all(c in "0123456789abcdef" for c in hashed):
        logger.warning(
            "Authenticating with legacy SHA256 hash. This is deprecated for security reasons. "
            "Please migrate to bcrypt. Use upgrade_legacy_keys_to_bcrypt() to upgrade your keys."
        )
        return hmac.compare_digest(_hash_secret_legacy(secret), hashed)
    return False


def _normalize_record(raw: dict[str, object], index: int) -> APIKeyRecord | None:
    status = str(raw.get("status", "active")).strip().lower()
    if status not in {"active", "disabled", "revoked"}:
        status = "active"
    key_id = str(raw.get("id") or f"key-{index + 1}").strip()
    owner = str(raw.get("owner")).strip() if raw.get("owner") else None
    role = str(raw.get("role")).strip() if raw.get("role") else None
    plaintext = str(raw.get("key", "")).strip()
    hashed = str(raw.get("hash", "")).strip()
    if not key_id or status != "active":
        return None
    if plaintext:
        secret_hash = _hash_secret(plaintext)
    elif hashed.startswith(("$2b$", "$2a$", "$2y$")):
        secret_hash = hashed
    elif len(hashed) == 64 and all(ch in "0123456789abcdef" for ch in hashed.lower()):
        secret_hash = hashed.lower()
        logger.warning(
            "Loaded legacy SHA256 API key hash for key_id=%s. "
            "This is deprecated and will be removed in a future release. "
            "Migrate to bcrypt using the upgrade_legacy_keys_to_bcrypt() function.",
            key_id,
        )
    else:
        return None
    return APIKeyRecord(
        key_id=key_id,
        secret_hash=secret_hash,
        owner=owner,
        role=role,
        status=status,
    )


def load_api_key_records() -> list[APIKeyRecord]:
    records: list[APIKeyRecord] = []
    if settings.api_keys_json:
        try:
            payload = json.loads(settings.api_keys_json)
        except json.JSONDecodeError:
            payload = []
        if isinstance(payload, list):
            for idx, raw in enumerate(payload):
                if isinstance(raw, dict):
                    record = _normalize_record(raw, idx)
                    if record:
                        records.append(record)
    elif settings.api_keys:
        for idx, value in enumerate(settings.api_keys.split(",")):
            key = value.strip()
            if not key:
                continue
            records.append(
                APIKeyRecord(
                    key_id=f"key-{idx + 1}",
                    secret_hash=_hash_secret(key),
                )
            )
    return records


def upgrade_legacy_keys_to_bcrypt(api_keys_json: str) -> list[dict]:
    """Upgrade JSON API-key records to bcrypt hashes when plaintext keys are available."""
    try:
        payload = json.loads(api_keys_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    upgraded = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        key_id = str(raw.get("id", ""))
        plaintext = str(raw.get("key", "")).strip()
        if not key_id or not plaintext:
            continue
        upgraded.append(
            {
                "id": key_id,
                "hash": _hash_secret(plaintext),
                "owner": raw.get("owner"),
                "role": raw.get("role"),
                "status": raw.get("status", "active"),
            }
        )
    return upgraded


def generate_api_key_record(key_id: str, plaintext: str, **kwargs) -> dict:
    """Generate a new API key record with a bcrypt hash."""
    return {
        "id": key_id,
        "hash": _hash_secret(plaintext),
        **kwargs,
    }


def validate_security_configuration() -> None:
    if settings.is_development:
        return
    if not load_api_key_records():
        raise RuntimeError("API keys must be configured outside development mode")
