from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class PublisherResult:
    external_id: str | None
    response: dict[str, Any]


class PlatformPublisher:
    """Small HTTP adapter for an explicitly configured platform integration.

    Platform-specific request contracts belong behind this boundary. The app
    never guesses a platform URL or logs credentials.
    """

    def __init__(self, *, platform: str, draft_url: str, publish_url: str, token: str) -> None:
        self.platform = platform
        self.draft_url = draft_url.rstrip("/")
        self.publish_url = publish_url.rstrip("/")
        self.token = token

    async def upload_draft(self, payload: dict[str, Any]) -> PublisherResult:
        return await self._post(self.draft_url, {**payload, "mode": "draft"})

    async def publish(self, payload: dict[str, Any], external_id: str | None) -> PublisherResult:
        body = {**payload, "mode": "publish"}
        if external_id:
            body["external_id"] = external_id
        return await self._post(self.publish_url, body)

    async def _post(self, url: str, payload: dict[str, Any]) -> PublisherResult:
        if not url or not self.token:
            raise RuntimeError(f"{self.platform} publisher is not configured")
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json() if response.content else {}
        if not isinstance(data, dict):
            data = {"raw": data}
        external_id = data.get("id") or data.get("chapter_id") or (data.get("data") or {}).get("id")
        accepted = bool(external_id or data.get("accepted") or data.get("success"))
        if not accepted:
            raise RuntimeError(f"{self.platform} publisher returned no accepted/id result")
        return PublisherResult(external_id=str(external_id) if external_id is not None else None, response=data)


class BrowserPlatformPublisher:
    """Playwright/CDP adapter for author centers that have no public API.

    The browser must already be logged in by the user. Selectors are explicit
    configuration because author-center DOMs change independently per platform.
    """

    def __init__(self, *, platform: str, cdp_url: str, author_url: str, selectors: dict[str, str]) -> None:
        self.platform = platform
        self.cdp_url = cdp_url
        self.author_url = author_url
        self.selectors = selectors

    async def _page(self):
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("浏览器发布需要安装 playwright") from exc
        manager = await async_playwright().start()
        browser = await manager.chromium.connect_over_cdp(self.cdp_url)
        contexts = browser.contexts
        if not contexts:
            await manager.stop()
            raise RuntimeError(f"{self.platform} 浏览器没有可用会话")
        pages = [page for context in contexts for page in context.pages]
        page = next(
            (candidate for candidate in pages if self.author_url and candidate.url.startswith(self.author_url)),
            None,
        )
        owns_page = False
        if page is None:
            # Never navigate an unrelated user tab. A fresh page still shares
            # the logged-in CDP context and leaves the user's tabs untouched.
            page = await contexts[0].new_page()
            owns_page = True
        if self.author_url and not page.url.startswith(self.author_url):
            await page.goto(self.author_url, wait_until="domcontentloaded")
        return manager, page, owns_page

    async def _finish(self, manager, page, owns_page: bool) -> None:
        if owns_page and not page.is_closed():
            await page.close()
        # browser.close() is intentionally avoided: with CDP it can close the
        # user's actual Chrome process, not merely the Playwright connection.
        await manager.stop()

    async def _click_action(self, page, text_key: str, selector_key: str) -> None:
        selector = self.selectors.get(selector_key)
        if selector:
            await page.locator(selector).click()
            return
        text = self.selectors.get(text_key)
        if not text:
            raise RuntimeError(f"{self.platform} 未配置操作按钮：{text_key}/{selector_key}")
        await page.get_by_text(text, exact=True).click()

    async def _verify_action_feedback(self, page, *, text_key: str = "success_text") -> None:
        """Do not report success merely because a button was clicked.

        Author centers often keep the editor URL unchanged after an async
        save/publish request. A configured success marker is therefore used
        as the minimum acknowledgement for browser-backed publishing.
        """
        success_selector = self.selectors.get(f"{text_key.replace('_text', '')}_selector")
        success_text = self.selectors.get(text_key)
        if not success_selector and not success_text:
            return
        deadline = 8000
        elapsed = 0
        while elapsed < deadline:
            if success_selector and await page.locator(success_selector).count():
                return
            if success_text and await page.get_by_text(success_text, exact=True).count():
                return
            await page.wait_for_timeout(400)
            elapsed += 400
        raise RuntimeError(f"{self.platform} 未收到平台成功反馈，不能确认已上传")

    async def _confirm_ai_if_required(self, page, payload: dict[str, Any]) -> None:
        if not payload.get("use_ai") and not payload.get("contains_ai"):
            return
        selector = self.selectors.get("ai_yes_selector")
        text = self.selectors.get("ai_yes_text")
        if selector and await page.locator(selector).count():
            await page.locator(selector).click()
        elif text and await page.get_by_text(text, exact=True).count():
            await page.get_by_text(text, exact=True).click()
        else:
            # Some platforms do not show an AI prompt. The automation should
            # continue in that case; if a prompt is rendered, the configured
            # selector/text above is still required and will be clicked.
            return

    async def upload_draft(self, payload: dict[str, Any]) -> PublisherResult:
        manager, page, owns_page = await self._page()
        try:
            if await page.locator(self.selectors["login_marker"]).count():
                raise RuntimeError(f"{self.platform} 浏览器会话已失效，请先手动登录")
            # Qimao opens a new chapter editor from the chapter-management
            # page. The resulting upload URL contains a per-chapter cid, so
            # this preparation step must happen in the browser session rather
            # than being encoded as a fixed URL in configuration.
            prepare_selector = self.selectors.get("prepare_draft_selector")
            if prepare_selector and not await page.locator(self.selectors["title"]).count():
                await page.locator(prepare_selector).click()
                await page.locator(self.selectors["title"]).wait_for(state="visible", timeout=15000)
            await page.locator(self.selectors["title"]).fill(str(payload["title"]))
            await page.locator(self.selectors["content"]).fill(str(payload["content"]))
            await self._click_action(page, "save_draft_text", "save_draft_selector")
            await self._verify_action_feedback(page, text_key="draft_success_text")
            return PublisherResult(external_id=page.url, response={"url": page.url, "transport": "browser"})
        finally:
            await self._finish(manager, page, owns_page)

    async def get_latest_chapter_number(self) -> int | None:
        """Read the latest chapter number shown by the author center.

        This is intentionally a read-only operation. The scheduler uses it
        as the source of truth before deciding which local chapter to create
        or upload.
        """
        manager, page, owns_page = await self._page()
        try:
            text = await page.locator("body").inner_text()
            numbers = [int(value) for value in re.findall(r"第\s*(\d+)\s*章", text)]
            return max(numbers) if numbers else None
        finally:
            await self._finish(manager, page, owns_page)

    async def publish(self, payload: dict[str, Any], external_id: str | None) -> PublisherResult:
        manager, page, owns_page = await self._page()
        try:
            if await page.locator(self.selectors["login_marker"]).count():
                raise RuntimeError(f"{self.platform} 浏览器会话已失效，请先手动登录")
            if external_id and external_id.startswith("http") and page.url != external_id:
                await page.goto(external_id, wait_until="domcontentloaded")
            await self._click_action(page, "publish_text", "publish_selector")
            await self._confirm_ai_if_required(page, payload)
            await self._click_action(page, "confirm_publish_text", "confirm_publish_selector")
            await self._verify_action_feedback(page, text_key="publish_success_text")
            return PublisherResult(external_id=page.url, response={"url": page.url, "transport": "browser"})
        finally:
            await self._finish(manager, page, owns_page)


