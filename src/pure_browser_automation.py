"""Pure browser automation for Slack - no API keys required.

This module provides complete Slack automation using only browser-based techniques:
- Headless browser control via Playwright
- DOM manipulation and extraction
- Session persistence via storage state
- Network interception for data extraction
- Dynamic content loading with robust wait strategies
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class PureBrowserConfig:
    """Configuration for pure browser automation."""

    storage_state_path: str = "config/browser_storage_state.json"
    headless: bool = False
    slow_mo_ms: int = 0
    timeout_ms: int = 30000
    navigation_timeout_ms: int = 60000
    slack_workspace_url: str = "https://app.slack.com/client"
    workspace_id: str = ""
    max_scroll_attempts: int = 50
    scroll_delay_ms: int = 500
    message_load_wait_ms: int = 2000
    retry_attempts: int = 3
    retry_delay_ms: int = 1000
    screenshot_on_error: bool = True
    screenshots_dir: str = "output/browser_screenshots"


class SlackPureBrowserClient:
    """Pure browser-based Slack client - no API keys needed."""

    def __init__(self, page: Any, config: PureBrowserConfig):
        self.page = page
        self.config = config
        self._channel_cache: dict[str, str] = {}
        self._user_cache: dict[str, dict[str, str]] = {}
        self._message_cache: list[dict[str, Any]] = []

    def navigate_to_channel(self, channel_name: str) -> bool:
        """Navigate to a Slack channel."""
        channel_id = self._resolve_channel_id(channel_name)
        if not channel_id:
            logger.error(f"Could not resolve channel: {channel_name}")
            return False

        url = f"{self.config.slack_workspace_url}/{self.config.workspace_id}/channels/{channel_id}"

        try:
            self.page.goto(url, timeout=self.config.navigation_timeout_ms)
            self._wait_for_channel_load()
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to channel {channel_name}: {e}")
            return False

    def _resolve_channel_id(self, channel_name: str) -> str | None:
        """Resolve channel name to ID using cache or DOM extraction."""
        # Check cache first
        if channel_name in self._channel_cache:
            return self._channel_cache[channel_name]

        # Try to extract from current page if we're on Slack
        try:
            channel_id = self._extract_channel_id_from_url()
            if channel_id:
                self._channel_cache[channel_name] = channel_id
                return channel_id
        except Exception:
            pass

        # Try to find channel in sidebar
        try:
            channel_id = self._find_channel_in_sidebar(channel_name)
            if channel_id:
                self._channel_cache[channel_name] = channel_id
                return channel_id
        except Exception as e:
            logger.warning(f"Could not find channel {channel_name} in sidebar: {e}")

        return None

    def _extract_channel_id_from_url(self) -> str | None:
        """Extract channel ID from current URL."""
        url = self.page.url
        match = re.search(r"/channels/([A-Z0-9]+)", url)
        if match:
            return match.group(1)
        return None

    def _find_channel_in_sidebar(self, channel_name: str) -> str | None:
        """Find channel ID by searching in the sidebar."""
        # Click on the channel in sidebar if visible
        channel_selectors = [
            f'[data-qa="channel_sidebar_name_{channel_name}"]',
            f'[data-qa*="{channel_name}"]',
            f"text=#{channel_name}",
        ]

        for selector in channel_selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible(timeout=5000):
                    element.click()
                    time.sleep(1)
                    return self._extract_channel_id_from_url()
            except Exception:
                continue

        return None

    def _wait_for_channel_load(self) -> None:
        """Wait for channel content to load."""
        # Wait for message list to appear
        message_list_selectors = [
            '[data-qa="message_list"]',
            '[data-qa="virtual_list"]',
            ".c-virtual_list__scroll_container",
            '[role="main"] .c-message_list',
        ]

        for selector in message_list_selectors:
            try:
                self.page.wait_for_selector(selector, timeout=10000)
                logger.info(f"Channel loaded (found: {selector})")
                return
            except Exception:
                continue

        # Fallback: wait for any message to appear
        try:
            self.page.wait_for_selector('[data-qa="message_content"]', timeout=10000)
        except Exception as e:
            logger.warning(f"Could not confirm channel load: {e}")

    def fetch_messages(
        self,
        since_timestamp: float | None = None,
        until_timestamp: float | None = None,
        max_messages: int = 1000,
    ) -> list[dict[str, Any]]:
        """Fetch messages from current channel by scrolling and extracting DOM."""
        messages: list[dict[str, Any]] = []
        seen_timestamps: set[str] = set()

        # Scroll to bottom first
        self._scroll_to_bottom()

        # Scroll up to load history
        for attempt in range(self.config.max_scroll_attempts):
            # Extract visible messages
            new_messages = self._extract_visible_messages()

            for msg in new_messages:
                ts = msg.get("ts", "")
                if ts and ts not in seen_timestamps:
                    # Check timestamp range
                    if since_timestamp and float(ts) < since_timestamp:
                        continue
                    if until_timestamp and float(ts) > until_timestamp:
                        continue

                    seen_timestamps.add(ts)
                    messages.append(msg)

                    if len(messages) >= max_messages:
                        return messages

            # Check if we've reached the top
            if not self._scroll_up():
                logger.info(f"Reached top of channel after {attempt + 1} scrolls")
                break

            # Wait for content to load
            time.sleep(self.config.scroll_delay_ms / 1000)

        return messages

    def _scroll_to_bottom(self) -> None:
        """Scroll to bottom of message list."""
        scroll_script = """
            const container = document.querySelector('[data-qa="virtual_list"]') 
                || document.querySelector('.c-virtual_list__scroll_container')
                || document.querySelector('[role="main"]');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
            window.scrollTo(0, document.body.scrollHeight);
        """
        self.page.evaluate(scroll_script)
        time.sleep(self.config.message_load_wait_ms / 1000)

    def _scroll_up(self) -> bool:
        """Scroll up to load older messages. Returns False if at top."""
        scroll_script = """
            const container = document.querySelector('[data-qa="virtual_list"]') 
                || document.querySelector('.c-virtual_list__scroll_container')
                || document.querySelector('[role="main"]');
            if (container) {
                const oldScrollTop = container.scrollTop;
                container.scrollTop = 0;
                return container.scrollTop !== oldScrollTop;
            }
            return false;
        """
        return cast(bool, self.page.evaluate(scroll_script))

    def _extract_visible_messages(self) -> list[dict[str, Any]]:
        """Extract messages from currently visible DOM elements."""
        extract_script = """
            () => {
                const messages = [];
                const messageElements = document.querySelectorAll('[data-qa="message_content"]');
                
                messageElements.forEach(el => {
                    const container = el.closest('[data-qa="message_container"]') 
                        || el.closest('.c-message')
                        || el.parentElement;
                    
                    // Extract timestamp
                    const timeEl = container.querySelector('a[data-ts]') 
                        || container.querySelector('time')
                        || container.querySelector('[data-ts]');
                    const ts = timeEl ? (timeEl.getAttribute('data-ts') || timeEl.getAttribute('datetime')) : null;
                    
                    // Extract user
                    const userEl = container.querySelector('[data-qa="message_sender"]')
                        || container.querySelector('.c-message__sender');
                    const user = userEl ? userEl.textContent.trim() : 'Unknown';
                    
                    // Extract user ID from avatar or mention
                    const avatarEl = container.querySelector('img[data-member-id]');
                    const userId = avatarEl ? avatarEl.getAttribute('data-member-id') : '';
                    
                    // Extract text
                    const text = el.textContent.trim();
                    
                    // Extract permalink
                    const linkEl = container.querySelector('a[href*="/archives/"]');
                    const permalink = linkEl ? linkEl.href : '';
                    
                    if (text) {
                        messages.push({
                            ts: ts,
                            user: user,
                            user_id: userId,
                            text: text,
                            permalink: permalink,
                            type: 'message'
                        });
                    }
                });
                
                return messages;
            }
        """

        try:
            return cast(list[dict[str, Any]], self.page.evaluate(extract_script))
        except Exception as e:
            logger.error(f"Failed to extract messages: {e}")
            return []

    def search_messages(
        self,
        query: str,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Search messages using Slack's web search."""
        # Navigate to search
        search_url = f"{self.config.slack_workspace_url}/{self.config.workspace_id}/search/{query.replace(' ', '%20')}"

        try:
            self.page.goto(search_url, timeout=self.config.navigation_timeout_ms)
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)  # Wait for results to render

            # Extract search results
            extract_script = """
                () => {
                    const results = [];
                    const resultElements = document.querySelectorAll('[data-qa="search_result"]');
                    
                    resultElements.forEach(el => {
                        const textEl = el.querySelector('[data-qa="message_content"]')
                            || el.querySelector('.c-message__body');
                        const userEl = el.querySelector('[data-qa="message_sender"]')
                            || el.querySelector('.c-message__sender');
                        const channelEl = el.querySelector('[data-qa="channel_name"]');
                        const timeEl = el.querySelector('time') || el.querySelector('[data-ts]');
                        
                        if (textEl) {
                            results.push({
                                text: textEl.textContent.trim(),
                                username: userEl ? userEl.textContent.trim() : 'Unknown',
                                channel: channelEl ? channelEl.textContent.trim() : 'unknown',
                                ts: timeEl ? (timeEl.getAttribute('data-ts') || timeEl.getAttribute('datetime')) : '',
                                permalink: ''
                            });
                        }
                    });
                    
                    return results;
                }
            """

            results = self.page.evaluate(extract_script)
            return cast(list[dict[str, Any]], results[:max_results])

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_channel_info(self) -> dict[str, Any]:
        """Get current channel info from DOM."""
        extract_script = """
            () => {
                const titleEl = document.querySelector('[data-qa="channel_name"]')
                    || document.querySelector('.p-classic_nav__model__title');
                const topicEl = document.querySelector('[data-qa="channel_topic"]');
                
                return {
                    name: titleEl ? titleEl.textContent.trim() : '',
                    topic: topicEl ? topicEl.textContent.trim() : '',
                    url: window.location.href
                };
            }
        """

        try:
            return cast(dict[str, Any], self.page.evaluate(extract_script))
        except Exception as e:
            logger.error(f"Failed to get channel info: {e}")
            return {}

    def get_user_info(self, user_name: str) -> dict[str, str]:
        """Get user info from cache or by clicking on user."""
        if user_name in self._user_cache:
            return self._user_cache[user_name]

        # Try to extract from current messages
        extract_script = f"""
            () => {{
                const userElements = document.querySelectorAll('[data-qa="message_sender"]');
                for (const el of userElements) {{
                    if (el.textContent.trim() === '{user_name}') {{
                        const container = el.closest('[data-qa="message_container"]');
                        const avatar = container ? container.querySelector('img[data-member-id]') : null;
                        return {{
                            name: '{user_name}',
                            id: avatar ? avatar.getAttribute('data-member-id') : ''
                        }};
                    }}
                }}
                return {{ name: '{user_name}', id: '' }};
            }}
        """

        try:
            user_info = self.page.evaluate(extract_script)
            self._user_cache[user_name] = user_info
            return cast(dict[str, str], user_info)
        except Exception:
            return {"name": user_name, "id": ""}


