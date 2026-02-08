"""Snapshot-driven browser fallback tests using static Slack/Notion DOM fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.browser import BrowserAutomationConfig, NotionBrowserClient, SlackBrowserClient
from src.dom_selectors import MESSAGE_CONTAINER, MESSAGE_LIST_CONTAINER, THREAD_MESSAGE_CONTAINER, DOMExtractor

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - environment dependent
    sync_playwright = None


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "browser_snapshots"


def _fixture_html(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def snapshot_context():
    if sync_playwright is None:  # pragma: no cover - environment dependent
        pytest.skip("Playwright is not available for snapshot fixture tests.")

    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.launch(headless=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        playwright.stop()
        pytest.skip(f"Playwright chromium launch failed: {exc}")

    context = browser.new_context()
    try:
        yield context
    finally:
        context.close()
        browser.close()
        playwright.stop()


@pytest.fixture
def snapshot_page(snapshot_context):
    page = snapshot_context.new_page()
    try:
        yield page
    finally:
        page.close()


def _slack_client_for_snapshot() -> SlackBrowserClient:
    config = BrowserAutomationConfig(
        enabled=True,
        slack_workspace_id="T123456",
        slack_client_url="https://app.slack.com/client",
    )
    return SlackBrowserClient(MagicMock(), config)


def _notion_client_for_snapshot() -> NotionBrowserClient:
    return NotionBrowserClient(MagicMock(), BrowserAutomationConfig(enabled=True))


def test_slack_snapshot_modern_extracts_messages(snapshot_page):
    snapshot_page.set_content(_fixture_html("slack_channel_modern.html"))
    extractor = DOMExtractor(snapshot_page)

    assert extractor.wait_for_element(MESSAGE_LIST_CONTAINER, timeout=1000)
    elements = snapshot_page.locator(MESSAGE_CONTAINER.primary).all()
    assert len(elements) == 2

    first = extractor.extract_message_data(elements[0])
    assert first is not None
    assert first["user"] == "Alice"
    assert first["user_id"] == "U12345678"
    assert first["ts"] == "1700000000.000001"
    assert first["text"] == "Shipped browser fallback"
    assert first["permalink"].endswith("/archives/C12345678/p1700000000000001")


def test_slack_snapshot_legacy_uses_fallback_selectors(snapshot_page):
    snapshot_page.set_content(_fixture_html("slack_channel_legacy.html"))
    extractor = DOMExtractor(snapshot_page)

    assert extractor.wait_for_element(MESSAGE_LIST_CONTAINER, timeout=1000)
    elements = snapshot_page.locator(MESSAGE_CONTAINER.fallbacks[0]).all()
    assert len(elements) == 2

    first = extractor.extract_message_data(elements[0])
    assert first is not None
    assert first["user"] == "Carlos"
    assert first["user_id"] == "U00000001"
    assert first["text"] == "Legacy channel message one"


def test_slack_thread_snapshot_collects_api_like_replies(snapshot_page):
    snapshot_page.set_content(_fixture_html("slack_thread_legacy.html"))
    client = _slack_client_for_snapshot()
    extractor = DOMExtractor(snapshot_page)

    scope = client._thread_pane_scope(snapshot_page, timeout=1000)
    assert scope is not None

    messages: list[dict] = []
    seen: set[str] = set()
    added = client._collect_messages_from_scope(
        snapshot_page,
        extractor,
        THREAD_MESSAGE_CONTAINER.get_all(),
        messages,
        seen,
        channel_id="C12345678",
        limit=10,
        thread_ts="1700000000.000200",
        scope=scope,
    )

    assert added == 2
    assert len(messages) == 2
    assert all(message["thread_ts"] == "1700000000.000200" for message in messages)
    assert all(message["channel_id"] == "C12345678" for message in messages)
    assert messages[0]["text"] == "Thread root message"


def test_notion_snapshot_modern_finds_editors_and_properties(snapshot_page):
    snapshot_page.set_content(_fixture_html("notion_page_modern.html"))
    client = _notion_client_for_snapshot()

    client._wait_for_main(snapshot_page, timeout=1000)
    editor = client._find_notion_editor(snapshot_page)
    assert editor is not None

    status_label = client._find_property_label(snapshot_page, "Status")
    assert status_label is not None
    status_cell = client._find_property_value_cell(status_label)
    assert status_cell is not None
    assert client._verify_property_value(snapshot_page, status_cell, "In Review")


def test_notion_snapshot_modern_sets_date_property(snapshot_page):
    snapshot_page.set_content(_fixture_html("notion_page_modern.html"))
    client = _notion_client_for_snapshot()

    label = client._find_property_label(snapshot_page, "Last Synced")
    assert label is not None
    value_cell = client._find_property_value_cell(label)
    assert value_cell is not None

    assert client._set_property_value(snapshot_page, value_cell, "2026-02-09")
    assert client._verify_property_value(snapshot_page, value_cell, "2026-02-09")


def test_notion_snapshot_legacy_fallback_selectors(snapshot_page):
    snapshot_page.set_content(_fixture_html("notion_page_legacy.html"))
    client = _notion_client_for_snapshot()

    client._wait_for_main(snapshot_page, timeout=1000)
    editor = client._find_notion_editor(snapshot_page)
    assert editor is not None

    label = client._find_property_label(snapshot_page, "Priority")
    assert label is not None
    value_cell = client._find_property_value_cell(label)
    assert value_cell is not None
    assert client._verify_property_value(snapshot_page, value_cell, "High")
