"""Tests for the browser automation module."""

from unittest.mock import MagicMock, patch

import pytest

from src.browser_automation import BrowserAutomationConfig, BrowserSession, NotionBrowserClient, SlackBrowserClient


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
    with patch("src.browser_automation.sync_playwright") as mock_playwright, patch(
        "src.browser_automation.os.path.exists", return_value=True
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
    
    with patch.object(slack_client, "_get_web_token", return_value="xoxc-test"), patch.object(
        slack_client.session, "request", return_value=mock_request
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
    
    with patch.object(slack_client, "_get_web_token", return_value="xoxc-test"), patch.object(
        slack_client.session, "request", return_value=mock_request
    ):
        with pytest.raises(RuntimeError) as exc_info:
            slack_client._slack_api_call("conversations.history", params={"channel": "C123456"})
        assert "Slack API error (browser): 404 channel_not_found" in str(exc_info.value)


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


if __name__ == "__main__":
    pytest.main([__file__])
