from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import httpx
import pytest
from pydantic import BaseModel, SecretStr

from novel_engine.models.enums import LLMProvider as LLMProviderName
from novel_engine.providers import (
    AnthropicProvider,
    ChatMessage,
    CustomOpenAICompatibleProvider,
    DeepSeekProvider,
    GeminiProvider,
    GrokProvider,
    LLMProvider,
    OpenAIProvider,
    ProviderAuthError,
    ProviderConfig,
    ProviderInvalidResponseError,
    ProviderRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnsupportedError,
    StreamChunk,
    TokenUsage,
    create_provider,
)
from novel_engine.providers.types import EmbedResult, GenerateResult


def _config(provider: LLMProviderName, **overrides) -> ProviderConfig:
    data = {
        "provider": provider,
        "model": "test-model",
        "api_key": "sk-test-not-real",
        "timeout": 5.0,
        "temperature": 0.2,
        "max_tokens": 128,
    }
    data.update(overrides)
    return ProviderConfig(**data)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


USER = [ChatMessage(role="user", content="Write a one-line hook.")]


class HookSchema(BaseModel):
    hook: str
    importance: str


class ScriptedProvider(LLMProvider):
    def __init__(self, replies: list[str]) -> None:
        super().__init__(_config(LLMProviderName.OPENAI))
        self._replies = replies
        self.calls = 0

    async def generate(self, messages, *, json_mode: bool = False, temperature: float | None = None) -> GenerateResult:
        text = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return GenerateResult(
            text=text,
            usage=TokenUsage(input_tokens=10, output_tokens=5, estimated_cost=0.001, latency_ms=2.0),
            model="test-model",
            provider="openai",
        )

    async def stream(self, messages) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(text="", done=True, usage=TokenUsage())

    async def embed(self, texts: str | Sequence[str]) -> EmbedResult:
        raise ProviderUnsupportedError("scripted provider has no embeddings")


def test_factory_routes_providers() -> None:
    dummy = _client(lambda _request: httpx.Response(500))
    assert isinstance(
        create_provider(_config(LLMProviderName.OPENAI), client=dummy), OpenAIProvider
    )
    assert isinstance(
        create_provider(_config(LLMProviderName.ANTHROPIC), client=dummy), AnthropicProvider
    )
    assert isinstance(
        create_provider(_config(LLMProviderName.GEMINI), client=dummy), GeminiProvider
    )
    assert isinstance(
        create_provider(_config(LLMProviderName.DEEPSEEK), client=dummy), DeepSeekProvider
    )
    assert isinstance(
        create_provider(_config(LLMProviderName.GROK), client=dummy), GrokProvider
    )
    custom = create_provider(
        _config(LLMProviderName.OPENAI_COMPATIBLE, base_url="https://gateway.example/v1"),
        client=dummy,
    )
    assert isinstance(custom, CustomOpenAICompatibleProvider)


def test_factory_requires_custom_base_url() -> None:
    with pytest.raises(ProviderInvalidResponseError, match="base_url"):
        create_provider(_config(LLMProviderName.OPENAI_COMPATIBLE))


def test_missing_api_key() -> None:
    with pytest.raises(ProviderAuthError):
        OpenAIProvider(_config(LLMProviderName.OPENAI, api_key=None))


def test_config_repr_hides_key() -> None:
    cfg = _config(LLMProviderName.OPENAI, api_key="sk-secret-value")
    assert "sk-secret-value" not in repr(cfg)
    assert isinstance(cfg.api_key, SecretStr)


