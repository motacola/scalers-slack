import argparse
import csv
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.browser_automation import BrowserAutomationConfig, BrowserSession, SlackBrowserClient
from src.config_loader import load_config

DEFAULT_COLUMNS = [
    "Status",
    "Priority",
    "Due Date",
    "Task",
    "Channel",
    "Owner",
    "Next Step",
    "Link",
    "Source",
]

DATE_RE = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_text(msg: dict[str, Any]) -> str:
    text = msg.get("text") or ""
    if text:
        return text
    blocks = msg.get("blocks") or []
    for block in blocks:
        if isinstance(block, dict):
            btext = block.get("text", {})
            if isinstance(btext, dict):
                t = btext.get("text")
                if t:
                    return t
    return ""


def _extract_due_date(text: str) -> str:
    match = DATE_RE.search(text)
    return match.group(0) if match else ""


def _is_ticket_complete(text: str) -> bool:
    lower = text.lower()
    return "ticket complete" in lower or "ticket completed" in lower


def _build_browser_config(settings: dict[str, Any]) -> BrowserAutomationConfig:
    return BrowserAutomationConfig(
        enabled=True,
        storage_state_path=settings.get("storage_state_path", "browser_storage_state.json"),
        headless=settings.get("headless", False),
        slow_mo_ms=int(settings.get("slow_mo_ms", 0) or 0),
        timeout_ms=int(settings.get("timeout_ms", 30000) or 30000),
        slack_workspace_id=settings.get("slack_workspace_id", ""),
        slack_client_url=settings.get("slack_client_url", "https://app.slack.com/client"),
        slack_api_base_url=settings.get("slack_api_base_url", "https://slack.com/api"),
        auto_save_storage_state=settings.get("auto_save_storage_state", True),
        interactive_login=settings.get("interactive_login", True),
        browser_channel=settings.get("browser_channel"),
        user_data_dir=settings.get("user_data_dir"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily Slack task report (CSV)")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--date", help="Date (YYYY-MM-DD). Defaults to today in local timezone.")
    parser.add_argument("--output", default="output/daily_task_report.csv", help="CSV output path")
    parser.add_argument(
        "--people",
        default="Francisco Oliveira,Italo Germando,Christopher Belgrave",
        help="Comma-separated display names to include",
    )
    parser.add_argument(
        "--channels",
        default="ss-website-pod,ss-website-tickets,standup",
        help="Comma-separated channel names to scan",
    )
    parser.add_argument(
        "--project-channels",
        default="",
        help="Comma-separated additional project channel names",
    )
    parser.add_argument(
        "--include-mentions-search",
        action="store_true",
        help="Also search Slack for @mentions of Christopher Belgrave",
    )

    args = parser.parse_args()

    config = load_config(args.config)
    settings = config.get("settings", {})
    browser_settings = settings.get("browser_automation", {})

    local_tz = datetime.now().astimezone().tzinfo
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target = datetime.now().astimezone().date()

    start = datetime.combine(target, datetime.min.time(), tzinfo=local_tz)
    end = start + timedelta(days=1)

    people = {p.strip() for p in args.people.split(",") if p.strip()}
    channels = [c.strip() for c in args.channels.split(",") if c.strip()]
    project_channels = [c.strip() for c in args.project_channels.split(",") if c.strip()]
    all_channels = channels + project_channels

    name_to_id: dict[str, str] = {}
    for project in config.get("projects", []):
        name = project.get("name")
        channel_id = project.get("slack_channel_id")
        if name and channel_id:
            name_to_id[name] = channel_id

    channel_ids = {name: name_to_id.get(name) for name in all_channels if name_to_id.get(name)}

    session = BrowserSession(_build_browser_config(browser_settings))
    slack = SlackBrowserClient(session, session.config)

    user_cache: dict[str, str | None] = {}

    def resolve_user(user_id: str | None) -> str | None:
        if not user_id:
            return None
        if user_id in user_cache:
            return user_cache[user_id]
        try:
            info = slack.get_user_info(user_id)
            name = info.get("real_name") or info.get("name")
        except Exception:
            name = None
        user_cache[user_id] = name
        return name

    rows: list[dict[str, str]] = []

    try:
        for channel_name, channel_id in channel_ids.items():
            messages = slack.fetch_channel_history_paginated(
                channel_id=channel_id,
                oldest=str(start.timestamp()),
                latest=str(end.timestamp()),
                limit=200,
                max_pages=10,
            )
            for msg in messages:
                text = _normalize(_extract_text(msg))
                if not text:
                    continue
                user_name = resolve_user(msg.get("user")) or msg.get("user") or ""

                if channel_name == "ss-website-tickets" and _is_ticket_complete(text):
                    continue

                if user_name not in people and "Christopher" not in text and "<@" not in text:
                    continue

                due_date = _extract_due_date(text) if channel_name == "ss-website-tickets" else ""

                rows.append(
                    {
                        "Status": "Open",
                        "Priority": "",
                        "Due Date": due_date,
                        "Task": text,
                        "Channel": channel_name,
                        "Owner": user_name,
                        "Next Step": "",
                        "Link": msg.get("permalink", ""),
                        "Source": "slack",
                    }
                )

        if args.include_mentions_search:
            queries = ["to:@christopher", '"Christopher Belgrave"', "@Christopher Belgrave"]
            seen = set()
            for query in queries:
                matches = slack.search_messages_paginated(query=query, count=100, max_pages=5)
                for msg in matches:
                    ts = msg.get("ts")
                    if not ts:
                        continue
                    ts_float = float(ts)
                    if not (start.timestamp() <= ts_float < end.timestamp()):
                        continue
                    channel = msg.get("channel", {})
                    channel_name = channel.get("name") or channel.get("id") or "unknown"
                    key = (channel_name, ts)
                    if key in seen:
                        continue
                    seen.add(key)
                    text = _normalize(msg.get("text") or "")
                    if not text:
                        continue
                    rows.append(
                        {
                            "Status": "Open",
                            "Priority": "",
                            "Due Date": "",
                            "Task": text,
                            "Channel": channel_name,
                            "Owner": msg.get("username") or msg.get("user") or msg.get("user_id") or "",
                            "Next Step": "",
                            "Link": msg.get("permalink", ""),
                            "Source": "slack_search",
                        }
                    )
    finally:
        session.close()

    output_path = args.output
    output_dir = output_path.rsplit("/", 1)[0] if "/" in output_path else ""
    if output_dir:
        import os
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DEFAULT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