class PureBrowserSession:
    """Manages a pure browser session for Slack automation."""

    def __init__(self, config: PureBrowserConfig):
        self.config = config
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None

    def start(self) -> Any:
        """Start browser session."""
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()

        launch_args = {
            "headless": self.config.headless,
            "slow_mo": self.config.slow_mo_ms,
        }

        self._browser = self._playwright.chromium.launch(**launch_args)

        context_args: dict[str, Any] = {}
        if Path(self.config.storage_state_path).exists():
            context_args["storage_state"] = self.config.storage_state_path

        self._context = self._browser.new_context(**context_args)
        self._context.set_default_timeout(self.config.timeout_ms)

        self._page = self._context.new_page()

        # Navigate to Slack
        self._page.goto(self.config.slack_workspace_url)

        # Check if we need to log in
        if self._is_login_required():
            if self.config.headless:
                raise RuntimeError(
                    "Login required but running in headless mode. Please run with headless=false first to authenticate."
                )
            self._handle_login()

        return self._page

    def _is_login_required(self) -> bool:
        """Check if login is required."""
        try:
            # Look for login indicators
            login_selectors = [
                '[data-qa="login_email"]',
                'input[type="email"]',
                "text=Sign in",
                ".p-login_page",
            ]

            for selector in login_selectors:
                if self._page.locator(selector).first.is_visible(timeout=5000):
                    return True

            return False
        except Exception:
            return False

    def _handle_login(self) -> None:
        """Handle interactive login."""
        logger.info("Waiting for user to log in...")
        print("\n" + "=" * 60)
        print("Please log in to Slack in the browser window.")
        print("The session will be saved for future use.")
        print("=" * 60 + "\n")

        # Wait for successful login
        success_selectors = [
            '[data-qa="team-menu"]',
            '[data-qa="channel_sidebar"]',
            ".p-workspace__sidebar",
        ]

        start_time = time.time()
        timeout = 300  # 5 minutes

        while time.time() - start_time < timeout:
            for selector in success_selectors:
                try:
                    if self._page.locator(selector).first.is_visible(timeout=2000):
                        logger.info("Login successful!")
                        self._save_storage_state()
                        return
                except Exception:
                    continue
            time.sleep(1)

        raise RuntimeError("Login timeout exceeded")

    def _save_storage_state(self) -> None:
        """Save browser storage state."""
        Path(self.config.storage_state_path).parent.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=self.config.storage_state_path)
        logger.info(f"Storage state saved to {self.config.storage_state_path}")

    def close(self) -> None:
        """Close browser session."""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def __enter__(self) -> Any:
        """Context manager entry."""
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


