from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Sequence

import httpx

from novel_engine.providers.base import LLMProvider, build_usage, request_max_tokens
from novel_engine.providers.errors import (
    ProviderAuthError,
    ProviderInvalidResponseError,
    ProviderUnsupportedError,
)
from novel_engine.providers.http import map_httpx_error, raise_for_status
from novel_engine.providers.types import (
    ChatMessage,
    EmbedResult,
    GenerateResult,
    ProviderConfig,
    StreamChunk,
)

_DEFAULT_BASE = "https://api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        config: ProviderConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(config)
        if not config.revealed_api_key():
            raise ProviderAuthError("anthropic API key is missing")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=config.base_url or _DEFAULT_BASE,
            timeout=httpx.Timeout(config.timeout),
            headers=self._headers(),
        )

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.config.revealed_api_key(),
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def _base(self) -> str:
        return self.config.base_url or _DEFAULT_BASE

    async def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> GenerateResult:
        started = time.perf_counter()
        payload = self._payload(messages, stream=False, temperature=temperature)
        data = await self._post("/v1/messages", payload)
        text = _content_text(data.get("content") or [])
        usage = data.get("usage") or {}
        model = data.get("model") or self.config.model
        return GenerateResult(
            text=text,
            usage=build_usage(
                model=model,
                input_tokens=int(usage.get("input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
                started_at=started,
            ),
            model=model,
            provider=self.name,
            finish_reason=data.get("stop_reason"),
        )

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[StreamChunk]:
        started = time.perf_counter()
        payload = self._payload(messages, stream=True)
        input_tokens = 0
        output_tokens = 0
        model = self.config.model
        try:
            async with self._client.stream(
                "POST",
                self._url("/v1/messages"),
                json=payload,
                headers=self._headers(),
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                raise_for_status(response, provider=self.name)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise ProviderInvalidResponseError("invalid Anthropic SSE JSON") from exc
                    event_type = event.get("type")
                    if event_type == "content_block_delta":
                        delta = (event.get("delta") or {}).get("text") or ""
                        if delta:
                            yield StreamChunk(text=delta)
                    elif event_type == "message_start":
                        message = event.get("message") or {}
                        model = message.get("model") or model
                        usage = message.get("usage") or {}
                        input_tokens = int(usage.get("input_tokens") or input_tokens)
                    elif event_type == "message_delta":
                        usage = event.get("usage") or {}
                        output_tokens = int(usage.get("output_tokens") or output_tokens)
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
        raise ProviderUnsupportedError(
            "Anthropic does not expose a text-embedding API in this adapter; "
            "configure an OpenAI-compatible embedding provider instead."
        )

    def _payload(
        self,
        messages: Sequence[ChatMessage],
        *,
        stream: bool,
        temperature: float | None = None,
    ) -> dict:
        system_parts = [item.content for item in messages if item.role == "system"]
        converted: list[dict[str, str]] = []
        for item in messages:
            if item.role == "system":
                continue
            role = "assistant" if item.role == "assistant" else "user"
            converted.append({"role": role, "content": item.content})
        if not converted:
            raise ProviderInvalidResponseError("Anthropic requires at least one user message")
        payload: dict = {
            "model": self.config.model,
            "messages": converted,
            "max_tokens": request_max_tokens(self.config.max_tokens) or 4096,
            "temperature": self.config.temperature if temperature is None else temperature,
            "stream": stream,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        return payload

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            response = await self._client.post(
                self._url(path),
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
            raise ProviderInvalidResponseError("anthropic returned non-JSON body") from exc

    def _url(self, path: str) -> str:
        if self._owns_client:
            return path
        return f"{self._base()}{path}"

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _content_text(blocks: list) -> str:
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text") or "")
    return "".join(parts)
