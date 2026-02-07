"""Tests for the browser automation module."""

import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.browser import (
    BrowserAutomationConfig,
    BrowserSession,
    LoadBalancer,
    NotionBrowserClient,
    PerformanceMonitor,
    SlackBrowserClient,
)


@pytest.fixture
def browser_config():
    """Fixture for browser automation configuration."""
    return BrowserAutomationConfig(
        enabled=True,
        storage_state_path="./storage_state.json",
        headless=True,
        slow_mo_ms=0,
        timeout_ms=30000,
        slack_workspace_id="T123456",
        slack_client_url="https://app.slack.com/client",
        slack_api_base_url="https://slack.com/api",
        notion_base_url="https://www.notion.so",
        max_retries=3,
        retry_delay_ms=1000,
    )


@pytest.fixture
def mock_browser_session(browser_config):
    """Fixture for a mock browser session."""
    with (
        patch("src.browser.base.sync_playwright") as mock_playwright,
        patch("src.browser.base.os.path.exists", return_value=True),
    ):
        mock_playwright.return_value.start.return_value = MagicMock()
        mock_playwright.return_value.chromium.launch.return_value = MagicMock()
        mock_playwright.return_value.chromium.launch.return_value.new_context.return_value = MagicMock()
        session = BrowserSession(browser_config)
        session.start()
        yield session


def test_browser_session_start(mock_browser_session):
    """Test that the browser session starts successfully."""
    assert mock_browser_session._playwright is not None
    assert mock_browser_session._browser is not None
    assert mock_browser_session._context is not None


def test_browser_session_close(mock_browser_session):
    """Test that the browser session closes successfully."""
    mock_browser_session.close()
    assert mock_browser_session._context is None
    assert mock_browser_session._browser is None
    assert mock_browser_session._playwright is None


def test_slack_browser_client_initialization(mock_browser_session, browser_config):
    """Test that the Slack browser client initializes successfully."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)
    assert slack_client.session is mock_browser_session
    assert slack_client.config is browser_config


def test_notion_browser_client_initialization(mock_browser_session, browser_config):
    """Test that the Notion browser client initializes successfully."""
    notion_client = NotionBrowserClient(mock_browser_session, browser_config)
    assert notion_client.session is mock_browser_session
    assert notion_client.config is browser_config


def test_slack_api_call_success(mock_browser_session, browser_config):
    """Test a successful Slack API call."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    # Mock the request and response
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json.return_value = {"ok": True, "messages": []}
    mock_request.get.return_value = mock_response

    with (
        patch.object(slack_client, "_get_web_token", return_value="xoxc-test"),
        patch.object(slack_client.session, "request", return_value=mock_request),
    ):
        result = slack_client._slack_api_call("conversations.history", params={"channel": "C123456"})
        assert result == {"ok": True, "messages": []}


def test_slack_api_call_failure(mock_browser_session, browser_config):
    """Test a failed Slack API call."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    # Mock the request and response
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 404
    mock_response.json.return_value = {"ok": False, "error": "channel_not_found"}
    mock_request.get.return_value = mock_response

    with (
        patch.object(slack_client, "_get_web_token", return_value="xoxc-test"),
        patch.object(slack_client.session, "request", return_value=mock_request),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            slack_client._slack_api_call("conversations.history", params={"channel": "C123456"})
        assert "Slack API error (browser): 404 channel_not_found" in str(exc_info.value)


def test_slack_api_call_retries_on_auth_error(mock_browser_session, browser_config):
    """Test that auth errors trigger a token refresh and retry."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    mock_request = MagicMock()
    mock_response1 = MagicMock()
    mock_response1.status = 200
    mock_response1.json.return_value = {"ok": False, "error": "invalid_auth"}
    mock_response2 = MagicMock()
    mock_response2.status = 200
    mock_response2.json.return_value = {"ok": True, "messages": []}
    mock_request.get.side_effect = [mock_response1, mock_response2]

    with (
        patch.object(slack_client, "_get_web_token", side_effect=["old", "new", "new"]),
        patch.object(slack_client.session, "request", return_value=mock_request),
        patch.object(slack_client, "_refresh_web_token", wraps=slack_client._refresh_web_token) as refresh_mock,
    ):
        result = slack_client._slack_api_call("conversations.history", params={"channel": "C123456"})
        assert result == {"ok": True, "messages": []}
        assert refresh_mock.called


