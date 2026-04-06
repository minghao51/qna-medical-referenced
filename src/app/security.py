"""Security configuration helpers for auth and deployment defaults."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass

from src.config import settings


@dataclass(frozen=True)
class APIKeyRecord:
    key_id: str
    secret_hash: str
    owner: str | None = None
    role: str | None = None
    status: str = "active"

    def matches(self, presented_key: str) -> bool:
        return hmac.compare_digest(_hash_secret(presented_key), self.secret_hash)


@dataclass(frozen=True)
class AuthContext:
    key_id: str
    owner: str | None = None
    role: str | None = None


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _normalize_record(raw: dict[str, object], index: int) -> APIKeyRecord | None:
    status = str(raw.get("status", "active")).strip().lower()
    if status not in {"active", "disabled", "revoked"}:
        status = "active"
    key_id = str(raw.get("id") or f"key-{index + 1}").strip()
    owner = str(raw.get("owner")).strip() if raw.get("owner") else None
    role = str(raw.get("role")).strip() if raw.get("role") else None
    plaintext = str(raw.get("key", "")).strip()
    hashed = str(raw.get("hash", "")).strip().lower()
    if not key_id or status != "active":
        return None
    if plaintext:
        secret_hash = _hash_secret(plaintext)
    elif len(hashed) == 64 and all(ch in "0123456789abcdef" for ch in hashed):
        secret_hash = hashed
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


def validate_security_configuration() -> None:
    if settings.is_development:
        return
    if not load_api_key_records():
        raise RuntimeError("API keys must be configured outside development mode")
