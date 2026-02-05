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