class PureBrowserAutomationManager:
    """High-level manager for pure browser automation."""

    def __init__(self, config: PureBrowserConfig | None = None):
        self.config = config or PureBrowserConfig()
        self.session: PureBrowserSession | None = None
        self.client: SlackPureBrowserClient | None = None

    def connect(self) -> SlackPureBrowserClient:
        """Connect to Slack via pure browser automation."""
        self.session = PureBrowserSession(self.config)
        page = self.session.start()
        self.client = SlackPureBrowserClient(page, self.config)
        return self.client

    def disconnect(self) -> None:
        """Disconnect from browser."""
        if self.session:
            self.session.close()
            self.session = None
            self.client = None

    def __enter__(self) -> SlackPureBrowserClient:
        """Context manager entry."""
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()


def create_storage_state_interactive(
    workspace_url: str = "https://app.slack.com/client",
    output_path: str = "config/browser_storage_state.json",
) -> None:
    """Create browser storage state with interactive login."""
    from playwright.sync_api import sync_playwright

    print("\n" + "=" * 60)
    print("Creating Browser Storage State")
    print("=" * 60)
    print("A browser window will open. Please log in to Slack.")
    print("Your session will be saved for automated use.")
    print("=" * 60 + "\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(workspace_url)

        # Wait for login
        print("Waiting for login (timeout: 5 minutes)...")
        success_selectors = [
            '[data-qa="team-menu"]',
            '[data-qa="channel_sidebar"]',
            ".p-workspace__sidebar",
        ]

        logged_in = False
        start_time = time.time()

        while time.time() - start_time < 300:
            for selector in success_selectors:
                try:
                    if page.locator(selector).first.is_visible(timeout=2000):
                        logged_in = True
                        break
                except Exception:
                    continue
            if logged_in:
                break
            time.sleep(1)

        if logged_in:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=output_path)
            print(f"\n✓ Storage state saved to: {output_path}")
        else:
            print("\n✗ Login timeout - please try again")

        browser.close()
