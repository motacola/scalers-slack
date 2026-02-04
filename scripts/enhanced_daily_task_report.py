#!/usr/bin/env python3
"""Enhanced daily Slack task report with filtering, structuring, and multiple output formats."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.browser_automation import BrowserAutomationConfig, BrowserSession
from src.cache_manager import CacheManager
from src.config_loader import load_config
from src.enhanced_browser_automation import EnhancedSlackBrowserClient
from src.report_generator import ReportGenerator
from src.task_processor import (
    Task,
    deduplicate_tasks,
    filter_actionable_tasks,
    process_message,
)

DEFAULT_TEAM_MEMBERS = {
    "Christopher Belgrave",
    "Francisco",
    "Italo Germando",
    "Lisa Appleby",
    "Craig Noonan",
}

DEFAULT_CHANNELS = [
    "ss-website-pod",
    "ss-website-tickets",
    "standup",
]

DEFAULT_PROJECT_CHANNELS = [
    "ss-magnify-website-management-and-hosting-wp",
    "ss-eds-pumps-website-management",
    "ss-seaside-toolbox-website",
]


def _build_browser_config(settings: dict[str, Any]) -> BrowserAutomationConfig:
    """Build browser automation config from settings."""
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


def _is_ticket_complete(text: str) -> bool:
    """Check if text indicates a completed ticket."""
    lower = text.lower()
    return "ticket complete" in lower or "ticket completed" in lower


def fetch_messages_with_cache(
    slack: EnhancedSlackBrowserClient,
    cache: CacheManager,
    channel_id: str,
    channel_name: str,
    start: datetime,
    end: datetime,
    max_pages: int = 10,
) -> list[dict[str, Any]]:
    """Fetch messages with caching support."""
    cache_key = f"conversations.history:{channel_id}"
    params = {
        "channel": channel_id,
        "oldest": str(start.timestamp()),
        "latest": str(end.timestamp()),
        "limit": 200,
    }

    # Try cache first
    cached_data = cache.get(cache_key, params)
    if cached_data is not None:
        print(f"  Using cached data for channel {channel_id}")
        return cast(list[dict[str, Any]], cached_data)

    # Fetch from API
    messages = slack.fetch_channel_history_with_permalinks(
        channel_id=channel_id,
        channel_name=channel_name,
        oldest=str(start.timestamp()),
        latest=str(end.timestamp()),
        limit=200,
        max_pages=max_pages,
    )

    # Cache the result
    cache.set(cache_key, params, messages)
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Enhanced daily Slack task report")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--date", help="Date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--output", default="output/daily_task_report", help="Output path (without extension)")
    parser.add_argument("--format", choices=["csv", "json", "markdown", "html", "all"], default="all",
                        help="Output format")
    parser.add_argument("--group-by", choices=["owner", "client", "none"], default="owner",
                        help="Group tasks by")
    parser.add_argument("--channels", help="Comma-separated channel names (overrides defaults)")
    parser.add_argument("--project-channels", help="Comma-separated project channel names")
    parser.add_argument("--include-mentions-search", action="store_true",
                        help="Include mentions search")
    parser.add_argument("--team-members", help="Comma-separated team member names")
    parser.add_argument("--actionable-only", action="store_true",
                        help="Only include actionable tasks")
    parser.add_argument("--cache-dir", default=".cache", help="Cache directory")
    parser.add_argument("--cache-ttl", type=int, default=3600, help="Cache TTL in seconds")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        return 1

    # Determine date
    if args.date:
        date = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        date = datetime.now()

    date_str = date.strftime("%Y-%m-%d")
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    print(f"Generating task report for {date_str}")

    # Determine channels
    channels = args.channels.split(",") if args.channels else DEFAULT_CHANNELS
    project_channels = args.project_channels.split(",") if args.project_channels else DEFAULT_PROJECT_CHANNELS
    all_channels = channels + project_channels

    # Determine team members
    team_members = None
    if args.team_members:
        team_members = set(args.team_members.split(","))
    elif args.actionable_only:
        team_members = DEFAULT_TEAM_MEMBERS

    # Initialize cache
    cache = None if args.no_cache else CacheManager(args.cache_dir, args.cache_ttl)

    # Build browser config
    settings = config.get("settings", {})
    browser_settings = settings.get("browser_automation", {})
    browser_config = _build_browser_config(browser_settings)

    # Build name -> id map from config to avoid extra API calls
    channel_map = {
        p.get("name"): p.get("slack_channel_id")
        for p in config.get("projects", [])
        if p.get("name") and p.get("slack_channel_id")
    }

    # Initialize browser session
    session = BrowserSession(browser_config)
    slack = EnhancedSlackBrowserClient(session, browser_config)

    tasks: list[Task] = []

    try:
        # Resolve channel IDs
        print("Resolving channel IDs...")
        channel_ids: dict[str, str] = {}
        for channel_name in all_channels:
            try:
                channel_id = channel_map.get(channel_name) or slack.resolve_channel_id(channel_name)
                if channel_id:
                    channel_ids[channel_name] = channel_id
                else:
                    print(f"  Warning: Could not resolve channel {channel_name}")
            except Exception as e:
                print(f"  Error resolving channel {channel_name}: {e}")

        # Fetch messages from channels
        print(f"\nFetching messages from {len(channel_ids)} channels...")
        for channel_name, channel_id in channel_ids.items():
            print(f"  Processing channel: {channel_name}")
            try:
                if cache:
                    messages = fetch_messages_with_cache(
                        slack, cache, channel_id, channel_name, start, end, max_pages=10
                    )
                else:
                    messages = slack.fetch_channel_history_with_permalinks(
                        channel_id=channel_id,
                        channel_name=channel_name,
                        oldest=str(start.timestamp()),
                        latest=str(end.timestamp()),
                        limit=200,
                        max_pages=10,
                    )

                for msg in messages:
                    text = msg.get("text") or ""
                    if not text:
                        continue

                    # Skip completed tickets in ticket channel
                    if channel_name == "ss-website-tickets" and _is_ticket_complete(text):
                        continue

                    # Get user name
                    user_id = msg.get("user") or ""
                    user_name = user_id  # Simplified - could resolve via API

                    # Process message into task
                    task = process_message(msg, channel_name, user_name, team_members)
                    if task:
                        tasks.append(task)

            except Exception as e:
                print(f"    Error processing channel {channel_name}: {e}")

        # Search for mentions
        if args.include_mentions_search:
            print("\nSearching for mentions...")
            queries = ["to:@christopher", '"Christopher Belgrave"', "@Christopher Belgrave"]
            seen = set()

            for query in queries:
                try:
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

                        user_name = msg.get("username") or msg.get("user") or "unknown"
                        task = process_message(msg, channel_name, user_name, team_members)
                        if task:
                            tasks.append(task)

                except Exception as e:
                    print(f"  Error searching with query '{query}': {e}")

    finally:
        session.close()

    print(f"\nProcessing {len(tasks)} raw tasks...")

    # Deduplicate tasks
    tasks = deduplicate_tasks(tasks)
    print(f"After deduplication: {len(tasks)} tasks")

    # Filter to actionable only if requested
    if args.actionable_only:
        tasks = filter_actionable_tasks(tasks)
        print(f"After actionable filter: {len(tasks)} tasks")

    # Generate reports
    print("\nGenerating reports...")
    generator = ReportGenerator(tasks, date_str)

    output_base = args.output
    if args.format in ("csv", "all"):
        generator.to_csv(f"{output_base}.csv")
    if args.format in ("json", "all"):
        generator.to_json(f"{output_base}.json")
    if args.format in ("markdown", "all"):
        generator.to_markdown(f"{output_base}.md", group_by=args.group_by)
    if args.format in ("html", "all"):
        generator.to_html(f"{output_base}.html", group_by=args.group_by)

    # Print summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Date: {date_str}")
    print(f"Total Tasks: {len(tasks)}")
    print(f"Actionable Tasks: {sum(1 for t in tasks if t.is_actionable)}")
    print(f"High Priority: {sum(1 for t in tasks if t.priority == 'High')}")
    print(f"Medium Priority: {sum(1 for t in tasks if t.priority == 'Medium')}")
    print(f"Low Priority: {sum(1 for t in tasks if t.priority == 'Low')}")

    if cache:
        stats = cache.get_stats()
        print(f"\nCache: {stats['total_files']} files, {stats['expired_files']} expired")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
