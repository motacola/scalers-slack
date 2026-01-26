from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    sync_playwright = None


@dataclass
class BrowserAutomationConfig:
    enabled: bool = False
    storage_state_path: str = ""
    headless: bool = True
    slow_mo_ms: int = 0
    timeout_ms: int = 30000
    slack_workspace_id: str = ""
    slack_client_url: str = "https://app.slack.com/client"
    slack_api_base_url: str = "https://slack.com/api"
    notion_base_url: str = "https://www.notion.so"


class BrowserSession:
    def __init__(self, config: BrowserAutomationConfig):
        self.config = config
        self._playwright = None
        self._browser = None
        self._context = None

    def start(self) -> None:
        if self._context:
            return
        if sync_playwright is None:
            raise RuntimeError("Playwright is not installed. Install it to use browser automation fallback.")

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo_ms,
        )
        context_args: dict[str, Any] = {}
        if self.config.storage_state_path:
            context_args["storage_state"] = self.config.storage_state_path
        self._context = self._browser.new_context(**context_args)
        self._context.set_default_timeout(self.config.timeout_ms)

    def new_page(self, url: str):
        self.start()
        page = self._context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        return page

    def close(self) -> None:
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None


class SlackBrowserClient:
    def __init__(self, session: BrowserSession, config: BrowserAutomationConfig):
        self.session = session
        self.config = config

    def _slack_client_home(self) -> str:
        if self.config.slack_workspace_id:
            return f"{self.config.slack_client_url}/{self.config.slack_workspace_id}"
        return self.config.slack_client_url

    def _with_page(self, url: str, func):
        page = self.session.new_page(url)
        try:
            return func(page)
        finally:
            page.close()

    def _slack_api_call(self, endpoint: str, params: dict | None = None, method: str = "GET", body: dict | None = None) -> dict:
        base_url = f"{self.config.slack_api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        url = f"{base_url}?{urlencode(params or {})}" if params else base_url
        payload = {
            "url": url,
            "method": method,
            "body": body,
        }

        def action(page):
            return page.evaluate(
                """
                async ({url, method, body}) => {
                    const options = {
                        method,
                        credentials: 'include',
                        headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    };
                    if (body) {
                        options.body = JSON.stringify(body);
                    }
                    const response = await fetch(url, options);
                    let data = null;
                    try {
                        data = await response.json();
                    } catch (err) {
                        data = null;
                    }
                    return { status: response.status, data };
                }
                """,
                payload,
            )

        result = self._with_page(self._slack_client_home(), action)
        status = result.get("status")
        data = result.get("data") or {}

        if status and status >= 400:
            error = data.get("error") if isinstance(data, dict) else "unknown_error"
            raise RuntimeError(f"Slack API error (browser): {status} {error}")

        if isinstance(data, dict) and not data.get("ok", True):
            raise RuntimeError(f"Slack API error (browser): {data.get('error', 'unknown_error')}")

        if not isinstance(data, dict):
            raise RuntimeError("Slack API error (browser): invalid response")

        return data

    def fetch_channel_history_paginated(
        self,
        channel_id: str,
        latest: str | None = None,
        oldest: str | None = None,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict]:
        messages: list[dict] = []
        cursor: str | None = None
        page = 0

        while True:
            params = {"channel": channel_id, "limit": limit}
            if latest:
                params["latest"] = latest
            if oldest:
                params["oldest"] = oldest
            if cursor:
                params["cursor"] = cursor
            data = self._slack_api_call("conversations.history", params=params)
            messages.extend(data.get("messages", []))
            cursor = data.get("response_metadata", {}).get("next_cursor")
            page += 1
            if not cursor or page >= max_pages:
                break
        return messages

    def search_messages_paginated(self, query: str, count: int = 100, max_pages: int = 5) -> list[dict]:
        matches: list[dict] = []
        page = 1
        while True:
            params = {"query": query, "count": count, "page": page}
            data = self._slack_api_call("search.messages", params=params)
            message_block = data.get("messages", {}) if isinstance(data, dict) else {}
            matches.extend(message_block.get("matches", []))
            paging = message_block.get("paging", {}) if isinstance(message_block, dict) else {}
            total_pages = paging.get("pages")
            if not total_pages or page >= total_pages or page >= max_pages:
                break
            page += 1
        return matches

    def update_channel_topic(self, channel_id: str, topic: str) -> None:
        self._slack_api_call("conversations.setTopic", method="POST", body={"channel": channel_id, "topic": topic})

    def get_channel_info(self, channel_id: str) -> dict:
        data = self._slack_api_call("conversations.info", params={"channel": channel_id})
        return data.get("channel", {})

    def auth_test(self) -> dict:
        return self._slack_api_call("auth.test")


class NotionBrowserClient:
    supports_verification = False
    supports_last_synced_update = True

    def __init__(self, session: BrowserSession, config: BrowserAutomationConfig):
        self.session = session
        self.config = config

    def _with_page(self, url: str, func):
        page = self.session.new_page(url)
        try:
            return func(page)
        finally:
            page.close()

    def _page_url(self, page_id_or_url: str) -> str:
        if page_id_or_url.startswith("http"):
            return page_id_or_url
        return f"{self.config.notion_base_url.rstrip('/')}/{page_id_or_url}"

    def append_audit_note(self, page_id: str, text: str) -> str:
        url = self._page_url(page_id)

        def action(page):
            page.wait_for_timeout(1500)
            page.click("div[contenteditable='true']", timeout=10000)
            page.keyboard.type(text)
            page.keyboard.press("Enter")

        self._with_page(url, action)
        return "browser-note"

    def get_block(self, block_id: str) -> dict:
        return {}

    def update_page_property(self, page_id: str, property_name: str, date_iso: str) -> None:
        url = self._page_url(page_id)
        date_value = date_iso.split("T")[0] if date_iso else ""

        def action(page):
            page.wait_for_timeout(1500)
            label = page.get_by_text(property_name, exact=True)
            label.wait_for(timeout=10000)

            row = label.locator(
                "xpath=ancestor::div[@role='row' or @role='listitem' or @data-property-id][1]"
            )
            if row.count() == 0:
                row = label.locator("xpath=..")

            value_cell = row.locator(
                "css=div[contenteditable='true'], css=div[role='button'], css=div[role='textbox']"
            ).first
            value_cell.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Meta+A")
            if date_value:
                page.keyboard.type(date_value)
            page.keyboard.press("Enter")

        self._with_page(url, action)

    def get_page(self, page_id: str) -> dict:
        return {}

    def check_page_access(self, page_id: str) -> bool:
        url = self._page_url(page_id)

        def action(page):
            page.wait_for_timeout(1500)
            current_url = page.url or ""
            if "login" in current_url or "signup" in current_url:
                return False
            try:
                page.wait_for_selector("div[role='main']", timeout=10000)
            except Exception:
                return False
            return True

        return bool(self._with_page(url, action))
