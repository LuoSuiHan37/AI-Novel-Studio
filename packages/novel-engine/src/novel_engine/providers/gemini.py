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
)

_DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    default_embedding_model = "text-embedding-004"

    def __init__(
        self,
        config: ProviderConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(config)
        if not config.revealed_api_key():
            raise ProviderAuthError("gemini API key is missing")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=config.base_url or _DEFAULT_BASE,
            timeout=httpx.Timeout(config.timeout),
            headers=self._headers(),
        )

    def _headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self.config.revealed_api_key(),
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
        payload = self._payload(messages, json_mode=json_mode, temperature=temperature)
        data = await self._post(f"/models/{self.config.model}:generateContent", payload)
        text = _candidate_text(data)
        usage = data.get("usageMetadata") or {}
        return GenerateResult(
            text=text,
            usage=build_usage(
                model=self.config.model,
                input_tokens=int(usage.get("promptTokenCount") or 0),
                output_tokens=int(usage.get("candidatesTokenCount") or 0),
                started_at=started,
            ),
            model=self.config.model,
            provider=self.name,
            finish_reason=_finish_reason(data),
        )

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[StreamChunk]:
        started = time.perf_counter()
        payload = self._payload(messages, json_mode=False)
        input_tokens = 0
        output_tokens = 0
        path = f"/models/{self.config.model}:streamGenerateContent?alt=sse"
        try:
            async with self._client.stream(
                "POST",
                self._url(path),
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
                        raise ProviderInvalidResponseError("invalid Gemini SSE JSON") from exc
                    usage = event.get("usageMetadata") or {}
                    if usage:
                        input_tokens = int(usage.get("promptTokenCount") or input_tokens)
                        output_tokens = int(usage.get("candidatesTokenCount") or output_tokens)
                    delta = _candidate_text(event)
                    if delta:
                        yield StreamChunk(text=delta)
        except httpx.HTTPError as exc:
            map_httpx_error(exc, provider=self.name)
            raise
        yield StreamChunk(
            text="",
            done=True,
            usage=build_usage(
                model=self.config.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                started_at=started,
            ),
        )

    async def embed(self, texts: str | Sequence[str]) -> EmbedResult:
        started = time.perf_counter()
        inputs = [texts] if isinstance(texts, str) else list(texts)
        model = self.config.embedding_model or self.default_embedding_model
        requests = [{"model": f"models/{model}", "content": {"parts": [{"text": item}]}} for item in inputs]
        data = await self._post(f"/models/{model}:batchEmbedContents", {"requests": requests})
        embeddings = [row.get("values") or [] for row in data.get("embeddings") or []]
        if not embeddings:
            raise ProviderInvalidResponseError("gemini embedding response was empty")
        total = sum(len(item) for item in inputs)
        return EmbedResult(
            embeddings=embeddings,
            usage=build_usage(
                model=model,
                input_tokens=total,
                output_tokens=0,
                started_at=started,
            ),
            model=model,
            provider=self.name,
        )

    def _payload(
        self,
        messages: Sequence[ChatMessage],
        *,
        json_mode: bool,
        temperature: float | None = None,
    ) -> dict:
        system_parts = [item.content for item in messages if item.role == "system"]
        contents: list[dict] = []
        for item in messages:
            if item.role == "system":
                continue
            role = "model" if item.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": item.content}]})
        if not contents:
            raise ProviderInvalidResponseError("Gemini requires at least one user message")
        generation: dict = {
            "temperature": self.config.temperature if temperature is None else temperature
        }
        max_tokens = request_max_tokens(self.config.max_tokens)
        if max_tokens is not None:
            generation["maxOutputTokens"] = max_tokens
        if json_mode:
            generation["responseMimeType"] = "application/json"
        payload: dict = {"contents": contents, "generationConfig": generation}
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
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
            raise ProviderInvalidResponseError("gemini returned non-JSON body") from exc

    def _url(self, path: str) -> str:
        if self._owns_client:
            if not path.startswith("/"):
                return "/" + path
            return path
        return f"{self._base()}{path if path.startswith('/') else '/' + path}"

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _candidate_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    return "".join(part.get("text") or "" for part in parts)


def _finish_reason(data: dict) -> str | None:
    candidates = data.get("candidates") or []
    if not candidates:
        return None
    return candidates[0].get("finishReason")
