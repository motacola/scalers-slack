import argparse
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.browser import BrowserAutomationConfig, BrowserSession, NotionBrowserClient, SlackBrowserClient
from src.config_loader import load_config


def _build_browser_config(settings: dict) -> BrowserAutomationConfig:
    return BrowserAutomationConfig(
        enabled=settings.get("enabled", False),
        storage_state_path=settings.get("storage_state_path", ""),
        headless=settings.get("headless", True),
        slow_mo_ms=int(settings.get("slow_mo_ms", 0) or 0),
        timeout_ms=int(settings.get("timeout_ms", 30000) or 30000),
        browser_channel=settings.get("browser_channel"),
        user_data_dir=settings.get("user_data_dir"),
        slack_workspace_id=settings.get("slack_workspace_id", ""),
        slack_client_url=settings.get("slack_client_url", "https://app.slack.com/client"),
        slack_api_base_url=settings.get("slack_api_base_url", "https://slack.com/api"),
        notion_base_url=settings.get("notion_base_url", "https://www.notion.so"),
        verbose_logging=settings.get("verbose_logging", False),
        keep_open=settings.get("keep_open", False),
        interactive_login=settings.get("interactive_login", True),
        interactive_login_timeout_ms=int(settings.get("interactive_login_timeout_ms", 120000) or 120000),
        auto_save_storage_state=settings.get("auto_save_storage_state", True),
        auto_recover=settings.get("auto_recover", True),
        auto_recover_refresh=settings.get("auto_recover_refresh", True),
        smart_wait=settings.get("smart_wait", True),
        smart_wait_network_idle=settings.get("smart_wait_network_idle", True),
        smart_wait_timeout_ms=int(settings.get("smart_wait_timeout_ms", 15000) or 15000),
        smart_wait_stability_ms=int(settings.get("smart_wait_stability_ms", 600) or 600),
        overlay_enabled=settings.get("overlay_enabled", False),
        recordings_dir=settings.get("recordings_dir", "output/browser_recordings"),
        event_log_path=settings.get("event_log_path", "output/browser_events.jsonl"),
        screenshot_on_step=settings.get("screenshot_on_step", False),
        screenshot_on_error=settings.get("screenshot_on_error", True),
        proxy_server=settings.get("proxy_server"),
        proxy_username=settings.get("proxy_username"),
        proxy_password=settings.get("proxy_password"),
    )


def _pick_notion_page_id(config: dict) -> str | None:
    audit = config.get("settings", {}).get("audit", {})
    audit_page_url = audit.get("notion_audit_page_url")
    if isinstance(audit_page_url, str) and audit_page_url:
        return audit_page_url
    audit_page_id = audit.get("notion_audit_page_id")
    if isinstance(audit_page_id, str) and audit_page_id:
        return audit_page_id
    last_synced_url = audit.get("notion_last_synced_page_url")
    if isinstance(last_synced_url, str) and last_synced_url:
        return last_synced_url
    last_synced_id = audit.get("notion_last_synced_page_id")
    if isinstance(last_synced_id, str) and last_synced_id:
        return last_synced_id

    for project in config.get("projects", []):
        project_audit_url = project.get("notion_audit_page_url")
        if isinstance(project_audit_url, str) and project_audit_url:
            return project_audit_url
        project_audit_id = project.get("notion_audit_page_id")
        if isinstance(project_audit_id, str) and project_audit_id:
            return project_audit_id
        project_last_synced_url = project.get("notion_last_synced_page_url")
        if isinstance(project_last_synced_url, str) and project_last_synced_url:
            return project_last_synced_url
        project_last_synced_id = project.get("notion_last_synced_page_id")
        if isinstance(project_last_synced_id, str) and project_last_synced_id:
            return project_last_synced_id
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser automation health check")
    parser.add_argument("--config", default="config/config.json", help="Path to config.json")
    args = parser.parse_args()

    config = load_config(args.config)
    browser_settings = config.get("settings", {}).get("browser_automation", {})
    browser_config = _build_browser_config(browser_settings)

    if not browser_config.enabled:
        print("Browser automation is disabled in config.json")
        return 1

    if not browser_config.storage_state_path:
        print("browser_automation.storage_state_path is not set")
        return 1

    if not os.path.exists(browser_config.storage_state_path):
        print(f"Storage state not found: {browser_config.storage_state_path}")
        return 1

    session = BrowserSession(browser_config)
    slack = SlackBrowserClient(session, browser_config)
    notion = NotionBrowserClient(session, browser_config)

    ok = True
    try:
        slack_auth = slack.auth_test()
        slack_user = slack_auth.get("user") or slack_auth.get("user_id")
        team_id = slack_auth.get("team_id") or slack_auth.get("team")
        print(f"Slack auth OK: {slack_user}")

        if browser_config.slack_workspace_id:
            if not team_id:
                ok = False
                print("Slack auth warning: team_id missing from auth.test response")
            elif team_id != browser_config.slack_workspace_id:
                ok = False
                print(f"Slack auth mismatch: expected {browser_config.slack_workspace_id}, got {team_id}")
                if browser_config.interactive_login and not browser_config.headless:
                    print("Attempting interactive Slack login to refresh session...")
                    slack._interactive_login_slack()
                    slack_auth = slack.auth_test()
                    team_id = slack_auth.get("team_id") or slack_auth.get("team")
                    if team_id == browser_config.slack_workspace_id:
                        ok = True
                        print("Slack auth refreshed and workspace matches.")
                    else:
                        ok = False

        channel_id = None
        if config.get("projects"):
            channel_id = config["projects"][0].get("slack_channel_id")
        if channel_id:
            slack_channel = slack.get_channel_info(channel_id)
            print(f"Slack channel OK: {slack_channel.get('name', channel_id)}")

    except Exception as exc:
        ok = False
        print(f"Slack browser check failed: {exc}")

    notion_page = _pick_notion_page_id(config)
    if notion_page:
        try:
            print(f"Checking Notion page access: {notion_page}")
            accessible = notion.check_page_access(notion_page)
            if accessible:
                print("Notion page access OK")
            else:
                ok = False
                print("Notion page access failed")
        except Exception as exc:
            ok = False
            print(f"Notion browser check failed: {exc}")
    else:
        print("No Notion page IDs configured; skipping Notion check")

    session.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
