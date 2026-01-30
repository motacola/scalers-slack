#!/usr/bin/env python3
"""Daily task report using pure browser automation - no API keys required."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.cache_manager import CacheManager
from src.config_manager import ConfigManager, get_default_config
from src.historical_comparison import HistoricalTracker
from src.pure_browser_automation import PureBrowserAutomationManager, PureBrowserConfig
from src.report_generator import ReportGenerator
from src.task_processor import (
    Task,
    deduplicate_tasks,
    filter_actionable_tasks,
    process_message,
)


def _build_browser_config(config: Any) -> PureBrowserConfig:
    """Build pure browser config from settings."""
    return PureBrowserConfig(
        storage_state_path=config.browser_automation.storage_state_path,
        headless=config.browser_automation.headless,
        slow_mo_ms=config.browser_automation.slow_mo_ms,
        timeout_ms=config.browser_automation.timeout_ms,
        workspace_id=config.browser_automation.slack_workspace_id,
        slack_workspace_url=config.browser_automation.slack_client_url,
    )


def _is_ticket_complete(text: str) -> bool:
    """Check if text indicates a completed ticket."""
    lower = text.lower()
    return "ticket complete" in lower or "ticket completed" in lower


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Daily Slack task report - Pure browser automation (no API keys)"
    )
    parser.add_argument("--config", default="config/daily_report_defaults.json",
                        help="Path to configuration file")
    parser.add_argument("--date", help="Date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--output", default="output/daily_task_report",
                        help="Output path (without extension)")
    parser.add_argument("--format", choices=["csv", "json", "markdown", "html", "all"],
                        default=None, help="Output format (overrides config)")
    parser.add_argument("--group-by", choices=["owner", "client", "none"],
                        default=None, help="Group tasks by (overrides config)")
    parser.add_argument("--channels", help="Comma-separated channel names (overrides config)")
    parser.add_argument("--project-channels", help="Comma-separated project channel names")
    parser.add_argument("--include-mentions-search", action="store_true",
                        help="Include mentions search")
    parser.add_argument("--team-members", help="Comma-separated team member names")
    parser.add_argument("--actionable-only", action="store_true",
                        help="Only include actionable tasks")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument("--compare", action="store_true",
                        help="Generate comparison with previous day")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--create-storage-state", action="store_true",
                        help="Create browser storage state with interactive login")

    args = parser.parse_args()

    # Handle storage state creation
    if args.create_storage_state:
        from src.pure_browser_automation import create_storage_state_interactive
        create_storage_state_interactive()
        return 0

    # Load configuration
    config_manager = ConfigManager(args.config)
    config = config_manager.merge_with_args(args)

    # Override headless mode if specified
    if args.headless:
        config.browser_automation.headless = True

    # Determine date
    if args.date:
        date = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        date = datetime.now()

    date_str = date.strftime("%Y-%m-%d")
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    print(f"=" * 60)
    print(f"Daily Task Report (Pure Browser) - {date_str}")
    print(f"=" * 60)

    # Get all channels
    all_channels = config.channels + config.project_channels
    print(f"\nChannels to scan: {len(all_channels)}")
    for ch in all_channels:
        print(f"  - {ch}")

    # Initialize cache
    cache = None if args.no_cache or not config.cache.enabled else CacheManager(
        config.cache.directory, config.cache.ttl_seconds
    )

    # Initialize pure browser automation
    browser_config = _build_browser_config(config)
    tasks: list[Task] = []

    try:
        with PureBrowserAutomationManager(browser_config) as slack:
            print("\nConnected to Slack via browser automation")

            # Process each channel
            for channel_name in all_channels:
                print(f"\n  Processing: {channel_name}")
                try:
                    # Navigate to channel
                    if not slack.navigate_to_channel(channel_name):
                        print(f"    ✗ Could not navigate to channel")
                        continue

                    # Fetch messages
                    messages = slack.fetch_messages(
                        since_timestamp=start.timestamp(),
                        until_timestamp=end.timestamp(),
                        max_messages=1000,
                    )
                    print(f"    Found {len(messages)} messages")

                    processed = 0
                    for msg in messages:
                        text = msg.get("text") or ""
                        if not text:
                            continue

                        # Skip completed tickets in ticket channel
                        if channel_name == "ss-website-tickets" and _is_ticket_complete(text):
                            continue

                        # Get user name
                        user_name = msg.get("user") or "Unknown"

                        # Process message into task
                        task = process_message(
                            msg, channel_name, user_name,
                            set(config.team_members) if config.team_members else None
                        )
                        if task:
                            tasks.append(task)
                            processed += 1

                    print(f"    Processed {processed} tasks")

                except Exception as e:
                    print(f"    Error: {e}")

            # Search for mentions if enabled
            if config.filtering.include_mentions_search:
                print("\nSearching for mentions...")
                queries = ["@christopher", "Christopher Belgrave"]
                seen = set()

                for query in queries:
                    try:
                        matches = slack.search_messages(query=query, max_results=100)
                        new_matches = 0
                        for msg in matches:
                            ts = msg.get("ts", "")
                            if not ts:
                                continue
                            try:
                                ts_float = float(ts)
                                if not (start.timestamp() <= ts_float < end.timestamp()):
                                    continue
                            except (ValueError, TypeError):
                                continue

                            channel_name = msg.get("channel", "unknown")
                            key = (channel_name, ts)
                            if key in seen:
                                continue
                            seen.add(key)

                            user_name = msg.get("username") or "unknown"
                            task = process_message(
                                msg, channel_name, user_name,
                                set(config.team_members) if config.team_members else None
                            )
                            if task:
                                tasks.append(task)
                                new_matches += 1

                        print(f"  Query '{query}': {new_matches} new matches")

                    except Exception as e:
                        print(f"  Error searching '{query}': {e}")

    except Exception as e:
        print(f"\nBrowser automation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print(f"\n{'=' * 60}")
    print("Processing Results")
    print(f"{'=' * 60}")

    print(f"\nRaw tasks extracted: {len(tasks)}")

    # Deduplicate tasks
    tasks = deduplicate_tasks(tasks)
    print(f"After deduplication: {len(tasks)}")

    # Filter to actionable only if requested
    if config.filtering.actionable_only:
        tasks = filter_actionable_tasks(tasks)
        print(f"After actionable filter: {len(tasks)}")

    # Save snapshot for historical tracking
    if config.historical_tracking.enabled:
        tracker = HistoricalTracker(config.historical_tracking.snapshots_directory)
        snapshot_path = tracker.save(tasks, date_str)
        print(f"\nSnapshot saved: {snapshot_path}")

    # Generate comparison if requested
    if args.compare and config.historical_tracking.enabled:
        print("\nGenerating comparison with previous day...")
        comparison_path = f"{args.output}_comparison.md"
        report = tracker.generate_report(date_str, output_path=comparison_path)
        if report:
            print(f"Comparison saved: {comparison_path}")
        else:
            print("No previous snapshot found for comparison")

    # Generate reports
    print(f"\n{'=' * 60}")
    print("Generating Reports")
    print(f"{'=' * 60}")

    generator = ReportGenerator(tasks, date_str)

    output_format = args.format or config.output.default_format
    group_by = args.group_by or config.output.group_by

    output_base = args.output
    if output_format in ("csv", "all"):
        generator.to_csv(f"{output_base}.csv")
    if output_format in ("json", "all"):
        generator.to_json(f"{output_base}.json")
    if output_format in ("markdown", "all"):
        generator.to_markdown(f"{output_base}.md", group_by=group_by)
    if output_format in ("html", "all"):
        generator.to_html(f"{output_base}.html", group_by=group_by)

    # Print summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Date: {date_str}")
    print(f"Total Tasks: {len(tasks)}")
    print(f"Actionable Tasks: {sum(1 for t in tasks if t.is_actionable)}")
    print(f"High Priority: {sum(1 for t in tasks if t.priority == 'High')}")
    print(f"Medium Priority: {sum(1 for t in tasks if t.priority == 'Medium')}")
    print(f"Low Priority: {sum(1 for t in tasks if t.priority == 'Low')}")

    # Group by owner for summary
    by_owner: dict[str, int] = {}
    for task in tasks:
        owner = task.owner or "Unknown"
        by_owner[owner] = by_owner.get(owner, 0) + 1

    print(f"\nTasks by Owner:")
    for owner, count in sorted(by_owner.items(), key=lambda x: -x[1]):
        print(f"  {owner}: {count}")

    if cache:
        stats = cache.get_stats()
        print(f"\nCache: {stats['total_files']} files, {stats['expired_files']} expired")

    print(f"\n{'=' * 60}")
    print("Done!")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())