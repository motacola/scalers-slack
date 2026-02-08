"""Enhanced browser automation with better reliability and fallback mechanisms."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, cast

from src.browser_automation import (
    BrowserAutomationConfig,
    BrowserSession,
    SlackBrowserClient,
)

logger = logging.getLogger(__name__)


class EnhancedSlackBrowserClient(SlackBrowserClient):
    """Enhanced Slack browser client with improved reliability and features."""

    def __init__(self, session: BrowserSession, config: BrowserAutomationConfig):
        super().__init__(session, config)
        self._user_cache: dict[str, dict[str, Any]] = {}
        self._channel_cache: dict[str, str] = {}
        self._message_cache: list[dict[str, Any]] = []

    def resolve_channel_id(self, channel_name: str) -> str | None:
        """Resolve channel ID with caching."""
        # Check cache first
        if channel_name in self._channel_cache:
            return self._channel_cache[channel_name]

        # Try multiple methods to resolve channel
        channel_id = None

        # Method 1: Try conversations.list
        try:
            channel_id = self._resolve_via_conversations_list(channel_name)
        except Exception as e:
            logger.warning(f"Failed to resolve channel via conversations.list: {e}")

        # Method 2: Try browser navigation
        if not channel_id:
            try:
                channel_id = self._resolve_via_browser_navigation(channel_name)
            except Exception as e:
                logger.warning(f"Failed to resolve channel via browser: {e}")

        # Cache result
        if channel_id:
            self._channel_cache[channel_name] = channel_id

        return channel_id

    def _resolve_via_conversations_list(self, channel_name: str) -> str | None:
        """Resolve channel ID using conversations.list API."""
        # Remove # if present
        name = channel_name.lstrip("#")

        cursor = None
        for _ in range(10):  # Max 10 pages
            params = {"limit": 200, "types": "public_channel,private_channel"}
            if cursor:
                params["cursor"] = cursor

            data = self._slack_api_call("conversations.list", params=params)
            channels = data.get("channels", [])
            for channel in channels:
                if channel.get("name") == name:
                    return cast(str, channel.get("id"))

            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return None

    def _resolve_via_browser_navigation(self, channel_name: str) -> str | None:
        """Resolve channel ID by navigating to channel in browser."""
        name = channel_name.lstrip("#")
        workspace_id = self.config.slack_workspace_id

        # Navigate to channel
        url = f"{self.config.slack_client_url}/{workspace_id}/channels/{name}"
        page = self.session.new_page(url)

        # Wait for page to load
        time.sleep(2)

        # Try to extract channel ID from URL or page content
        try:
            current_url = page.url
            # Look for channel ID pattern in URL
            match = re.search(r"[CD][A-Z0-9]{8,}", current_url)
            if match:
                return match.group(0)
        except Exception:
            pass

        # Try to get from page JavaScript
        try:
            channel_id = page.evaluate("() => { return window.boot_data && window.boot_data.channel_id; }")
            if channel_id:
                return cast(str, channel_id)
        except Exception:
            pass

        return None

    def get_user_info_cached(self, user_id: str) -> dict[str, Any]:
        """Get user info with caching."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            user_info = self.get_user_info(user_id)
            self._user_cache[user_id] = user_info
            return user_info
        except Exception as e:
            logger.warning(f"Failed to get user info for {user_id}: {e}")
            return {"id": user_id, "name": user_id}

    def resolve_user_name(self, user_id: str) -> str:
        """Resolve user ID to display name."""
        user_info = self.get_user_info_cached(user_id)

        # Try different name fields
        profile = user_info.get("profile", {})
        return (
            profile.get("display_name")
            or profile.get("real_name")
            or user_info.get("name")
            or user_info.get("real_name")
            or user_id
        )

    def fetch_channel_history_with_permalinks(
        self,
        channel_id: str,
        channel_name: str,
        oldest: str | None = None,
        latest: str | None = None,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch channel history and add permalinks to messages."""
        messages = self.fetch_channel_history_paginated(
            channel_id=channel_id,
            oldest=oldest,
            latest=latest,
            limit=limit,
            max_pages=max_pages,
        )

        # Add permalinks
        for msg in messages:
            ts = msg.get("ts", "").replace(".", "")
            if ts:
                msg["permalink"] = f"https://quickerleads.slack.com/archives/{channel_id}/p{ts}"

        return messages

    def search_messages_with_fallback(
        self,
        query: str,
        count: int = 100,
        max_pages: int = 5,
    ) -> list[dict[str, Any]]:
        """Search messages with fallback to browser-based search if API fails."""
        try:
            # Try API search first
            return self.search_messages_paginated(query=query, count=count, max_pages=max_pages)
        except Exception as e:
            logger.warning(f"API search failed, trying browser fallback: {e}")
            return self._browser_search(query, count)

    def _browser_search(self, query: str, count: int) -> list[dict[str, Any]]:
        """Perform search using browser navigation."""
        workspace_id = self.config.slack_workspace_id
        encoded_query = query.replace(" ", "%20")

        url = f"{self.config.slack_client_url}/{workspace_id}/search/{encoded_query}"
        page = self.session.new_page(url)

        # Wait for search results to load
        time.sleep(3)

        # Extract search results from page
        # This is a simplified version - in practice you'd need more robust extraction
        results = []

        try:
            # Try to get message data from page
            messages_data = page.evaluate("""() => {
                const messages = [];
                const elements = document.querySelectorAll('[data-qa="search_result"]');
                elements.forEach(el => {
                    const textEl = el.querySelector('.c-message__body');
                    const userEl = el.querySelector('.c-message__sender');
                    const timeEl = el.querySelector('.c-timestamp__label');
                    if (textEl) {
                        messages.push({
                            text: textEl.textContent,
                            user: userEl ? userEl.textContent : 'unknown',
                            ts: timeEl ? timeEl.getAttribute('data-ts') : null
                        });
                    }
                });
                return messages;
            }""")

            for msg_data in messages_data[:count]:
                results.append(
                    {
                        "text": msg_data.get("text", ""),
                        "username": msg_data.get("user", "unknown"),
                        "ts": msg_data.get("ts", ""),
                        "channel": {"name": "search_result"},
                    }
                )

        except Exception as e:
            logger.error(f"Browser search extraction failed: {e}")

        return results

    def get_thread_replies(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all replies in a thread."""
        try:
            params = {
                "channel": channel_id,
                "ts": thread_ts,
                "limit": limit,
            }
            data = self._slack_api_call("conversations.replies", params=params)
            return cast(list[dict[str, Any]], data.get("messages", []))
        except Exception as e:
            logger.error(f"Failed to get thread replies: {e}")
            return []

    def fetch_all_messages_with_threads(
        self,
        channel_id: str,
        channel_name: str,
        oldest: str | None = None,
        latest: str | None = None,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch messages including thread replies."""
        messages = self.fetch_channel_history_with_permalinks(
            channel_id=channel_id,
            channel_name=channel_name,
            oldest=oldest,
            latest=latest,
            limit=limit,
            max_pages=max_pages,
        )

        # Fetch thread replies for messages with replies
        all_messages = []
        for msg in messages:
            all_messages.append(msg)

            # Check if message has replies
            reply_count = msg.get("reply_count", 0)
            if reply_count > 0:
                thread_ts = msg.get("thread_ts") or msg.get("ts")
                replies = self.get_thread_replies(channel_id, cast(str, thread_ts))
                # Skip the parent message (first in replies)
                all_messages.extend(replies[1:])

        return all_messages


class BrowserAutomationManager:
    """Manager for browser automation with retry and recovery."""

    def __init__(self, config: BrowserAutomationConfig):
        self.config = config
        self.session: BrowserSession | None = None
        self.client: EnhancedSlackBrowserClient | None = None
        self._is_connected = False

    def connect(self) -> EnhancedSlackBrowserClient:
        """Connect to Slack via browser with retry logic."""
        if self._is_connected and self.client:
            return self.client

        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.session = BrowserSession(self.config)
                self.session.start()
                self.client = EnhancedSlackBrowserClient(self.session, self.config)
                self._is_connected = True
                logger.info("Successfully connected to Slack via browser")
                return self.client
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if self.session:
                    self.session.close()
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                else:
                    raise

        raise RuntimeError("Failed to connect after all retries")

    def disconnect(self) -> None:
        """Disconnect from browser."""
        if self.session:
            self.session.close()
            self.session = None
            self.client = None
            self._is_connected = False
            logger.info("Disconnected from browser")

    def __enter__(self) -> EnhancedSlackBrowserClient:
        """Context manager entry."""
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()


def create_storage_state_interactive(
    output_path: str = "config/browser_storage_state.json",
    headless: bool = False,
) -> None:
    """Create browser storage state with interactive login."""
    from playwright.sync_api import sync_playwright

    logger.info("Creating browser storage state interactively")
    # Interactive prompts for CLI users
    logger.info("Creating browser storage state...")
    logger.info("A browser window will open. Please log in to Slack manually.")
    logger.info("The session will be saved after login.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to Slack
        page.goto("https://app.slack.com")

        # Wait for user to log in
        logger.info("Waiting for login (timeout: 5 minutes)")
        logger.info("Waiting for login (timeout: 5 minutes)...")
        try:
            # Wait for a sign that user is logged in
            page.wait_for_selector('[data-qa="team-menu"]', timeout=300000)
            logger.info("Login detected successfully")
            logger.info("Login detected!")
        except Exception:
            logger.warning("Login timeout exceeded")
            logger.warning("Timeout waiting for login. Please try again.")
            browser.close()
            return

        # Save storage state
        context.storage_state(path=output_path)
        logger.info("Storage state saved to: %s", output_path)
        logger.info(f"Storage state saved to {output_path}")

        browser.close()


def verify_storage_state(storage_state_path: str) -> bool:
    """Verify that storage state is valid and not expired."""
    path = Path(storage_state_path)
    if not path.exists():
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        # Check for required fields
        if "cookies" not in state:
            return False

        # Check if any cookies are expired
        for cookie in state.get("cookies", []):
            expires = cookie.get("expires", 0)
            if expires and expires < time.time():
                return False

        return True
    except (json.JSONDecodeError, OSError):
        return False
