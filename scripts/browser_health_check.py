import argparse
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.browser_automation import BrowserAutomationConfig, BrowserSession, NotionBrowserClient, SlackBrowserClient
from src.config_loader import load_config


def _build_browser_config(settings: dict) -> BrowserAutomationConfig:
    return BrowserAutomationConfig(
        enabled=settings.get("enabled", False),
        storage_state_path=settings.get("storage_state_path", ""),
        headless=settings.get("headless", True),
        slow_mo_ms=int(settings.get("slow_mo_ms", 0) or 0),
        timeout_ms=int(settings.get("timeout_ms", 30000) or 30000),
        slack_workspace_id=settings.get("slack_workspace_id", ""),
        slack_client_url=settings.get("slack_client_url", "https://app.slack.com/client"),
        slack_api_base_url=settings.get("slack_api_base_url", "https://slack.com/api"),
        notion_base_url=settings.get("notion_base_url", "https://www.notion.so"),
    )


def _pick_notion_page_id(config: dict) -> str | None:
    audit = config.get("settings", {}).get("audit", {})
    if audit.get("notion_audit_page_id"):
        return audit["notion_audit_page_id"]
    if audit.get("notion_last_synced_page_id"):
        return audit["notion_last_synced_page_id"]

    for project in config.get("projects", []):
        if project.get("notion_audit_page_id"):
            return project["notion_audit_page_id"]
        if project.get("notion_last_synced_page_id"):
            return project["notion_last_synced_page_id"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser automation health check")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
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
        print(f"Slack auth OK: {slack_user}")

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
