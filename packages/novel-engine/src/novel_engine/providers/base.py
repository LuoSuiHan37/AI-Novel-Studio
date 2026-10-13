from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import AsyncIterator, Sequence
from typing import Iterator, TypeVar

from pydantic import BaseModel

from novel_engine.prompts.loader import load_prompt, render_prompt
from novel_engine.providers.errors import ProviderInvalidResponseError
from novel_engine.providers.json_parse import extract_json_object, parse_model
from novel_engine.providers.types import (
    ChatMessage,
    EmbedResult,
    GenerateResult,
    ProviderConfig,
    StreamChunk,
    TokenUsage,
)
from novel_engine.providers.usage import estimate_cost

TModel = TypeVar("TModel", bound=BaseModel)

_REQUEST_MAX_TOKENS: ContextVar[int | None] = ContextVar(
    "novel_engine_request_max_tokens", default=None
)


def request_max_tokens(default: int | None) -> int | None:
    """Return a per-request token override without mutating shared provider config."""
    override = _REQUEST_MAX_TOKENS.get()
    return override if override is not None else default


@contextmanager
def _with_request_max_tokens(value: int | None) -> Iterator[None]:
    token = _REQUEST_MAX_TOKENS.set(value)
    try:
        yield
    finally:
        _REQUEST_MAX_TOKENS.reset(token)


class LLMProvider(ABC):
    """Vendor-neutral language model port."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.provider.value

    @abstractmethod
    async def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> GenerateResult:
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        messages: Sequence[ChatMessage],
    ) -> AsyncIterator[StreamChunk]:
        raise NotImplementedError

    @abstractmethod
    async def embed(self, texts: str | Sequence[str]) -> EmbedResult:
        raise NotImplementedError

    async def generate_json(
        self,
        messages: Sequence[ChatMessage],
        schema: type[TModel],
        *,
        temperature: float | None = None,
    ) -> tuple[TModel, GenerateResult]:
        schema_json = schema.model_json_schema()
        schema_text = json.dumps(schema_json, ensure_ascii=False, indent=2)
        instruction = render_prompt(
            load_prompt("providers/json_schema_system.txt"),
            schema=schema_text,
        )
        first_messages = [*messages, ChatMessage(role="user", content=instruction)]
        first = await self.generate(first_messages, json_mode=True, temperature=temperature)
        try:
            parsed = parse_model(schema, extract_json_object(first.text))
            return parsed, first
        except ProviderInvalidResponseError as first_error:
            latest = first
            latest_error = first_error
            merged = first

            # A truncated JSON document may itself be truncated again. Retry only
            # length failures, escalating the per-request budget each time. This
            # keeps normal schema repairs at one retry while allowing large nested
            # research proposals to finish. The ContextVar keeps the override
            # safe when one provider instance serves concurrent requests.
            repair_attempts = 0
            while True:
                repair_attempts += 1
                repair = render_prompt(
                    load_prompt("providers/json_repair.txt"),
                    schema=schema_text,
                    error=str(latest_error),
                    output=latest.text,
                )
                repair_budget = _repair_max_tokens(self.config.max_tokens, repair_attempts)
                with _with_request_max_tokens(repair_budget):
                    latest = await self.generate(
                        [*first_messages, ChatMessage(role="user", content=repair)],
                        json_mode=True,
                        temperature=temperature,
                    )
                merged = _merge_usage(merged, latest)
                try:
                    parsed = parse_model(schema, extract_json_object(latest.text))
                    return parsed, merged
                except ProviderInvalidResponseError as error:
                    latest_error = error
                    if not _is_length_truncation(latest) or repair_attempts >= 3:
                        finish_reason = latest.finish_reason or first.finish_reason or "unknown"
                        raise ProviderInvalidResponseError(
                            f"JSON schema validation failed after {repair_attempts} repair attempts: "
                            f"{latest_error}; finish_reason={finish_reason}"
                        ) from error


def _repair_max_tokens(configured: int | None, attempt: int) -> int | None:
    if configured is None:
        return None
    return min(max(configured * (2**attempt), 8192 * (2 ** (attempt - 1))), 32768)


def _is_length_truncation(result: GenerateResult) -> bool:
    reason = (result.finish_reason or "").strip().lower()
    return reason in {"length", "max_tokens", "max_output_tokens", "token_limit"}

    async def aclose(self) -> None:
        return None

    async def __aenter__(self) -> LLMProvider:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()


def build_usage(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    started_at: float,
) -> TokenUsage:
    latency_ms = (time.perf_counter() - started_at) * 1000
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimate_cost(model, input_tokens, output_tokens),
        latency_ms=round(latency_ms, 3),
    )


def _merge_usage(first: GenerateResult, second: GenerateResult) -> GenerateResult:
    usage = TokenUsage(
        input_tokens=first.usage.input_tokens + second.usage.input_tokens,
        output_tokens=first.usage.output_tokens + second.usage.output_tokens,
        estimated_cost=first.usage.estimated_cost + second.usage.estimated_cost,
        latency_ms=round(first.usage.latency_ms + second.usage.latency_ms, 3),
    )
    return second.model_copy(update={"usage": usage})
