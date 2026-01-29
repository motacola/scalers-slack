# Browser Automation Documentation

## Overview

The browser automation module provides a robust framework for automating interactions with Slack and Notion through a web browser. This is particularly useful when API keys are not available or when browser-based interactions are preferred.

## Key Components

### 1. BrowserSession

The `BrowserSession` class manages the lifecycle of a browser session using Playwright. It handles:

- Starting and stopping the browser.
- Creating and managing browser contexts.
- Navigating to URLs and interacting with pages.

### 2. SlackBrowserClient

The `SlackBrowserClient` class automates interactions with Slack. It includes:

- Fetching channel history and searching messages.
- Updating channel topics.
- Retrieving channel and user information.
- Handling authentication and API calls through the browser.

### 3. NotionBrowserClient

The `NotionBrowserClient` class automates interactions with Notion. It includes:

- Appending audit notes to Notion pages.
- Updating page properties.
- Checking page access and retrieving page information.

## Configuration

The `BrowserAutomationConfig` dataclass allows you to configure the browser automation behavior:

- `enabled`: Enable or disable browser automation.
- `storage_state_path`: Path to the browser's storage state for persistent sessions.
- `headless`: Run the browser in headless mode.
- `browser_channel`: Browser channel (e.g. `chrome`, `msedge`).
- `user_data_dir`: Persistent browser profile directory (enables Chrome profile reuse).
- `slow_mo_ms`: Slow down operations for debugging.
- `timeout_ms`: Default timeout for browser operations.
- `slack_workspace_id`: Slack workspace ID for multi-workspace support.
- `slack_client_url`: Base URL for the Slack client.
- `slack_api_base_url`: Base URL for the Slack API.
- `notion_base_url`: Base URL for Notion.
- `verbose_logging`: Enable verbose browser logging.
- `keep_open`: Keep the browser session open after a run.
- `interactive_login`: Allow interactive login when headed.
- `interactive_login_timeout_ms`: Maximum wait time for interactive login.
- `auto_save_storage_state`: Save storage state after interactive login.
- `auto_recover`: Retry failed actions with a refresh.
- `auto_recover_refresh`: Refresh the page during auto-recovery.
- `smart_wait`: Wait for network idle + page stability after navigation.
- `smart_wait_network_idle`: Include network idle in smart waits.
- `smart_wait_timeout_ms`: Max wait time for smart waits.
- `smart_wait_stability_ms`: Page stability window for smart waits.
- `overlay_enabled`: Show a status overlay in the page.
- `recordings_dir`: Directory for screenshots.
- `event_log_path`: JSONL event log path.
- `screenshot_on_step`: Capture screenshots after successful actions.
- `screenshot_on_error`: Capture screenshots on errors.

## Usage

### Starting a Browser Session

```python
from src.browser_automation import BrowserSession, BrowserAutomationConfig

config = BrowserAutomationConfig(
    enabled=True,
    storage_state_path="./storage_state.json",
    headless=False,
    browser_channel="chrome",
    user_data_dir="./chrome_profile",
    interactive_login=True,
)

session = BrowserSession(config)
session.start()
```

### Using SlackBrowserClient

```python
from src.browser_automation import SlackBrowserClient

slack_client = SlackBrowserClient(session, config)
messages = slack_client.fetch_channel_history_paginated("CHANNEL_ID")
```

### Using NotionBrowserClient

```python
from src.browser_automation import NotionBrowserClient

notion_client = NotionBrowserClient(session, config)
notion_client.append_audit_note("PAGE_ID", "This is an audit note.")
```

## Error Handling

The module includes comprehensive error handling and logging to ensure robustness:

- Errors are logged using Python's `logging` module.
- Exceptions are raised with descriptive messages for debugging.
- Retry mechanisms are in place for handling rate limits and network errors.

## Best Practices

- **Persistent Sessions**: Use `storage_state_path` to maintain sessions across runs.
- **Headless Mode**: Enable `headless` mode for production environments.
- **Timeouts**: Adjust `timeout_ms` based on network conditions.
- **Logging**: Configure logging to monitor browser automation activities.
- **Interactive Login**: Use headed mode with `interactive_login` to refresh storage state without manual scripts.
- **Persistent Profiles**: Use `browser_channel="chrome"` + `user_data_dir` to keep personal logins.

## CLI Flags

The main engine CLI exposes browser-related flags:

- `--headless` / `--headed`: Force headless or headed browser mode.
- `--verbose-browser`: Enable verbose browser logging.
- `--keep-browser-open`: Keep the browser session open after a run.
- `--refresh-storage-state`: Allow interactive login and auto-save storage state.
- `--browser-channel`: Browser channel (e.g. `chrome`, `msedge`).
- `--user-data-dir`: Persistent profile directory.
- `--recordings-dir`: Directory for screenshots.
- `--event-log-path`: JSONL event log path.
- `--screenshot-on-step`: Capture screenshots after successful actions.
- `--no-screenshot-on-error`: Disable screenshots on errors.
- `--smart-wait` / `--no-smart-wait`: Toggle smart waits.
- `--overlay`: Show a status overlay.
- `--auto-recover` / `--no-auto-recover`: Toggle auto-recovery.

## Testing

Ensure that browser automation is thoroughly tested:

- Test with different configurations (headless vs. non-headless).
- Validate interactions with Slack and Notion.
- Test error handling and recovery mechanisms.

## Future Enhancements

- **Performance Optimization**: Further optimize browser automation workflows.
- **Modularization**: Enhance modularity for better maintainability.
- **Documentation**: Expand documentation with more examples and use cases.
