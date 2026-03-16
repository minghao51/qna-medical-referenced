"""API request/response schemas."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field("default", min_length=1, max_length=128)
    user_context: Optional[str] = None

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
    label: str
    source: str
    url: Optional[str] = None
    page: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    sources: list[ChatSource]
