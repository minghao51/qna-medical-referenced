"""API request/response schemas."""


from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(
        None,
        min_length=1,
        max_length=128,
        description="Deprecated. Session ownership is determined by a server-issued cookie.",
    )
    user_context: str | None = None

    @field_validator("message", mode="before")
    @classmethod
    def sanitize_message(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("session_id", mode="before")
    @classmethod
    def sanitize_session_id(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class ChatSource(BaseModel):
    canonical_label: str
    display_label: str
    source_url: str | None = None
    source_type: str = "other"
    source_class: str = "unknown"
    domain: str | None = None
    domain_type: str = "unknown"
    label: str
    source: str
    url: str | None = None
    page: int | None = None
    content_type: str | None = None


class ChatResponse(BaseModel):
    response: str
    sources: list[ChatSource]
