from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlencode

_sync_playwright: Any = None
try:
    from playwright.sync_api import sync_playwright as _sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    pass

sync_playwright: Any = _sync_playwright


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
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

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
        self.stats: dict[str, Any] = {}
        self.pagination_stats: dict[str, Any] = {}
        self.reset_stats()

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

    def _slack_api_call(
        self,
        endpoint: str,
        params: dict | None = None,
        method: str = "GET",
        body: dict | None = None,
    ) -> dict[str, Any]:
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
        result = cast(dict[str, Any], result)
        status = result.get("status")
        data = cast(dict[str, Any], result.get("data") or {})

        self.stats["api_calls"] += 1
        if status == 429:
            self.stats["rate_limit_hits"] += 1

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
        self._set_pagination_stats("history", page, len(messages))
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
        self._set_pagination_stats("search", page, len(matches))
        return matches

    def update_channel_topic(self, channel_id: str, topic: str) -> None:
        self._slack_api_call("conversations.setTopic", method="POST", body={"channel": channel_id, "topic": topic})

    def get_channel_info(self, channel_id: str) -> dict[str, Any]:
        data = self._slack_api_call("conversations.info", params={"channel": channel_id})
        return cast(dict[str, Any], data.get("channel", {}))

    def get_user_info(self, user_id: str) -> dict[str, Any]:
        data = self._slack_api_call("users.info", params={"user": user_id})
        return cast(dict[str, Any], data.get("user", {}))

    def auth_test(self) -> dict[str, Any]:
        return self._slack_api_call("auth.test")

    def reset_stats(self) -> None:
        self.stats = {
            "api_calls": 0,
            "retries": 0,
            "rate_limit_hits": 0,
            "rate_limit_sleep_s": 0.0,
            "retry_sleep_s": 0.0,
        }
        self.pagination_stats = {}

    def get_stats(self) -> dict[str, Any]:
        return dict(self.stats)

    def get_pagination_stats(self) -> dict[str, Any]:
        return dict(self.pagination_stats)

    def _set_pagination_stats(self, method: str, pages: int, messages: int) -> None:
        self.pagination_stats = {
            "method": method,
            "pages": pages,
            "messages": messages,
        }


class NotionBrowserClient:
    supports_verification = False
    supports_last_synced_update = True

    def __init__(self, session: BrowserSession, config: BrowserAutomationConfig):
        self.session = session
        self.config = config
        self.stats: dict[str, Any] = {}
        self.reset_stats()

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
        self.stats["ui_actions"] += 1
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
        self.stats["ui_actions"] += 1

    def get_page(self, page_id: str) -> dict:
        return {}

    def reset_stats(self) -> None:
        self.stats = {
            "ui_actions": 0,
            "errors": 0,
        }

    def get_stats(self) -> dict[str, Any]:
        return dict(self.stats)

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
