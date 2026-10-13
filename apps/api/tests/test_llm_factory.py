from pydantic import SecretStr

from app.core.config import Settings
from app.llm.factory import provider_config_from_settings
from novel_engine.models.enums import LLMProvider as LLMProviderName


def test_settings_map_to_provider_config(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-3-5-haiku-latest")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.4")
    monkeypatch.setenv("LLM_TIMEOUT", "12.5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    settings = Settings(_env_file=None)
    config = provider_config_from_settings(settings)
    assert config.provider is LLMProviderName.ANTHROPIC
    assert config.model == "claude-3-5-haiku-latest"
    assert config.temperature == 0.4
    assert config.timeout == 12.5
    assert isinstance(config.api_key, SecretStr)
    assert config.revealed_api_key() == "sk-ant-test"
    assert "sk-ant-test" not in repr(config)


def test_deepseek_gemini_grok_defaults(monkeypatch) -> None:
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)

    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek")
    deepseek = provider_config_from_settings(Settings(_env_file=None))
    assert deepseek.provider is LLMProviderName.DEEPSEEK
    assert deepseek.model == "deepseek-chat"
    assert deepseek.base_url == "https://api.deepseek.com/v1"
    assert deepseek.revealed_api_key() == "sk-deepseek"

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "sk-gemini")
    gemini = provider_config_from_settings(Settings(_env_file=None))
    assert gemini.provider is LLMProviderName.GEMINI
    assert gemini.model == "gemini-2.0-flash"
    assert gemini.revealed_api_key() == "sk-gemini"

    monkeypatch.setenv("LLM_PROVIDER", "grok")
    monkeypatch.setenv("GROK_API_KEY", "sk-grok")
    grok = provider_config_from_settings(Settings(_env_file=None))
    assert grok.provider is LLMProviderName.GROK
    assert grok.model == "grok-3-mini"
    assert grok.base_url == "https://api.x.ai/v1"
    assert grok.revealed_api_key() == "sk-grok"
