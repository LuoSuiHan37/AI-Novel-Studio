from __future__ import annotations

import httpx

from novel_engine.models.enums import LLMProvider as LLMProviderName
from novel_engine.providers.anthropic import AnthropicProvider
from novel_engine.providers.base import LLMProvider
from novel_engine.providers.errors import ProviderInvalidResponseError
from novel_engine.providers.gemini import GeminiProvider
from novel_engine.providers.openai_compatible import (
    CustomOpenAICompatibleProvider,
    DeepSeekProvider,
    GrokProvider,
    OpenAIProvider,
)
from novel_engine.providers.types import ProviderConfig


def create_provider(
    config: ProviderConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> LLMProvider:
    if config.provider is LLMProviderName.OPENAI:
        return OpenAIProvider(config, client=client)
    if config.provider is LLMProviderName.ANTHROPIC:
        return AnthropicProvider(config, client=client)
    if config.provider is LLMProviderName.GEMINI:
        return GeminiProvider(config, client=client)
    if config.provider is LLMProviderName.DEEPSEEK:
        return DeepSeekProvider(config, client=client)
    if config.provider is LLMProviderName.GROK:
        return GrokProvider(config, client=client)
    if config.provider is LLMProviderName.OPENAI_COMPATIBLE:
        return CustomOpenAICompatibleProvider(config, client=client)
    raise ProviderInvalidResponseError(f"unsupported provider: {config.provider}")
