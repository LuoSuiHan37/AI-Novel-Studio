from __future__ import annotations

import os

from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.db.models.llm import LLMConfig
from novel_engine.models.enums import LLMProvider as LLMProviderName
from novel_engine.providers import LLMProvider, ProviderConfig, create_provider


def resolve_api_key(settings: Settings, provider: LLMProviderName, env_name: str | None = None) -> str:
    if env_name:
        return os.environ.get(env_name, "")
    mapping = {
        LLMProviderName.OPENAI: settings.openai_api_key,
        LLMProviderName.OPENAI_COMPATIBLE: settings.openai_api_key,
        LLMProviderName.ANTHROPIC: settings.anthropic_api_key,
        LLMProviderName.GEMINI: settings.gemini_api_key,
        LLMProviderName.DEEPSEEK: settings.deepseek_api_key,
        LLMProviderName.GROK: settings.grok_api_key,
    }
    return mapping.get(provider, "")


def resolve_row_api_key(settings: Settings, row: LLMConfig | None) -> str:
    if row is None:
        return ""
    if row.api_key:
        return row.api_key
    return resolve_api_key(settings, LLMProviderName(row.provider), row.api_key_env_name)


def resolve_base_url(settings: Settings, provider: LLMProviderName) -> str | None:
    if settings.llm_base_url:
        return settings.llm_base_url
    if provider is LLMProviderName.OPENAI:
        return settings.openai_base_url or None
    if provider is LLMProviderName.OPENAI_COMPATIBLE:
        return settings.openai_base_url or None
    if provider is LLMProviderName.ANTHROPIC:
        return settings.anthropic_base_url or None
    if provider is LLMProviderName.GEMINI:
        return settings.gemini_base_url or None
    if provider is LLMProviderName.DEEPSEEK:
        return settings.deepseek_base_url or None
    if provider is LLMProviderName.GROK:
        return settings.grok_base_url or None
    return None


def resolve_model(settings: Settings, provider: LLMProviderName) -> str:
    if settings.llm_model:
        return settings.llm_model
    defaults = {
        LLMProviderName.OPENAI: settings.openai_model or "gpt-4o-mini",
        LLMProviderName.OPENAI_COMPATIBLE: settings.openai_model or "gpt-4o-mini",
        LLMProviderName.ANTHROPIC: settings.anthropic_model or "claude-3-5-sonnet-latest",
        LLMProviderName.GEMINI: settings.gemini_model or "gemini-2.0-flash",
        LLMProviderName.DEEPSEEK: settings.deepseek_model or "deepseek-chat",
        LLMProviderName.GROK: settings.grok_model or "grok-3-mini",
    }
    return defaults[provider]


def _review_model(settings: Settings, provider: LLMProviderName) -> str:
    """Resolve a reviewer model without inheriting the generation override."""
    defaults = {
        LLMProviderName.OPENAI: settings.openai_model or "gpt-4o-mini",
        LLMProviderName.OPENAI_COMPATIBLE: settings.openai_model or "gpt-4o-mini",
        LLMProviderName.ANTHROPIC: settings.anthropic_model or "claude-3-5-sonnet-latest",
        LLMProviderName.GEMINI: settings.gemini_model or "gemini-2.0-flash",
        LLMProviderName.DEEPSEEK: settings.deepseek_model or "deepseek-chat",
        LLMProviderName.GROK: settings.grok_model or "grok-3-mini",
    }
    return defaults[provider]


def provider_config_from_settings(
    settings: Settings | None = None,
    *,
    row: LLMConfig | None = None,
) -> ProviderConfig:
    settings = settings or get_settings()
    if row is not None:
        provider = LLMProviderName(row.provider)
        return ProviderConfig(
            provider=provider,
            model=row.model,
            api_key=_secret(resolve_row_api_key(settings, row)),
            base_url=row.base_url or resolve_base_url(settings, provider),
            temperature=row.temperature,
            max_tokens=row.max_tokens,
            timeout=settings.llm_timeout,
            embedding_model=settings.llm_embedding_model or None,
        )
    provider = LLMProviderName(settings.llm_provider)
    return ProviderConfig(
        provider=provider,
        model=resolve_model(settings, provider),
        api_key=_secret(resolve_api_key(settings, provider)),
        base_url=resolve_base_url(settings, provider),
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout,
        embedding_model=settings.llm_embedding_model or None,
    )


def llm_provider_from_settings(
    settings: Settings | None = None,
    *,
    row: LLMConfig | None = None,
) -> LLMProvider:
    return create_provider(provider_config_from_settings(settings, row=row))


def reviewer_provider_config_from_settings(settings: Settings) -> ProviderConfig | None:
    """Build the optional independent review provider from REVIEW_* settings."""
    if not settings.review_provider.strip():
        return None
    provider = LLMProviderName(settings.review_provider.strip().lower())
    base = provider_config_from_settings(settings)
    return base.model_copy(
        update={
            "provider": provider,
            "model": settings.review_model or _review_model(settings, provider),
            "api_key": _secret(settings.review_api_key) or _secret(resolve_api_key(settings, provider)),
            "base_url": settings.review_base_url or resolve_base_url(settings, provider),
            "temperature": 0.2,
            "max_tokens": min(settings.llm_max_tokens or 4096, 4096),
        }
    )


def _secret(value: str) -> SecretStr | None:
    return SecretStr(value) if value else None