@pytest.mark.asyncio
async def test_openai_generate_usage_and_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "model": "gpt-4o-mini",
                    "choices": [
                        {"message": {"content": "She walked out of the pack hall."}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 8},
                },
            )
        return httpx.Response(404)

    provider = OpenAIProvider(_config(LLMProviderName.OPENAI), client=_client(handler))
    result = await provider.generate(USER)
    assert "pack hall" in result.text
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 8
    assert result.usage.latency_ms >= 0
    assert result.usage.estimated_cost > 0

    def unauthorized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    auth_provider = OpenAIProvider(_config(LLMProviderName.OPENAI), client=_client(unauthorized))
    with pytest.raises(ProviderAuthError):
        await auth_provider.generate(USER)

    def limited(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "slow down"}})

    limited_provider = OpenAIProvider(_config(LLMProviderName.OPENAI), client=_client(limited))
    with pytest.raises(ProviderRateLimitError):
        await limited_provider.generate(USER)

    failed_provider = OpenAIProvider(
        _config(LLMProviderName.OPENAI),
        client=_client(lambda _request: httpx.Response(400, json={"error": {"message": "bad request"}})),
    )
    with pytest.raises(ProviderRequestError, match="HTTP 400"):
        await failed_provider.generate(USER)

    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    timeout_provider = OpenAIProvider(_config(LLMProviderName.OPENAI), client=_client(boom))
    with pytest.raises(ProviderTimeoutError):
        await timeout_provider.generate(USER)


@pytest.mark.asyncio
async def test_openai_stream_and_embed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat/completions"):
            body = (
                'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":" Luna"}}],'
                '"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\n'
                "data: [DONE]\n\n"
            )
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(
                200,
                json={
                    "model": "text-embedding-3-small",
                    "data": [{"index": 0, "embedding": [0.1, 0.2]}],
                    "usage": {"prompt_tokens": 3, "total_tokens": 3},
                },
            )
        return httpx.Response(404)

    provider = OpenAIProvider(_config(LLMProviderName.OPENAI), client=_client(handler))
    chunks = [chunk async for chunk in provider.stream(USER)]
    text = "".join(item.text for item in chunks)
    assert text == "Hello Luna"
    assert chunks[-1].done is True
    assert chunks[-1].usage is not None
    assert chunks[-1].usage.input_tokens == 4

    embedded = await provider.embed("rejected mate")
    assert embedded.embeddings == [[0.1, 0.2]]
    assert embedded.usage.input_tokens == 3


@pytest.mark.asyncio
async def test_anthropic_generate_and_embed_unsupported() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "claude-3-5-sonnet",
                "content": [{"type": "text", "text": "The Alpha froze."}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 9, "output_tokens": 6},
            },
        )

    provider = AnthropicProvider(_config(LLMProviderName.ANTHROPIC), client=_client(handler))
    result = await provider.generate(USER)
    assert result.text == "The Alpha froze."
    assert result.usage.input_tokens == 9
    with pytest.raises(ProviderUnsupportedError):
        await provider.embed("text")


@pytest.mark.asyncio
async def test_gemini_generate() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "She kept the secret."}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 7},
            },
        )

    provider = GeminiProvider(_config(LLMProviderName.GEMINI), client=_client(handler))
    result = await provider.generate(USER)
    assert "secret" in result.text
    assert result.usage.output_tokens == 7


@pytest.mark.asyncio
async def test_generate_json_success_and_repair() -> None:
    ok = ScriptedProvider(['{"hook": "He rejected her at dawn.", "importance": "high"}'])
    parsed, usage_result = await ok.generate_json(USER, HookSchema)
    assert parsed.hook.startswith("He rejected")
    assert usage_result.usage.input_tokens == 10

    repaired = ScriptedProvider(
        [
            "not json",
            '{"hook": "The pack will remember.", "importance": "critical"}',
        ]
    )
    parsed, merged = await repaired.generate_json(USER, HookSchema)
    assert parsed.importance == "critical"
    assert repaired.calls == 2
    assert merged.usage.input_tokens == 20

    failed = ScriptedProvider(["nope", "still nope"])
    with pytest.raises(ProviderInvalidResponseError, match="repair"):
        await failed.generate_json(USER, HookSchema)
    assert failed.calls == 2


@pytest.mark.asyncio
async def test_json_repair_expands_output_budget() -> None:
    budgets: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        budgets.append(payload["max_tokens"])
        if len(budgets) < 3:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": '{"hook": "unfinished'}, "finish_reason": "length"}
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 128},
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"hook": "complete", "importance": "high"}'
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 10},
            },
        )

    provider = OpenAIProvider(_config(LLMProviderName.OPENAI), client=_client(handler))
    parsed, _ = await provider.generate_json(USER, HookSchema)

    assert parsed.hook == "complete"
    assert budgets == [128, 8192, 16384]
