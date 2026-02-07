#!/usr/bin/env python3
"""Initialize Task Memory with configurable seed data.

Examples:
  python scripts/init_task_memory.py
  python scripts/init_task_memory.py --date 2026-02-07 --dry-run
  python scripts/init_task_memory.py --from-json config/task_memory_seed.json --memory-path config/task_memory.json
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.task_memory import TaskMemory, TaskSource, TaskStatus, setup_default_team


def _date_arg(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}', expected YYYY-MM-DD") from exc
    return value


def _load_seed_file(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Seed file must contain a top-level JSON object")
    return payload


def build_default_seed(seed_date: str) -> dict[str, Any]:
    """Build the default seed payload for a given date."""
    return {
        "setup_default_team": True,
        "completed_tasks": [
            {
                "task_name": "Captain Clean Location Pages",
                "assignee": "Italo Germando",
                "confirmed_by": "Emily A",
                "source": TaskSource.SLACK_THREAD.value,
                "channel": "ss-captain-clean-website-edits",
                "notes": "Confirmed complete in Slack thread.",
            },
            {
                "task_name": "Captain Clean Service Area Page",
                "assignee": "Italo Germando",
                "confirmed_by": "Emily A",
                "source": TaskSource.SLACK_THREAD.value,
                "channel": "ss-captain-clean-website-edits",
                "notes": "Marked done in Slack thread.",
            },
            {
                "task_name": "Unified Designs",
                "assignee": "Italo Germando",
                "confirmed_by": "Christopher Belgrave",
                "source": TaskSource.USER_CONFIRMATION.value,
                "notes": "Confirmed via operator note.",
            },
            {
                "task_name": "EDS Pumps Services Site Publish",
                "assignee": "Italo Germando",
                "confirmed_by": "Emily A",
                "source": TaskSource.SLACK_THREAD.value,
                "channel": "ss-eds-pumps-website-management",
                "notes": "Marked published in Slack thread.",
            },
        ],
        "standups": [
            {
                "team_member": "Italo Germando",
                "tasks": ["EDS build", "Awful nice guys - promo", "AAA Electrical edits"],
                "date": seed_date,
                "timestamp": f"{seed_date}T09:14:00",
            },
            {
                "team_member": "Francisco Oliveira",
                "tasks": [
                    "My Calgary build - finish up",
                    "Spence and Daves build",
                    "Parker and Co",
                    "Ark Home website checks",
                ],
                "date": seed_date,
                "timestamp": f"{seed_date}T09:44:00",
            },
            {
                "team_member": "Christopher Belgrave",
                "tasks": ["Performance of Maine", "Lake Country", "EDS"],
                "date": seed_date,
                "timestamp": f"{seed_date}T10:46:00",
            },
        ],
        "tasks": [
            {
                "task_name": "EDS Build",
                "assignee": "Italo Germando",
                "status": TaskStatus.IN_PROGRESS.value,
                "source": TaskSource.NOTION.value,
                "priority": "high",
                "notes": "Main site build - design/content to share by end of week",
            },
            {
                "task_name": "Awful Nice Guys Promo",
                "assignee": "Italo Germando",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.SLACK_STANDUP.value,
                "due_date": seed_date,
            },
            {
                "task_name": "AAA Electrical Edits",
                "assignee": "Italo Germando",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.SLACK_STANDUP.value,
                "due_date": seed_date,
            },
            {
                "task_name": "My Calgary Build",
                "assignee": "Francisco Oliveira",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.SLACK_STANDUP.value,
                "due_date": seed_date,
            },
            {
                "task_name": "Spence and Daves Build",
                "assignee": "Francisco Oliveira",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.SLACK_STANDUP.value,
                "due_date": seed_date,
            },
            {
                "task_name": "Parker and Co",
                "assignee": "Francisco Oliveira",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.SLACK_STANDUP.value,
                "due_date": seed_date,
            },
            {
                "task_name": "Ark Home Website Checks",
                "assignee": "Francisco Oliveira",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.SLACK_STANDUP.value,
                "due_date": seed_date,
            },
            {
                "task_name": "RH Coatings",
                "assignee": "Francisco Oliveira",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.NOTION.value,
                "due_date": seed_date,
            },
            {
                "task_name": "Buzz Electrical SEO",
                "assignee": "Francisco Oliveira",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.NOTION.value,
                "due_date": seed_date,
            },
            {
                "task_name": "Buzz Electrical LSA",
                "assignee": "Francisco Oliveira",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.NOTION.value,
                "due_date": seed_date,
            },
            {
                "task_name": "Performance of Maine",
                "assignee": "Christopher Belgrave",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.SLACK_STANDUP.value,
                "due_date": seed_date,
            },
            {
                "task_name": "Lake County Mechanical",
                "assignee": "Christopher Belgrave",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.NOTION.value,
                "due_date": seed_date,
                "priority": "high",
            },
            {
                "task_name": "EDS Content Docs",
                "assignee": "Christopher Belgrave",
                "status": TaskStatus.IN_PROGRESS.value,
                "source": TaskSource.NOTION.value,
                "priority": "high",
                "notes": "LP edit done yesterday, more content work expected",
            },
            {
                "task_name": "Trips Change Insurance",
                "assignee": "Christopher Belgrave",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.NOTION.value,
                "due_date": seed_date,
                "priority": "high",
            },
            {
                "task_name": "Content Needed",
                "assignee": "Christopher Belgrave",
                "status": TaskStatus.PENDING.value,
                "source": TaskSource.NOTION.value,
                "due_date": seed_date,
                "priority": "high",
            },
        ],
        "snapshot_date": seed_date,
    }


def _apply_seed_date_defaults(seed: dict[str, Any], seed_date: str) -> dict[str, Any]:
    """Fill missing date fields from CLI date while preserving explicit values."""
    payload = copy.deepcopy(seed)

    payload.setdefault("snapshot_date", seed_date)

    for idx, standup in enumerate(payload.get("standups", [])):
        if not isinstance(standup, dict):
            continue
        standup.setdefault("date", seed_date)
        standup.setdefault("timestamp", f"{seed_date}T09:{10 + idx:02d}:00")

    for task in payload.get("tasks", []):
        if not isinstance(task, dict):
            continue
        if "due_date" not in task and task.get("status") == TaskStatus.PENDING.value:
            task["due_date"] = seed_date

    return payload


def summarize_seed(seed: dict[str, Any]) -> dict[str, int]:
    return {
        "setup_default_team": 1 if bool(seed.get("setup_default_team", True)) else 0,
        "team_members": len(seed.get("team_members", [])),
        "completed_tasks": len(seed.get("completed_tasks", [])),
        "standups": len(seed.get("standups", [])),
        "tasks": len(seed.get("tasks", [])),
        "snapshot": 1 if bool(seed.get("snapshot_date")) else 0,
    }


def apply_seed(memory: TaskMemory, seed: dict[str, Any], dry_run: bool = False) -> dict[str, int]:
    summary = summarize_seed(seed)

    if dry_run:
        return summary

    if bool(seed.get("setup_default_team", True)):
        setup_default_team(memory)

    for member in seed.get("team_members", []):
        if not isinstance(member, dict):
            continue
        memory.add_team_member(
            name=member.get("name", ""),
            channels=member.get("channels"),
            slack_user_id=member.get("slack_user_id"),
            role=member.get("role"),
        )

    for completion in seed.get("completed_tasks", []):
        if not isinstance(completion, dict):
            continue
        memory.mark_task_complete(
            task_name=completion.get("task_name", ""),
            assignee=completion.get("assignee", ""),
            task_id=completion.get("task_id"),
            confirmed_by=completion.get("confirmed_by"),
            source=completion.get("source", TaskSource.SLACK_THREAD.value),
            channel=completion.get("channel"),
            notes=completion.get("notes"),
        )

    for standup in seed.get("standups", []):
        if not isinstance(standup, dict):
            continue
        memory.record_standup(
            team_member=standup.get("team_member", ""),
            tasks=standup.get("tasks", []),
            date=standup.get("date"),
            timestamp=standup.get("timestamp"),
        )

    for task in seed.get("tasks", []):
        if not isinstance(task, dict):
            continue
        memory.add_task(
            task_name=task.get("task_name", ""),
            assignee=task.get("assignee", ""),
            task_id=task.get("task_id"),
            status=task.get("status", TaskStatus.PENDING.value),
            due_date=task.get("due_date"),
            source=task.get("source", TaskSource.MANUAL.value),
            channel=task.get("channel"),
            notion_url=task.get("notion_url"),
            priority=task.get("priority"),
            notes=task.get("notes"),
        )

    snapshot_date = seed.get("snapshot_date")
    if isinstance(snapshot_date, str) and snapshot_date:
        memory.create_daily_snapshot(snapshot_date)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize Task Memory with configurable seed data")
    parser.add_argument(
        "--memory-path",
        default="config/task_memory.json",
        help="Path to the task memory JSON file",
    )
    parser.add_argument(
        "--date",
        type=_date_arg,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Seed date (YYYY-MM-DD). Used by the default seed and missing date fields.",
    )
    parser.add_argument(
        "--from-json",
        default="",
        help="Path to a custom seed JSON payload",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without modifying task memory",
    )
    args = parser.parse_args()

    if args.from_json:
        seed = _load_seed_file(args.from_json)
        source_label = args.from_json
    else:
        seed = build_default_seed(args.date)
        source_label = "default-seed"

    seed = _apply_seed_date_defaults(seed, args.date)
    summary = summarize_seed(seed)

    print("Initializing Task Memory")
    print("-" * 50)
    print(f"Seed source: {source_label}")
    print(f"Seed date: {args.date}")
    print(f"Memory path: {args.memory_path}")
    print(f"Dry run: {'yes' if args.dry_run else 'no'}")

    print("\nPlanned operations:")
    print(f"  - setup_default_team: {summary['setup_default_team']}")
    print(f"  - team_members: {summary['team_members']}")
    print(f"  - completed_tasks: {summary['completed_tasks']}")
    print(f"  - standups: {summary['standups']}")
    print(f"  - tasks: {summary['tasks']}")
    print(f"  - snapshot: {summary['snapshot']}")

    if args.dry_run:
        print("\nDry run complete. No changes written.")
        return 0

    memory = TaskMemory(args.memory_path)
    apply_seed(memory, seed, dry_run=False)

    stats = memory.get_stats()
    print("\nInitialization complete.")
    print(f"  - total_tasks: {stats['total_tasks']}")
    print(f"  - total_completions: {stats['total_completions']}")
    print(f"  - team_members: {stats['team_members']}")
    print(f"  - standup_days: {stats['standup_days']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
