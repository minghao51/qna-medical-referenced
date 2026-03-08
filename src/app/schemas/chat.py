"""API request/response schemas."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = "default"
    user_context: Optional[str] = None

    @field_validator("message", mode="before")
    @classmethod
    def sanitize_message(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class ChatResponse(BaseModel):
    response: str
    sources: list[str]
