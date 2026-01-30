"""DOM selectors and extraction strategies for Slack web interface.

This module provides robust selectors and extraction logic for scraping
Slack's web interface. Selectors are organized by feature and include
fallback strategies for resilience against UI changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SelectorSet:
    """A set of selectors with fallbacks."""

    primary: str
    fallbacks: list[str]

    def get_all(self) -> list[str]:
        """Get all selectors in order of preference."""
        return [self.primary] + self.fallbacks


# Message list containers
MESSAGE_LIST_CONTAINER = SelectorSet(
    primary='[data-qa="virtual_list"]',
    fallbacks=[
        '[data-qa="message_list"]',
        '.c-virtual_list__scroll_container',
        '.p-message_pane__virtual_list',
        '[role="main"] .c-message_list',
        '.c-message_list',
    ]
)

# Individual message containers
MESSAGE_CONTAINER = SelectorSet(
    primary='[data-qa="message_container"]',
    fallbacks=[
        '.c-message',
        '.c-message--light',
    ]
)

# Message content/text
MESSAGE_CONTENT = SelectorSet(
    primary='[data-qa="message_content"]',
    fallbacks=[
        '.c-message__body',
        '.p-rich_text_section',
        '.c-message__message_content',
    ]
)

# Message sender/user
MESSAGE_SENDER = SelectorSet(
    primary='[data-qa="message_sender"]',
    fallbacks=[
        '.c-message__sender',
        '.p-classic_nav__model__title',
        '[data-qa="message_container"] .c-custom_status',
    ]
)

# Message timestamp
MESSAGE_TIMESTAMP = SelectorSet(
    primary='a[data-ts]',
    fallbacks=[
        'time[data-ts]',
        'time',
        '[data-ts]',
        '.c-timestamp__label',
    ]
)

# User avatar (contains user ID)
USER_AVATAR = SelectorSet(
    primary='img[data-member-id]',
    fallbacks=[
        'img[data-user-id]',
        '.c-avatar img',
        '[data-qa="message_container"] img',
    ]
)

# Channel sidebar
CHANNEL_SIDEBAR = SelectorSet(
    primary='[data-qa="channel_sidebar"]',
    fallbacks=[
        '.p-workspace__sidebar',
        '.p-channel_sidebar',
        '[role="navigation"]',
    ]
)

# Channel name in header
CHANNEL_HEADER_NAME = SelectorSet(
    primary='[data-qa="channel_name"]',
    fallbacks=[
        '.p-classic_nav__model__title',
        '.p-view_header__title',
        'h1[data-qa]',
    ]
)

# Channel topic
CHANNEL_TOPIC = SelectorSet(
    primary='[data-qa="channel_topic"]',
    fallbacks=[
        '.p-classic_nav__model__subtitle',
        '.p-view_header__subtitle',
    ]
)

# Search results
SEARCH_RESULT = SelectorSet(
    primary='[data-qa="search_result"]',
    fallbacks=[
        '.p-search_result',
        '.c-search_result',
        '[data-qa="search_message_result"]',
    ]
)

# Login indicators
LOGIN_EMAIL_INPUT = SelectorSet(
    primary='[data-qa="login_email"]',
    fallbacks=[
        'input[type="email"]',
        'input[name="email"]',
        '#email',
    ]
)

LOGIN_PASSWORD_INPUT = SelectorSet(
    primary='[data-qa="login_password"]',
    fallbacks=[
        'input[type="password"]',
        'input[name="password"]',
        '#password',
    ]
)

# Logged-in indicators
TEAM_MENU = SelectorSet(
    primary='[data-qa="team-menu"]',
    fallbacks=[
        '.p-team_menu',
        '[data-qa="user-button"]',
        '.p-workspace__top_nav',
    ]
)

# Day dividers (date separators)
DAY_DIVIDER = SelectorSet(
    primary='[data-qa="day_divider"]',
    fallbacks=[
        '.c-message_list__day_divider',
        '.p-message_pane__day_divider',
    ]
)

# Thread replies indicator
THREAD_REPLIES = SelectorSet(
    primary='[data-qa="thread_replies"]',
    fallbacks=[
        '.c-message__reply_count',
        '[data-qa="reply_count"]',
    ]
)

# Message actions menu
MESSAGE_ACTIONS = SelectorSet(
    primary='[data-qa="message_actions_menu"]',
    fallbacks=[
        '.c-message__actions',
        '.c-message_actions__container',
    ]
)


class DOMExtractor:
    """Extract data from Slack DOM using robust selectors."""

    def __init__(self, page: Any):
        self.page = page

    def find_element(self, selector_set: SelectorSet, timeout: int = 5000) -> Any | None:
        """Find element using selector set with fallbacks."""
        for selector in selector_set.get_all():
            try:
                element = self.page.locator(selector).first
                if element.is_visible(timeout=timeout):
                    return element
            except Exception:
                continue
        return None

    def wait_for_element(self, selector_set: SelectorSet, timeout: int = 10000) -> bool:
        """Wait for any selector in set to appear."""
        for selector in selector_set.get_all():
            try:
                self.page.wait_for_selector(selector, timeout=timeout)
                return True
            except Exception:
                continue
        return False

    def extract_message_data(self, message_element: Any) -> dict[str, Any] | None:
        """Extract all data from a message element."""
        try:
            data = {
                "text": self._extract_text(message_element),
                "user": self._extract_user(message_element),
                "user_id": self._extract_user_id(message_element),
                "ts": self._extract_timestamp(message_element),
                "permalink": self._extract_permalink(message_element),
            }

            # Only return if we have at least text
            if data["text"]:
                return data

        except Exception as e:
            # Log error but don't fail - message might be malformed
            pass

        return None

    def _extract_text(self, element: Any) -> str:
        """Extract message text."""
        for selector in MESSAGE_CONTENT.get_all():
            try:
                text_el = element.locator(selector).first
                if text_el.is_visible(timeout=1000):
                    return text_el.text_content().strip()
            except Exception:
                continue
        return ""

    def _extract_user(self, element: Any) -> str:
        """Extract user name."""
        for selector in MESSAGE_SENDER.get_all():
            try:
                user_el = element.locator(selector).first
                if user_el.is_visible(timeout=1000):
                    return user_el.text_content().strip()
            except Exception:
                continue
        return "Unknown"

    def _extract_user_id(self, element: Any) -> str:
        """Extract user ID from avatar."""
        for selector in USER_AVATAR.get_all():
            try:
                avatar = element.locator(selector).first
                if avatar.is_visible(timeout=1000):
                    return (
                        avatar.get_attribute("data-member-id") or
                        avatar.get_attribute("data-user-id") or
                        ""
                    )
            except Exception:
                continue
        return ""

    def _extract_timestamp(self, element: Any) -> str:
        """Extract message timestamp."""
        for selector in MESSAGE_TIMESTAMP.get_all():
            try:
                ts_el = element.locator(selector).first
                if ts_el.is_visible(timeout=1000):
                    return (
                        ts_el.get_attribute("data-ts") or
                        ts_el.get_attribute("datetime") or
                        ""
                    )
            except Exception:
                continue
        return ""

    def _extract_permalink(self, element: Any) -> str:
        """Extract message permalink."""
        try:
            # Look for timestamp link which contains permalink
            for selector in MESSAGE_TIMESTAMP.get_all():
                link = element.locator(f'{selector}[href]').first
                if link.is_visible(timeout=1000):
                    href = link.get_attribute("href")
                    if href:
                        return href if href.startswith("http") else f"https://quickerleads.slack.com{href}"
        except Exception:
            pass
        return ""

    def is_message_visible(self, element: Any) -> bool:
        """Check if element is a visible message."""
        try:
            return element.is_visible(timeout=1000)
        except Exception:
            return False

    def count_messages(self) -> int:
        """Count visible messages on page."""
        count = 0
        for selector in MESSAGE_CONTAINER.get_all():
            try:
                count = self.page.locator(selector).count()
                if count > 0:
                    return count
            except Exception:
                continue
        return 0

    def scroll_container(self) -> Any | None:
        """Get the scrollable message container."""
        for selector in MESSAGE_LIST_CONTAINER.get_all():
            try:
                container = self.page.locator(selector).first
                if container.is_visible(timeout=5000):
                    return container
            except Exception:
                continue
        return None