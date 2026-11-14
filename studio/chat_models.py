from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: UUID
    expected_revision: int = Field(ge=0, strict=True)
    text: str = Field(min_length=1, max_length=2000)
    mode: Literal["guide", "gemini"] = "guide"

    @field_validator("text")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Nhập câu hỏi trước khi gửi.")
        return value.strip()


class ChatAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=5000)
    source_ids: list[str] = Field(min_length=1, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("answer")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Câu trả lời trống.")
        return value.strip()