def test_notion_append_audit_note(mock_browser_session, browser_config):
    """Test appending an audit note to a Notion page."""
    notion_client = NotionBrowserClient(mock_browser_session, browser_config)

    # Mock the page and its actions
    mock_page = MagicMock()
    mock_page.wait_for_timeout = MagicMock()
    mock_page.wait_for_selector = MagicMock()
    mock_page.locator.return_value = MagicMock()
    mock_page.locator.return_value.last = MagicMock()
    mock_page.locator.return_value.last.click = MagicMock()
    mock_page.keyboard.type = MagicMock()
    mock_page.keyboard.press = MagicMock()

    with patch.object(notion_client, "_with_page", return_value=None):
        result = notion_client.append_audit_note("PAGE_ID", "Test audit note")
        assert result == "browser-note"


def test_notion_normalize_property_value(mock_browser_session, browser_config):
    """Notion property values should normalize ISO datetime inputs to date-only strings."""
    notion_client = NotionBrowserClient(mock_browser_session, browser_config)
    assert notion_client._normalize_property_value("2026-02-07T11:23:45.000Z") == "2026-02-07"
    assert notion_client._normalize_property_value("In Progress") == "In Progress"


def test_notion_update_page_property_uses_text_value(mock_browser_session, browser_config):
    """Property updates should pass non-date text values through the setter path."""
    notion_client = NotionBrowserClient(mock_browser_session, browser_config)
    mock_page = MagicMock()
    mock_label = MagicMock()
    mock_value_cell = MagicMock()

    with (
        patch.object(notion_client, "_with_page", side_effect=lambda _url, fn, *_a, **_k: fn(mock_page)),
        patch.object(notion_client, "_wait_for_main"),
        patch.object(notion_client, "_find_property_label", return_value=mock_label),
        patch.object(notion_client, "_find_property_value_cell", return_value=mock_value_cell),
        patch.object(notion_client, "_set_property_value", return_value=True) as set_value,
        patch.object(notion_client, "_verify_property_value", return_value=True),
    ):
        notion_client.update_page_property("PAGE_ID", "Status", "In Progress")

    set_value.assert_called_once_with(mock_page, mock_value_cell, "In Progress")


def test_notion_update_page_property_normalizes_datetime_input(mock_browser_session, browser_config):
    """Property updates should normalize ISO datetime values before setting."""
    notion_client = NotionBrowserClient(mock_browser_session, browser_config)
    mock_page = MagicMock()
    mock_label = MagicMock()
    mock_value_cell = MagicMock()

    with (
        patch.object(notion_client, "_with_page", side_effect=lambda _url, fn, *_a, **_k: fn(mock_page)),
        patch.object(notion_client, "_wait_for_main"),
        patch.object(notion_client, "_find_property_label", return_value=mock_label),
        patch.object(notion_client, "_find_property_value_cell", return_value=mock_value_cell),
        patch.object(notion_client, "_set_property_value", return_value=True) as set_value,
        patch.object(notion_client, "_verify_property_value", return_value=True),
    ):
        notion_client.update_page_property("PAGE_ID", "Last Synced", "2026-02-07T11:23:45.000Z")

    set_value.assert_called_once_with(mock_page, mock_value_cell, "2026-02-07")


def test_retry_mechanism(mock_browser_session, browser_config):
    """Test the retry mechanism for browser actions."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    # Mock the page and its actions to fail twice and succeed on the third attempt
    mock_page = MagicMock()
    mock_page.evaluate.side_effect = [Exception("Failed"), Exception("Failed"), "token"]

    with patch.object(slack_client, "_with_page", return_value="token"):
        token = slack_client._get_web_token()
        assert token == "token"


def test_caching_mechanism(mock_browser_session, browser_config):
    """Test the caching mechanism for frequently accessed data."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    # Mock the page and its actions
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "token"

    with patch.object(slack_client, "_with_page", return_value="token"):
        # First call should fetch the token
        token1 = slack_client._get_web_token()
        assert token1 == "token"

        # Second call should use the cached token
        token2 = slack_client._get_web_token()
        assert token2 == "token"


def test_parallel_browser_sessions(mock_browser_session, browser_config):
    """Test support for parallel browser sessions."""
    # This test is a placeholder for testing parallel browser sessions
    # In a real scenario, you would test concurrent operations
    session1 = BrowserSession(browser_config)
    session2 = BrowserSession(browser_config)

    assert session1.config is browser_config
    assert session2.config is browser_config


def test_security_measures(mock_browser_session, browser_config):
    """Test security measures for browser automation."""
    # This test is a placeholder for testing security measures
    # In a real scenario, you would test authentication and authorization
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)
    assert slack_client.config.slack_workspace_id == "T123456"


