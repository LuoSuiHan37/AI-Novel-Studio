from types import SimpleNamespace

import httpx
import pytest

from app.services.platform_publishers import PlatformPublisher, get_platform_publisher


def test_publisher_is_opt_in() -> None:
    settings = SimpleNamespace(
        fanqie_publisher_enabled=False,
        fanqie_publish_draft_url="https://example.test/draft",
        fanqie_publish_url="https://example.test/publish",
        fanqie_publish_token="secret",
        qidian_publisher_enabled=False,
        qidian_publish_draft_url="",
        qidian_publish_url="",
        qidian_publish_token="",
        qimao_publisher_enabled=False,
        qimao_publish_draft_url="",
        qimao_publish_url="",
        qimao_publish_token="",
    )
    assert get_platform_publisher("fanqie", settings) is None
    settings.fanqie_publisher_enabled = True
    assert get_platform_publisher("fanqie", settings) is not None


@pytest.mark.asyncio
async def test_publisher_posts_draft_and_extracts_external_id(monkeypatch: pytest.MonkeyPatch) -> None:
    publisher = PlatformPublisher(
        platform="fanqie",
        draft_url="https://example.test/draft",
        publish_url="https://example.test/publish",
        token="secret",
    )

    async def fake_post(self, url, **kwargs):
        assert url.endswith("/draft")
        assert kwargs["headers"]["Authorization"] == "Bearer secret"
        assert kwargs["json"]["mode"] == "draft"
        return httpx.Response(200, request=httpx.Request("POST", url), json={"id": "chapter-1"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await publisher.upload_draft({"title": "第一章", "content": "正文"})
    assert result.external_id == "chapter-1"
