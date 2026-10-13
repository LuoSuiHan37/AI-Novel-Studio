from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from novel_engine.models.enums import LLMProvider as LLMProviderName


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ProviderConfig(BaseModel):
    """Runtime LLM settings. API keys come from env/secrets, never from source."""

    model_config = ConfigDict(extra="forbid")

    provider: LLMProviderName
    model: str
    api_key: SecretStr | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = 4096
    timeout: float = 60.0
    embedding_model: str | None = None

    @field_validator("base_url")
    @classmethod
    def _strip_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().rstrip("/")
        return stripped or None

    def revealed_api_key(self) -> str:
        if self.api_key is None:
            return ""
        return self.api_key.get_secret_value()

    def __repr__(self) -> str:
        return (
            f"ProviderConfig(provider={self.provider!r}, model={self.model!r}, "
            f"base_url={self.base_url!r}, temperature={self.temperature}, "
            f"max_tokens={self.max_tokens}, timeout={self.timeout}, api_key='***')"
        )


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: float = 0.0


class GenerateResult(BaseModel):
    text: str
    usage: TokenUsage
    model: str
    provider: str
    finish_reason: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class StreamChunk(BaseModel):
    text: str = ""
    done: bool = False
    usage: TokenUsage | None = None


class EmbedResult(BaseModel):
    embeddings: list[list[float]]
    usage: TokenUsage
    model: str
    provider: str


def as_message_list(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    return [item.model_dump() for item in messages]
