#!/usr/bin/env python3
"""Run browser-only Slack/Notion smoke checks without API keys."""

from __future__ import annotations

import argparse
import json
import sys
import time
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


def _status_line(name: str, ok: bool, detail: str, elapsed_ms: int | None = None) -> str:
    timing = f" ({elapsed_ms}ms)" if isinstance(elapsed_ms, int) else ""
    return f"[{'OK' if ok else 'FAIL'}]{timing} {name}: {detail}"


def _normalize_ts_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "." in text:
        whole, frac = text.split(".", 1)
        return f"{whole}.{frac[:6].ljust(6, '0')}"
    if text.isdigit():
        return f"{text}.000000"
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser-only smoke checks (no API keys required).")
    parser.add_argument("--config", default="config/config.json", help="Path to config.json")
    parser.add_argument("--channel-id", help="Slack channel ID override")
    parser.add_argument("--thread-ts", help="Slack thread ts override")
    parser.add_argument("--notion-page", help="Notion page URL/ID override")
    parser.add_argument("--history-limit", type=int, default=20, help="Messages to fetch from channel history")
    parser.add_argument("--reply-limit", type=int, default=30, help="Replies to fetch from thread")
    parser.add_argument("--force-dom", action="store_true", help="Force DOM fallback by disabling Slack API calls")
    parser.add_argument("--skip-thread", action="store_true", help="Skip Slack thread reply check")
    parser.add_argument("--skip-notion", action="store_true", help="Skip Notion page access check")
    parser.add_argument(
        "--strict-thread",
        action="store_true",
        help="Use full thread pane extraction (default force-dom mode uses a faster history-derived check)",
    )
    parser.add_argument(
        "--interactive-timeout-ms",
        type=int,
        default=20000,
        help="Per-page readiness timeout in milliseconds (lower is faster for smoke runs)",
    )
    parser.add_argument(
        "--page-timeout-ms",
        type=int,
        default=15000,
        help="Navigation/action timeout in milliseconds",
    )
    parser.add_argument(
        "--smart-wait-timeout-ms",
        type=int,
        default=8000,
        help="Network-idle smart-wait timeout in milliseconds",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Browser action retry attempts during smoke checks",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    config = load_config(args.config)
    browser_settings = config.get("settings", {}).get("browser_automation", {})
    browser_config = _build_browser_config(browser_settings)
    browser_config.enabled = True
    interactive_timeout_ms = max(1000, int(args.interactive_timeout_ms))
    browser_config.interactive_login_timeout_ms = interactive_timeout_ms
    browser_config.timeout_ms = max(3000, int(args.page_timeout_ms))
    browser_config.smart_wait_timeout_ms = max(1000, int(args.smart_wait_timeout_ms))
    browser_config.smart_wait_stability_ms = min(int(browser_config.smart_wait_stability_ms or 600), 350)
    browser_config.max_retries = max(1, int(args.max_retries))

    session = BrowserSession(browser_config)
    slack = SlackBrowserClient(session, browser_config)
    notion = NotionBrowserClient(session, browser_config)

    checks: list[dict[str, Any]] = []
    overall_ok = True

    def add_check(
        name: str,
        ok: bool,
        detail: str,
        extra: dict[str, Any] | None = None,
        elapsed_ms: int | None = None,
    ) -> None:
        nonlocal overall_ok
        if not ok:
            overall_ok = False
        record = {"name": name, "ok": ok, "detail": detail}
        if isinstance(elapsed_ms, int):
            record["elapsed_ms"] = max(0, elapsed_ms)
        if extra:
            record["extra"] = extra
        checks.append(record)

    run_start = time.perf_counter()

    try:
        session.start()

        if args.force_dom:

            def _disabled_api(*_a, **_kw):
                raise RuntimeError("not_authed")

            slack._slack_api_call = _disabled_api  # type: ignore[method-assign]

        check_start = time.perf_counter()
        try:
            auth = slack.auth_test()
            team_id = auth.get("team_id") or auth.get("team") or "unknown"
            add_check(
                "Slack auth",
                bool(auth.get("ok", True)),
                f"team={team_id}",
                elapsed_ms=int((time.perf_counter() - check_start) * 1000),
            )
        except Exception as exc:
            add_check(
                "Slack auth",
                False,
                str(exc),
                elapsed_ms=int((time.perf_counter() - check_start) * 1000),
            )

        check_start = time.perf_counter()
        try:
            conversations = slack.list_conversations_paginated(limit=20, max_pages=1)
            add_check(
                "Slack conversations",
                len(conversations) > 0,
                f"count={len(conversations)}",
                extra={"pagination": slack.get_pagination_stats()},
                elapsed_ms=int((time.perf_counter() - check_start) * 1000),
            )
        except Exception as exc:
            add_check(
                "Slack conversations",
                False,
                str(exc),
                elapsed_ms=int((time.perf_counter() - check_start) * 1000),
            )

        channel_id = args.channel_id or _pick_channel_id(config)
        history: list[dict[str, Any]] = []
        check_start = time.perf_counter()
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
                    elapsed_ms=int((time.perf_counter() - check_start) * 1000),
                )
            except Exception as exc:
                add_check(
                    "Slack history",
                    False,
                    str(exc),
                    elapsed_ms=int((time.perf_counter() - check_start) * 1000),
                )
        else:
            add_check(
                "Slack history",
                True,
                "skipped (no channel configured)",
                elapsed_ms=int((time.perf_counter() - check_start) * 1000),
            )

        thread_ts = args.thread_ts or _pick_thread_ts(history)
        check_start = time.perf_counter()
        if args.skip_thread:
            add_check(
                "Slack thread replies",
                True,
                "skipped (--skip-thread)",
                elapsed_ms=int((time.perf_counter() - check_start) * 1000),
            )
        elif channel_id and thread_ts:
            try:
                if args.force_dom and not args.strict_thread and history:
                    target_thread = _normalize_ts_text(thread_ts)
                    replies = [
                        message
                        for message in history
                        if (
                            _normalize_ts_text(message.get("thread_ts")) == target_thread
                            or _normalize_ts_text(message.get("ts")) == target_thread
                        )
                    ]
                    detail = f"thread_ts={thread_ts} count={len(replies)} (history-derived)"
                else:
                    replies = slack.fetch_thread_replies_paginated(
                        channel_id,
                        thread_ts=thread_ts,
                        limit=max(1, args.reply_limit),
                        max_pages=1,
                    )
                    detail = f"thread_ts={thread_ts} count={len(replies)}"
                add_check(
                    "Slack thread replies",
                    len(replies) > 0,
                    detail,
                    extra={"pagination": slack.get_pagination_stats()},
                    elapsed_ms=int((time.perf_counter() - check_start) * 1000),
                )
            except Exception as exc:
                add_check(
                    "Slack thread replies",
                    False,
                    str(exc),
                    elapsed_ms=int((time.perf_counter() - check_start) * 1000),
                )
        else:
            add_check(
                "Slack thread replies",
                True,
                "skipped (no thread available)",
                elapsed_ms=int((time.perf_counter() - check_start) * 1000),
            )

        notion_page = args.notion_page or _pick_notion_page_id(config)
        check_start = time.perf_counter()
        if args.skip_notion:
            add_check(
                "Notion page access",
                True,
                "skipped (--skip-notion)",
                elapsed_ms=int((time.perf_counter() - check_start) * 1000),
            )
        elif notion_page:
            try:
                accessible = notion.check_page_access(notion_page)
                add_check(
                    "Notion page access",
                    accessible,
                    f"page={notion_page}",
                    elapsed_ms=int((time.perf_counter() - check_start) * 1000),
                )
            except Exception as exc:
                add_check(
                    "Notion page access",
                    False,
                    str(exc),
                    elapsed_ms=int((time.perf_counter() - check_start) * 1000),
                )
        else:
            add_check(
                "Notion page access",
                True,
                "skipped (no Notion page configured)",
                elapsed_ms=int((time.perf_counter() - check_start) * 1000),
            )
    finally:
        session.close()

    elapsed_ms = int((time.perf_counter() - run_start) * 1000)

    if args.json:
        print(json.dumps({"ok": overall_ok, "elapsed_ms": elapsed_ms, "checks": checks}, indent=2))
    else:
        for check in checks:
            print(
                _status_line(
                    check["name"],
                    bool(check["ok"]),
                    str(check["detail"]),
                    check.get("elapsed_ms"),
                )
            )
            if isinstance(check.get("extra"), dict):
                print(f"      {json.dumps(check['extra'])}")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
