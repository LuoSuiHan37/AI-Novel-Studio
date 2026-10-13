from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Sequence

import httpx

from novel_engine.providers.base import LLMProvider, build_usage, request_max_tokens
from novel_engine.providers.errors import ProviderAuthError, ProviderInvalidResponseError
from novel_engine.providers.http import map_httpx_error, raise_for_status
from novel_engine.providers.types import (
    ChatMessage,
    EmbedResult,
    GenerateResult,
    ProviderConfig,
    StreamChunk,
    as_message_list,
)

_DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"


class OpenAICompatibleProvider(LLMProvider):
    """Chat Completions + Embeddings protocol used by OpenAI, DeepSeek, and custom gateways."""

    default_base_url = _DEFAULT_OPENAI_BASE
    default_embedding_model = "text-embedding-3-small"

    def __init__(
        self,
        config: ProviderConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(config)
        if not config.revealed_api_key():
            raise ProviderAuthError(f"{self.name} API key is missing")
        self._owns_client = client is None
        timeout = httpx.Timeout(config.timeout)
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url(),
            timeout=timeout,
            headers=self._headers(),
        )

    def _base_url(self) -> str:
        return self.config.base_url or self.default_base_url

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.revealed_api_key()}",
            "Content-Type": "application/json",
        }

    def _embedding_model(self) -> str:
        return self.config.embedding_model or self.default_embedding_model

    async def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> GenerateResult:
        started = time.perf_counter()
        payload = self._chat_payload(
            messages, stream=False, json_mode=json_mode, temperature=temperature
        )
        data = await self._post("/chat/completions", payload)
        choice = _first_choice(data)
        message = choice.get("message") or {}
        text = _message_content(message)
        usage = data.get("usage") or {}
        model = data.get("model") or self.config.model
        return GenerateResult(
            text=text,
            usage=build_usage(
                model=model,
                input_tokens=int(usage.get("prompt_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or 0),
                started_at=started,
            ),
            model=model,
            provider=self.name,
            finish_reason=choice.get("finish_reason"),
        )

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[StreamChunk]:
        started = time.perf_counter()
        payload = self._chat_payload(messages, stream=True, json_mode=False)
        payload["stream_options"] = {"include_usage": True}
        input_tokens = 0
        output_tokens = 0
        model = self.config.model
        try:
            async with self._client.stream(
                "POST",
                self._join("/chat/completions"),
                json=payload,
                headers=self._headers(),
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                raise_for_status(response, provider=self.name)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError as exc:
                        raise ProviderInvalidResponseError("invalid SSE JSON") from exc
                    model = event.get("model") or model
                    usage = event.get("usage") or {}
                    if usage:
                        input_tokens = int(usage.get("prompt_tokens") or input_tokens)
                        output_tokens = int(usage.get("completion_tokens") or output_tokens)
                    choice = (event.get("choices") or [{}])[0]
                    delta = (choice.get("delta") or {}).get("content") or ""
                    if delta:
                        yield StreamChunk(text=delta)
        except httpx.HTTPError as exc:
            map_httpx_error(exc, provider=self.name)
            raise
        yield StreamChunk(
            text="",
            done=True,
            usage=build_usage(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                started_at=started,
            ),
        )

    async def embed(self, texts: str | Sequence[str]) -> EmbedResult:
        started = time.perf_counter()
        inputs = [texts] if isinstance(texts, str) else list(texts)
        data = await self._post(
            "/embeddings",
            {"model": self._embedding_model(), "input": inputs},
        )
        items = sorted(data.get("data") or [], key=lambda row: row.get("index", 0))
        vectors = [row.get("embedding") or [] for row in items]
        if not vectors:
            raise ProviderInvalidResponseError(f"{self.name} embedding response was empty")
        usage = data.get("usage") or {}
        model = data.get("model") or self._embedding_model()
        return EmbedResult(
            embeddings=vectors,
            usage=build_usage(
                model=model,
                input_tokens=int(usage.get("prompt_tokens") or usage.get("total_tokens") or 0),
                output_tokens=0,
                started_at=started,
            ),
            model=model,
            provider=self.name,
        )

    def _chat_payload(
        self,
        messages: Sequence[ChatMessage],
        *,
        stream: bool,
        json_mode: bool,
        temperature: float | None = None,
    ) -> dict:
        payload: dict = {
            "model": self.config.model,
            "messages": as_message_list(messages),
            "temperature": self.config.temperature if temperature is None else temperature,
            "stream": stream,
        }
        max_tokens = request_max_tokens(self.config.max_tokens)
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            response = await self._client.post(
                self._join(path),
                json=payload,
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            map_httpx_error(exc, provider=self.name)
            raise
        raise_for_status(response, provider=self.name)
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise ProviderInvalidResponseError(f"{self.name} returned non-JSON body") from exc

    def _join(self, path: str) -> str:
        if self._owns_client:
            return path
        return f"{self._base_url()}{path}"

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class OpenAIProvider(OpenAICompatibleProvider):
    default_base_url = _DEFAULT_OPENAI_BASE


class DeepSeekProvider(OpenAICompatibleProvider):
    default_base_url = "https://api.deepseek.com/v1"
    default_embedding_model = "text-embedding-3-small"


class GrokProvider(OpenAICompatibleProvider):
    """xAI Grok — OpenAI-compatible Chat Completions at api.x.ai."""

    default_base_url = "https://api.x.ai/v1"
    default_embedding_model = "text-embedding-3-small"


class CustomOpenAICompatibleProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        config: ProviderConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not config.base_url:
            raise ProviderInvalidResponseError(
                "openai_compatible provider requires base_url"
            )
        super().__init__(config, client=client)


def _first_choice(data: dict) -> dict:
    choices = data.get("choices") or []
    if not choices:
        raise ProviderInvalidResponseError("chat completion contained no choices")
    return choices[0]


def _message_content(message: dict) -> str:
    """Normalize OpenAI-compatible string or segmented message content."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""