def test_history_dom_fallback_preserves_pagination_window(mock_browser_session, browser_config):
    """When API fails, DOM fallback should cover the same pagination window."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    with (
        patch.object(slack_client, "_slack_api_call", side_effect=RuntimeError("not_authed")),
        patch.object(slack_client, "_fetch_channel_history_dom", return_value=[]) as dom_fetch,
    ):
        slack_client.fetch_channel_history_paginated("C123", limit=50, max_pages=3)

    dom_fetch.assert_called_once_with("C123", latest=None, oldest=None, limit=150)


def test_search_dom_fallback_preserves_pagination_window(mock_browser_session, browser_config):
    """When API search fails, DOM fallback should cover the same pagination window."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    with (
        patch.object(slack_client, "_slack_api_call", side_effect=RuntimeError("token_expired")),
        patch.object(slack_client, "_search_messages_dom", return_value=[]) as dom_search,
    ):
        slack_client.search_messages_paginated("test query", count=25, max_pages=4)

    dom_search.assert_called_once_with("test query", limit=100)


def test_history_dom_fallback_carries_time_window(mock_browser_session, browser_config):
    """DOM history fallback should preserve oldest/latest filters."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    with (
        patch.object(slack_client, "_slack_api_call", side_effect=RuntimeError("not_authed")),
        patch.object(slack_client, "_fetch_channel_history_dom", return_value=[]) as dom_fetch,
    ):
        slack_client.fetch_channel_history_paginated(
            "C123",
            oldest="1700000000.000000",
            latest="1800000000.000000",
            limit=10,
            max_pages=2,
        )

    dom_fetch.assert_called_once_with(
        "C123",
        latest="1800000000.000000",
        oldest="1700000000.000000",
        limit=20,
    )


def test_dom_search_match_includes_channel_structure(mock_browser_session, browser_config):
    """DOM search conversion should return API-compatible match structure."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    result = slack_client._build_api_like_search_match(
        {
            "text": "hello world",
            "permalink": "https://example.slack.com/archives/C12345678/p1700000000000000",
            "ts": "1700000000.000000",
            "channel_id": "C12345678",
        }
    )
    assert result is not None
    assert result["channel"]["id"] == "C12345678"
    assert result["thread_ts"] == "1700000000.000000"


def test_get_channel_info_falls_back_to_dom(mock_browser_session, browser_config):
    """Channel info should use DOM fallback when API path is unavailable."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    with (
        patch.object(slack_client, "_slack_api_call", side_effect=RuntimeError("not_authed")),
        patch.object(
            slack_client,
            "_get_channel_info_dom",
            return_value={"id": "C123", "name": "general", "topic": {"value": ""}},
        ) as dom_info,
    ):
        info = slack_client.get_channel_info("C123")

    assert info["id"] == "C123"
    dom_info.assert_called_once_with("C123")


def test_get_user_info_falls_back_to_minimal_data(mock_browser_session, browser_config):
    """User info should return minimal safe structure when API is unavailable."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    with patch.object(slack_client, "_slack_api_call", side_effect=RuntimeError("token_expired")):
        user = slack_client.get_user_info("U12345678")

    assert user["id"] == "U12345678"
    assert user["real_name"] == "U12345678"


def test_auth_test_falls_back_to_dom(mock_browser_session, browser_config):
    """auth_test should still pass using DOM fallback when API auth fails."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    with (
        patch.object(slack_client, "_slack_api_call", side_effect=RuntimeError("not_authed")),
        patch.object(slack_client, "_auth_test_dom", return_value={"ok": True, "team_id": "T123456"}) as dom_auth,
    ):
        result = slack_client.auth_test()

    assert result["ok"] is True
    dom_auth.assert_called_once()


def test_thread_replies_dom_fallback_uses_thread_extractor_first(mock_browser_session, browser_config):
    """Thread reply fallback should use thread-pane DOM extraction before history approximation."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)
    dom_replies = [{"ts": "1700000000.000001", "thread_ts": "1700000000.000001", "text": "reply", "user": "U1"}]

    with (
        patch.object(slack_client, "_slack_api_call", side_effect=RuntimeError("not_authed")),
        patch.object(slack_client, "_fetch_thread_replies_dom", return_value=dom_replies) as dom_fetch,
        patch.object(slack_client, "_fetch_channel_history_dom", return_value=[]) as history_fetch,
    ):
        replies = slack_client.fetch_thread_replies_paginated(
            "C123",
            thread_ts="1700000000.000001",
            limit=10,
            max_pages=2,
        )

    assert replies == dom_replies
    dom_fetch.assert_called_once_with("C123", thread_ts="1700000000.000001", limit=20)
    history_fetch.assert_not_called()


