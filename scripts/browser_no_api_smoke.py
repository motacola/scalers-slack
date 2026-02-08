#!/usr/bin/env python3
"""Run browser-only Slack/Notion smoke checks without API keys."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.browser_health_check import _build_browser_config, _pick_notion_page_id
from src.browser import BrowserSession, NotionBrowserClient, SlackBrowserClient
from src.config_loader import load_config


def _pick_channel_id(config: dict[str, Any]) -> str | None:
    for project in config.get("projects", []):
        channel_id = project.get("slack_channel_id")
        if isinstance(channel_id, str) and channel_id:
            return channel_id
    return None


def _pick_thread_ts(history: list[dict[str, Any]]) -> str | None:
    for message in history:
        ts = message.get("thread_ts") or message.get("ts")
        if isinstance(ts, str) and ts:
            return ts
    return None


def _status_line(name: str, ok: bool, detail: str) -> str:
    return f"[{'OK' if ok else 'FAIL'}] {name}: {detail}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser-only smoke checks (no API keys required).")
    parser.add_argument("--config", default="config/config.json", help="Path to config.json")
    parser.add_argument("--channel-id", help="Slack channel ID override")
    parser.add_argument("--thread-ts", help="Slack thread ts override")
    parser.add_argument("--notion-page", help="Notion page URL/ID override")
    parser.add_argument("--history-limit", type=int, default=20, help="Messages to fetch from channel history")
    parser.add_argument("--reply-limit", type=int, default=30, help="Replies to fetch from thread")
    parser.add_argument("--force-dom", action="store_true", help="Force DOM fallback by disabling Slack API calls")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    config = load_config(args.config)
    browser_settings = config.get("settings", {}).get("browser_automation", {})
    browser_config = _build_browser_config(browser_settings)
    browser_config.enabled = True

    session = BrowserSession(browser_config)
    slack = SlackBrowserClient(session, browser_config)
    notion = NotionBrowserClient(session, browser_config)

    checks: list[dict[str, Any]] = []
    overall_ok = True

    def add_check(name: str, ok: bool, detail: str, extra: dict[str, Any] | None = None) -> None:
        nonlocal overall_ok
        if not ok:
            overall_ok = False
        record = {"name": name, "ok": ok, "detail": detail}
        if extra:
            record["extra"] = extra
        checks.append(record)

    try:
        session.start()

        if args.force_dom:

            def _disabled_api(*_a, **_kw):
                raise RuntimeError("not_authed")

            slack._slack_api_call = _disabled_api  # type: ignore[method-assign]

        try:
            auth = slack.auth_test()
            team_id = auth.get("team_id") or auth.get("team") or "unknown"
            add_check("Slack auth", bool(auth.get("ok", True)), f"team={team_id}")
        except Exception as exc:
            add_check("Slack auth", False, str(exc))

        try:
            conversations = slack.list_conversations_paginated(limit=20, max_pages=1)
            add_check(
                "Slack conversations",
                len(conversations) > 0,
                f"count={len(conversations)}",
                extra={"pagination": slack.get_pagination_stats()},
            )
        except Exception as exc:
            add_check("Slack conversations", False, str(exc))

        channel_id = args.channel_id or _pick_channel_id(config)
        history: list[dict[str, Any]] = []
        if channel_id:
            try:
                history = slack.fetch_channel_history_paginated(
                    channel_id, limit=max(1, args.history_limit), max_pages=1
                )
                add_check(
                    "Slack history",
                    len(history) > 0,
                    f"channel={channel_id} count={len(history)}",
                    extra={"pagination": slack.get_pagination_stats()},
                )
            except Exception as exc:
                add_check("Slack history", False, str(exc))
        else:
            add_check("Slack history", True, "skipped (no channel configured)")

        thread_ts = args.thread_ts or _pick_thread_ts(history)
        if channel_id and thread_ts:
            try:
                replies = slack.fetch_thread_replies_paginated(
                    channel_id,
                    thread_ts=thread_ts,
                    limit=max(1, args.reply_limit),
                    max_pages=1,
                )
                add_check(
                    "Slack thread replies",
                    len(replies) > 0,
                    f"thread_ts={thread_ts} count={len(replies)}",
                    extra={"pagination": slack.get_pagination_stats()},
                )
            except Exception as exc:
                add_check("Slack thread replies", False, str(exc))
        else:
            add_check("Slack thread replies", True, "skipped (no thread available)")

        notion_page = args.notion_page or _pick_notion_page_id(config)
        if notion_page:
            try:
                accessible = notion.check_page_access(notion_page)
                add_check("Notion page access", accessible, f"page={notion_page}")
            except Exception as exc:
                add_check("Notion page access", False, str(exc))
        else:
            add_check("Notion page access", True, "skipped (no Notion page configured)")
    finally:
        session.close()

    if args.json:
        print(json.dumps({"ok": overall_ok, "checks": checks}, indent=2))
    else:
        for check in checks:
            print(_status_line(check["name"], bool(check["ok"]), str(check["detail"])))
            if isinstance(check.get("extra"), dict):
                print(f"      {json.dumps(check['extra'])}")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