def get_platform_publisher(platform: str, settings: Settings) -> PlatformPublisher | None:
    prefix = platform.strip().lower()
    browser_values = {
        "fanqie": (getattr(settings, "fanqie_browser_enabled", False), getattr(settings, "fanqie_cdp_url", ""), getattr(settings, "fanqie_author_url", ""), getattr(settings, "fanqie_browser_selectors", {})),
        "qidian": (getattr(settings, "qidian_browser_enabled", False), getattr(settings, "qidian_cdp_url", ""), getattr(settings, "qidian_author_url", ""), getattr(settings, "qidian_browser_selectors", {})),
        "qimao": (getattr(settings, "qimao_browser_enabled", False), getattr(settings, "qimao_cdp_url", ""), getattr(settings, "qimao_author_url", ""), getattr(settings, "qimao_browser_selectors", {})),
    }
    browser_enabled, cdp_url, author_url, selectors = browser_values.get(prefix, (False, "", "", {}))
    if browser_enabled and cdp_url and author_url and isinstance(selectors, dict):
        required = {"login_marker", "title", "content"}
        has_draft_action = "save_draft_text" in selectors or "save_draft_selector" in selectors
        has_publish_action = "publish_text" in selectors or "publish_selector" in selectors
        has_confirm_action = "confirm_publish_text" in selectors or "confirm_publish_selector" in selectors
        if required.issubset(selectors) and has_draft_action and has_publish_action and has_confirm_action:
            return BrowserPlatformPublisher(platform=prefix, cdp_url=cdp_url, author_url=author_url, selectors=selectors)
    values = {
        "fanqie": (settings.fanqie_publisher_enabled, settings.fanqie_publish_draft_url, settings.fanqie_publish_url, settings.fanqie_publish_token),
        "qidian": (settings.qidian_publisher_enabled, settings.qidian_publish_draft_url, settings.qidian_publish_url, settings.qidian_publish_token),
        "qimao": (settings.qimao_publisher_enabled, settings.qimao_publish_draft_url, settings.qimao_publish_url, settings.qimao_publish_token),
    }
    enabled, draft_url, publish_url, token = values.get(prefix, (False, "", "", ""))
    if not enabled or not draft_url or not publish_url or not token:
        return None
    return PlatformPublisher(platform=prefix, draft_url=draft_url, publish_url=publish_url, token=token)
