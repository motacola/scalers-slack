import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, cast

from playwright.sync_api import sync_playwright

# Add src to path so we can read config defaults if desired.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config_loader import load_config


def _extract_slack_token_from_state(state: Any, workspace_id: str | None) -> str | None:
    origins = state.get("origins", []) if isinstance(state, dict) else []
    for origin in origins:
        if "slack.com" not in origin.get("origin", ""):
            continue
        for entry in origin.get("localStorage", []):
            if entry.get("name") not in {"localConfig_v2", "localConfig"}:
                continue
            raw = entry.get("value")
            if not isinstance(raw, str) or not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            teams = parsed.get("teams") if isinstance(parsed, dict) else None
            if not isinstance(teams, dict):
                continue
            if workspace_id and workspace_id in teams and isinstance(teams[workspace_id], dict):
                token = teams[workspace_id].get("token")
                if isinstance(token, str) and token:
                    return token
            for team in teams.values():
                if isinstance(team, dict):
                    token = team.get("token")
                    if isinstance(token, str) and token:
                        return token
    return None


def _extract_slack_token_from_page(page, workspace_id: str | None) -> str | None:
    try:
        token = page.evaluate(
            """
            (workspaceId) => {
                const keys = ["localConfig_v2", "localConfig"];
                for (const key of keys) {
                    const raw = window.localStorage.getItem(key);
                    if (!raw) continue;
                    try {
                        const parsed = JSON.parse(raw);
                        const teams = parsed && parsed.teams ? parsed.teams : null;
                        if (!teams) continue;
                        if (workspaceId && teams[workspaceId] && teams[workspaceId].token) {
                            return teams[workspaceId].token;
                        }
                        for (const id of Object.keys(teams)) {
                            const team = teams[id];
                            if (team && team.token) return team.token;
                        }
                    } catch (e) {
                        continue;
                    }
                }
                return null;
            }
            """,
            workspace_id,
        )
        if isinstance(token, str) and token:
            return token
        return None
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Playwright storage state for Slack + Notion.")
    parser.add_argument("--config", default="config/config.json", help="Path to config.json for defaults")
    parser.add_argument("--output", default="config/browser_storage_state.json", help="Storage state output path")
    parser.add_argument("--headless", action="store_true", help="Run browser headless (not recommended)")
    parser.add_argument(
        "--workspace-id",
        default=os.getenv("SLACK_WORKSPACE_ID") or os.getenv("SLACK_TEAM_ID") or "",
        help="Slack workspace ID (e.g., T12345678). Defaults to SLACK_WORKSPACE_ID env var.",
    )
    parser.add_argument(
        "--user-data-dir",
        default="",
        help=(
            "Chrome user data dir for persistent context "
            "(recommended to match config.browser_automation.user_data_dir)"
        ),
    )
    parser.add_argument(
        "--browser-channel",
        default="",
        help="Browser channel to use (e.g., chrome). Defaults to config.browser_automation.browser_channel.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=900,
        help="Max seconds to wait for manual login before saving storage state",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=5,
        help="Seconds between auth checks",
    )
    args = parser.parse_args()

    config_defaults: dict = {}
    try:
        if args.config:
            config_defaults = load_config(args.config).get("settings", {}).get("browser_automation", {}) or {}
    except Exception:
        config_defaults = {}

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_id = args.workspace_id.strip() or config_defaults.get("slack_workspace_id") or None
    user_data_dir = (args.user_data_dir or config_defaults.get("user_data_dir") or "").strip() or None
    browser_channel = (args.browser_channel or config_defaults.get("browser_channel") or "").strip() or None

    with sync_playwright() as p:
        if user_data_dir:
            data_dir = os.path.abspath(user_data_dir)
            os.makedirs(data_dir, exist_ok=True)
            launch_args: dict[str, object] = {"headless": args.headless}
            if browser_channel:
                launch_args["channel"] = browser_channel
            context = p.chromium.launch_persistent_context(data_dir, **cast(Any, launch_args))
            browser = None
        else:
            launch_args = {"headless": args.headless}
            if browser_channel:
                launch_args["channel"] = browser_channel
            browser = p.chromium.launch(**cast(Any, launch_args))
            context = browser.new_context()
        page = context.new_page()

        slack_url = f"https://app.slack.com/client/{workspace_id}" if workspace_id else "https://app.slack.com/client"
        print("Opening Slack. Please log in if needed, then leave the tab open.")
        page.goto(slack_url, wait_until="domcontentloaded")

        deadline = time.time() + args.wait_seconds
        while time.time() < deadline:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                result = page.evaluate(
                    """
                    async () => {
                        try {
                            const res = await fetch('https://slack.com/api/auth.test', { credentials: 'include' });
                            const data = await res.json();
                            return { ok: Boolean(data && data.ok), data };
                        } catch (e) {
                            return { ok: false, error: String(e) };
                        }
                    }
                    """
                )
            except Exception:
                time.sleep(args.poll_seconds)
                continue

            if result.get("ok"):
                print("Slack auth confirmed.")
                break
            time.sleep(args.poll_seconds)
        else:
            print("Slack auth not confirmed before timeout.")

        # Ensure Slack web token is present in localStorage for browser-mode API calls
        deadline = time.time() + args.wait_seconds
        slack_token = None
        while time.time() < deadline and not slack_token:
            state = context.storage_state()
            slack_token = _extract_slack_token_from_state(state, workspace_id)
            if not slack_token:
                slack_token = _extract_slack_token_from_page(page, workspace_id)
            if slack_token:
                print("Slack web token found in localStorage.")
                break
            time.sleep(args.poll_seconds)
        if not slack_token:
            print(
                "Warning: Slack web token not found in localStorage. "
                "Browser automation may fail until Slack is fully loaded."
            )

        print("Opening Notion. Please log in if needed, then leave the tab open.")
        page.goto("https://www.notion.so", wait_until="domcontentloaded")

        deadline = time.time() + args.wait_seconds
        while time.time() < deadline:
            cookies = context.cookies("https://www.notion.so")
            if any(cookie.get("name") == "token_v2" for cookie in cookies):
                print("Notion auth confirmed.")
                break
            time.sleep(args.poll_seconds)
        else:
            print("Notion auth not confirmed before timeout.")

        context.storage_state(path=str(output_path))
        if browser:
            browser.close()
        else:
            context.close()

    print(f"Storage state saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