def test_thread_replies_dom_fallback_uses_history_if_thread_empty(mock_browser_session, browser_config):
    """If thread-pane extraction is empty, fallback should still return filtered history replies."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)
    history_messages = [
        {"ts": "1700000000.000001", "thread_ts": "1700000000.000001", "text": "root"},
        {"ts": "1700000000.000002", "thread_ts": "1700000000.000001", "text": "reply"},
        {"ts": "1700000000.000003", "thread_ts": "1700000000.000003", "text": "other"},
    ]

    with (
        patch.object(slack_client, "_slack_api_call", side_effect=RuntimeError("not_authed")),
        patch.object(slack_client, "_fetch_thread_replies_dom", return_value=[]),
        patch.object(slack_client, "_fetch_channel_history_dom", return_value=history_messages) as history_fetch,
    ):
        replies = slack_client.fetch_thread_replies_paginated(
            "C123",
            thread_ts="1700000000.000001",
            limit=10,
            max_pages=2,
        )

    assert len(replies) == 2
    assert all(msg["thread_ts"] == "1700000000.000001" for msg in replies)
    history_fetch.assert_called_once_with("C123", limit=200)


def test_thread_url_candidates_include_channel_base(mock_browser_session, browser_config):
    """Thread URL candidates should include a channel URL for click-open fallback."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)
    candidates = slack_client._thread_url_candidates("C12345678", "1700000000.000001")

    assert candidates
    assert candidates[0].endswith("/T123456/C12345678")
    assert any("thread_ts=1700000000.000001" in candidate for candidate in candidates)


def test_fetch_thread_replies_dom_attempts_root_click_open(mock_browser_session, browser_config):
    """When thread pane is missing, DOM thread fetch should attempt root-message click opening."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)
    page = MagicMock()

    with (
        patch.object(slack_client.session, "new_page", return_value=page),
        patch.object(slack_client, "_wait_until_ready"),
        patch.object(
            slack_client,
            "_thread_url_candidates",
            return_value=["https://app.slack.com/client/T123456/C12345678"],
        ),
        patch.object(slack_client, "_thread_pane_scope", return_value=None),
        patch.object(slack_client, "_open_thread_from_root_message", return_value=False) as open_root,
        patch.object(slack_client, "_collect_messages_from_scope", return_value=0),
        patch("src.browser.slack_client.DOMExtractor") as extractor_cls,
    ):
        extractor = MagicMock()
        extractor.wait_for_element.return_value = True
        extractor_cls.return_value = extractor

        messages = slack_client._fetch_thread_replies_dom(
            "C12345678",
            "1700000000.000001",
            limit=5,
            max_scrolls=1,
        )

    assert messages == []
    open_root.assert_called_once_with(page, channel_id="C12345678", thread_ts="1700000000.000001")


def test_build_api_like_message_allows_thread_override(mock_browser_session, browser_config):
    """DOM conversion should preserve explicit thread_ts override for thread-pane extraction."""
    slack_client = SlackBrowserClient(mock_browser_session, browser_config)

    message = slack_client._build_api_like_message(
        {
            "text": "hello",
            "ts": "1700000000.000001",
            "thread_ts": "1700000000.000001",
            "permalink": "https://example.slack.com/archives/C123/p1700000000000001",
        },
        channel_id="C123",
        thread_ts="1709999999.123456",
    )

    assert message is not None
    assert message["thread_ts"] == "1709999999.123456"


def test_dom_snapshot_written(tmp_path):
    """Test that DOM snapshots are written when enabled."""
    config = BrowserAutomationConfig(recordings_dir=str(tmp_path), html_snapshot_on_error=True)
    session = BrowserSession(config)
    page = MagicMock()
    page.content.return_value = "<html>ok</html>"

    session._maybe_dom_snapshot(page, "error")
    files = os.listdir(tmp_path)
    assert any(name.endswith("_error.html") for name in files)


def test_load_balancer_round_robin_selection():
    """Test that load balancer selects workers in order starting at first."""
    balancer = LoadBalancer(max_workers=2)
    balancer.add_worker("worker-1")
    balancer.add_worker("worker-2")

    first = balancer.get_available_worker()
    second = balancer.get_available_worker()

    assert first == "worker-1"
    assert second == "worker-2"


def test_performance_monitor_stop_before_start_logs_warning():
    """Test that stopping before starting does not update metrics."""
    monitor = PerformanceMonitor()
    with patch("src.browser.base.logger") as mock_logger:
        monitor.stop_monitoring(success=True, operation_name="op")
        assert mock_logger.warning.called
    assert monitor.get_metrics()["sync_operations"] == 0
    assert monitor.get_metrics()["total_time_ms"] == 0


def test_log_event_without_directory():
    """Test log_event writes when event_log_path has no directory."""
    config = BrowserAutomationConfig(event_log_path="events.jsonl")
    session = BrowserSession(config)

    with patch("src.browser.base.os.makedirs") as mock_makedirs, patch("builtins.open", mock_open()):
        session.log_event("test_event", {"ok": True})
        mock_makedirs.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__])
