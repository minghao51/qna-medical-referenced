"""API configuration."""

from pydantic import BaseModel


class ApiConfig(BaseModel):
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000"
    max_message_length: int = 2000
    api_keys: str | None = None
    api_keys_json: str | None = None
    rate_limit_per_minute: int = 60
    anonymous_chat_rate_limit_per_minute: int = 12
    rate_limit_bypass_key_ids: str = ""
    rate_limit_bypass_roles: str = ""
    anonymous_browser_cookie_name: str = "anon_browser_id"
    chat_session_cookie_name: str = "chat_session_id"
    chat_session_cookie_max_age_seconds: int = 2592000
    chat_history_ttl_seconds: int = 2592000
    trust_proxy_headers: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def rate_limit_bypass_key_id_set(self) -> set[str]:
        return {v.strip() for v in self.rate_limit_bypass_key_ids.split(",") if v.strip()}

    @property
    def rate_limit_bypass_role_set(self) -> set[str]:
        return {v.strip() for v in self.rate_limit_bypass_roles.split(",") if v.strip()}
