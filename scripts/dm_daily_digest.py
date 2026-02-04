import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

# Ensure repo root is on sys.path so `src.*` imports work when running as a script.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.browser_automation import BrowserAutomationConfig, BrowserSession, SlackBrowserClient
from src.config_loader import load_config
from src.report_generator import ReportGenerator
from src.task_processor import Task, deduplicate_tasks, process_message


def _coerce_int(value: object, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            return int(value)
        return default
    except (TypeError, ValueError):
        return default


def _build_browser_config(settings: dict[str, Any], *, headless_override: bool | None = None) -> BrowserAutomationConfig:
    return BrowserAutomationConfig(
        enabled=True,
        storage_state_path=settings.get("storage_state_path", "browser_storage_state.json"),
        headless=bool(headless_override) if headless_override is not None else bool(settings.get("headless", False)),
        slow_mo_ms=_coerce_int(settings.get("slow_mo_ms"), 0),
        timeout_ms=_coerce_int(settings.get("timeout_ms"), 30000),
        slack_workspace_id=settings.get("slack_workspace_id", ""),
        slack_client_url=settings.get("slack_client_url", "https://app.slack.com/client"),
        slack_api_base_url=settings.get("slack_api_base_url", "https://slack.com/api"),
        auto_save_storage_state=bool(settings.get("auto_save_storage_state", True)),
        interactive_login=bool(settings.get("interactive_login", True)),
        interactive_login_timeout_ms=_coerce_int(settings.get("interactive_login_timeout_ms"), 120000),
        browser_channel=settings.get("browser_channel"),
        user_data_dir=settings.get("user_data_dir"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Friendly daily digest from Slack (browser automation; no posting)")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the browser in headless mode (recommended for scheduled runs)",
    )
    parser.add_argument(
        "--channels",
        default="ss-website-pod,ss-website-tickets,standup",
        help=(
            "Which channels to include (comma-separated). You can use channel names from config.json (projects[].name) "
            "or raw Slack channel IDs like C0123ABC. Default: ss-website-pod,ss-website-tickets,standup"
        ),
    )
    parser.add_argument(
        "--include-dms",
        action="store_true",
        help="Also include DMs (useful, but usually noisier)",
    )
    parser.add_argument("--max-dms", type=int, default=60, help="Max DM conversations to scan (when --include-dms is set)")
    parser.add_argument(
        "--important",
        action="store_true",
        help="Shortcut: include the main channels (pod + tickets + standup)",
    )
    parser.add_argument(
        "--owners",
        default="",
        help="Only include items from these people (comma-separated, e.g. 'Francisco,Italo')",
    )
    parser.add_argument(
        "--dev-tasks",
        action="store_true",
        help="Shortcut for: --owners Francisco,Italo",
    )
    parser.add_argument(
        "--format",
        choices=["html", "md"],
        default="html",
        help="Output format for review (default: html)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output path (default: output/dm_daily_digest_YYYY_MM_DD.<html|md>)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated report after writing it",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    settings = cast(dict[str, Any], config.get("settings", {}))
    browser_settings = cast(dict[str, Any], settings.get("browser_automation", {}))

    # Build a lookup of config project name -> channel id
    projects = cast(list[dict[str, Any]], config.get("projects", []))
    project_channel_by_name: dict[str, str] = {}
    for p in projects:
        name = cast(str, p.get("name") or "").strip()
        cid = cast(str, p.get("slack_channel_id") or "").strip()
        if name and cid:
            project_channel_by_name[name] = cid

    # Use UTC for timestamps, Slack expects unix seconds.
    now = datetime.now(timezone.utc)
    since_dt = now - timedelta(hours=int(args.hours))
    oldest = str(since_dt.timestamp())
    latest = str(now.timestamp())

    out_path = args.output
    if not out_path:
        stamp = now.astimezone().strftime("%Y_%m_%d")
        ext = "html" if args.format == "html" else "md"
        out_path = f"output/dm_daily_digest_{stamp}.{ext}"

    session = BrowserSession(_build_browser_config(browser_settings, headless_override=(True if args.headless else None)))
    slack = SlackBrowserClient(session, session.config)

    tasks: list[Task] = []

    try:
        # Cache user names (for DMs and channel posts)
        user_name_cache: dict[str, str] = {}

        def resolve_user_name(user_id: str) -> str:
            if user_id in user_name_cache:
                return user_name_cache[user_id]
            info = slack.get_user_info(user_id)
            name = cast(str, (info.get("real_name") or info.get("name") or user_id))
            user_name_cache[user_id] = name
            return name

        def scan_channel(channel_id: str, label: str) -> None:
            """Pull messages + thread replies from a channel and turn them into Tasks."""
            messages = slack.fetch_channel_history_paginated(
                channel_id=channel_id,
                oldest=oldest,
                latest=latest,
                limit=200,
                max_pages=5,
            )

            for msg in messages:
                ts = cast(str, msg.get("ts") or "")
                if ts and not msg.get("permalink"):
                    pl = slack.get_message_permalink(channel_id, ts)
                    if pl:
                        msg["permalink"] = pl

                owner_id = cast(str, msg.get("user") or "")
                owner = resolve_user_name(owner_id) if owner_id else "unknown"

                t = process_message(msg, channel_name=label, owner=owner)
                if t:
                    tasks.append(t)

                reply_count = int(msg.get("reply_count") or 0)
                if reply_count > 0:
                    thread_ts = cast(str, msg.get("thread_ts") or ts)
                    if not thread_ts:
                        continue
                    replies = slack.fetch_thread_replies_paginated(
                        channel_id=channel_id,
                        thread_ts=thread_ts,
                        limit=200,
                        max_pages=5,
                    )
                    for r in replies[1:]:
                        rts = cast(str, r.get("ts") or "")
                        if rts and not r.get("permalink"):
                            pl = slack.get_message_permalink(channel_id, rts)
                            if pl:
                                r["permalink"] = pl
                        owner_id = cast(str, r.get("user") or "")
                        owner = resolve_user_name(owner_id) if owner_id else "unknown"
                        rt = process_message(r, channel_name=label, owner=owner)
                        if rt:
                            tasks.append(rt)

        # 1) Important channels
        raw = [c.strip() for c in str(args.channels).split(",") if c.strip()]
        if args.important:
            raw = ["ss-website-pod", "ss-website-tickets", "standup"]
        if not raw:
            raw = ["ss-website-pod", "ss-website-tickets", "standup"]

        for c in raw:
            # allow either a config project name OR a raw channel id
            channel_id = project_channel_by_name.get(c, c)
            if not channel_id or not channel_id.startswith("C"):
                available = ", ".join(sorted(project_channel_by_name.keys()))
                raise SystemExit(
                    f"I can't find the channel '{c}'.\n\n"
                    f"Use a channel ID (like C0123ABC) or one of the names in config.json.\n"
                    f"Available names: {available}"
                )
            scan_channel(channel_id=channel_id, label=f"#{c}")

        # 2) Optional DMs
        if args.include_dms:
            dms = slack.list_conversations_paginated(types="im,mpim", limit=200, max_pages=10, exclude_archived=True)
            dms = dms[: int(args.max_dms)]

            for dm in dms:
                channel_id = cast(str, dm.get("id") or "")
                if not channel_id:
                    continue

                dm_label = "dm"
                if dm.get("is_im") and dm.get("user"):
                    dm_label = f"dm--{resolve_user_name(cast(str, dm.get('user')))}"
                elif dm.get("is_mpim"):
                    dm_label = f"dm--group"

                scan_channel(channel_id=channel_id, label=dm_label)

        tasks = deduplicate_tasks(tasks)

        # Optional: focus on specific owners (e.g., the devs)
        owners_raw = str(args.owners or "").strip()
        if args.dev_tasks:
            owners_raw = "Francisco,Italo"
        if owners_raw:
            wanted = {o.strip().lower() for o in owners_raw.split(",") if o.strip()}
            if wanted:
                tasks = [t for t in tasks if (t.owner or "").strip().lower() in wanted]

        gen = ReportGenerator(tasks=tasks, date=now.astimezone().strftime("%Y-%m-%d"))
        if args.format == "html":
            gen.to_html(out_path, group_by="owner")
        else:
            gen.to_markdown(out_path, group_by="owner")
        print(f"Wrote DM digest to {out_path}")
        if args.open:
            try:
                import subprocess

                subprocess.run(["open", out_path], check=False)
            except Exception:
                pass
        return 0
    finally:
        try:
            session.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
