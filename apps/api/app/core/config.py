from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ENV_FILES = (
    str(Path.cwd() / ".env"),
    str(_REPO_ROOT / ".env"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ai-novel-studio-api"
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # Single shared gateway token until a real identity provider is integrated.
    # Production refuses to start without it.
    api_auth_token: str = ""
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001,"
        "http://localhost:3020,http://127.0.0.1:3020,"
        "http://localhost:3010,http://127.0.0.1:3010"
    )

    database_url: str = (
        "postgresql+asyncpg://novel:novel@localhost:5433/ai_novel_studio"
    )
    database_connect_timeout: float = 10.0
    save_root: str = str(_REPO_ROOT / "save")

    llm_provider: str = "deepseek"
    llm_model: str = ""
    llm_temperature: float = 0.7
    llm_max_tokens: int | None = 4096
    llm_timeout: float = 60.0
    llm_base_url: str = ""
    llm_embedding_model: str = "text-embedding-3-small"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    anthropic_model: str = ""
    gemini_api_key: str = ""
    gemini_base_url: str = ""
    gemini_model: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = ""
    grok_api_key: str = ""
    grok_base_url: str = "https://api.x.ai/v1"
    grok_model: str = ""
    # Optional independent reviewer. When empty, the primary continuity agent is used alone.
    review_provider: str = ""
    review_model: str = ""
    review_base_url: str = ""
    review_api_key: str = ""

    fanqie_publish_draft_url: str = ""
    fanqie_publish_url: str = ""
    fanqie_publish_token: str = ""
    fanqie_publisher_enabled: bool = False
    qidian_publish_draft_url: str = ""
    qidian_publish_url: str = ""
    qidian_publish_token: str = ""
    qidian_publisher_enabled: bool = False
    qimao_publish_draft_url: str = ""
    qimao_publish_url: str = ""
    qimao_publish_token: str = ""
    qimao_publisher_enabled: bool = False
    fanqie_browser_enabled: bool = False
    fanqie_cdp_url: str = "http://127.0.0.1:9222"
    fanqie_author_url: str = ""
    fanqie_browser_selectors: dict = {}
    qidian_browser_enabled: bool = False
    qidian_cdp_url: str = "http://127.0.0.1:9222"
    qidian_author_url: str = ""
    qidian_browser_selectors: dict = {}
    qimao_browser_enabled: bool = False
    qimao_cdp_url: str = "http://127.0.0.1:9222"
    qimao_author_url: str = ""
    qimao_browser_selectors: dict = {}

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def sync_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql+psycopg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
