"""
DailyAggregator - Unified view of all tasks across Notion and Slack.

This module provides a single command to get comprehensive task information by:
- Combining TaskMemory data with ChannelManager lookups
- Generating daily summaries for team members
- Identifying priority actions and potential issues
- Providing quick status checks

Usage:
    from src.daily_aggregator import DailyAggregator

    aggregator = DailyAggregator()

    # Get full daily summary for a team member
    summary = aggregator.get_daily_summary("Christopher Belgrave")

    # Get quick priority tasks
    priorities = aggregator.get_priority_tasks("Italo Germando")

    # Get full team overview
    team_status = aggregator.get_team_overview()

    # Print formatted report
    print(aggregator.format_daily_report("Francisco Oliveira"))
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .task_memory import TaskMemory, TaskStatus, TaskSource
from .channel_manager import ChannelManager, ChecklistItem

logger = logging.getLogger(__name__)


class DailyAggregator:
    """
    Aggregates task information from multiple sources into unified views.

    Combines:
    - TaskMemory: Task states, completions, standups
    - ChannelManager: Channel priorities, patterns
    """

    def __init__(
        self,
        task_memory: Optional[TaskMemory] = None,
        channel_manager: Optional[ChannelManager] = None
    ):
        """
        Initialize DailyAggregator.

        Args:
            task_memory: TaskMemory instance (creates new if not provided)
            channel_manager: ChannelManager instance (creates new if not provided)
        """
        self.memory = task_memory or TaskMemory()
        self.channels = channel_manager or ChannelManager()

    # ==================== Daily Summaries ====================

    def get_daily_summary(
        self,
        name: str,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive daily summary for a team member.

        Args:
            name: Team member name
            date: Date in YYYY-MM-DD format (defaults to today)

        Returns:
            Dictionary with all relevant task information
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # Get task data from memory
        task_data = self.memory.get_team_member_tasks(name, date, include_completed=True)

        # Get channel data
        channel_checklist = self.channels.generate_daily_checklist(name)
        priority_channels = self.channels.get_priority_channels(name, "high")

        # Get standup
        standup = self.memory.get_standup(name, date)

        # Categorize tasks
        pending_tasks = []
        in_progress_tasks = []
        completed_tasks = []

        for task in self.memory.get_tasks_by_assignee(name):
            if task.status == TaskStatus.COMPLETE.value:
                completed_tasks.append(task)
            elif task.status == TaskStatus.IN_PROGRESS.value:
                in_progress_tasks.append(task)
            else:
                pending_tasks.append(task)

        # Build summary
        summary = {
            "team_member": name,
            "date": date,
            "generated_at": datetime.now().isoformat(),

            # Task counts
            "task_counts": {
                "total": len(pending_tasks) + len(in_progress_tasks) + len(completed_tasks),
                "pending": len(pending_tasks),
                "in_progress": len(in_progress_tasks),
                "completed": len(completed_tasks)
            },

            # Tasks by status
            "pending_tasks": [
                {
                    "name": t.task_name,
                    "source": t.source,
                    "priority": t.priority,
                    "due_date": t.due_date
                }
                for t in pending_tasks
            ],
            "in_progress_tasks": [
                {
                    "name": t.task_name,
                    "source": t.source,
                    "priority": t.priority,
                    "notes": t.notes
                }
                for t in in_progress_tasks
            ],
            "completed_tasks": [
                {
                    "name": t.task_name,
                    "confirmed_by": t.confirmed_by,
                    "source": t.source
                }
                for t in completed_tasks
            ],

            # Standup info
            "standup": {
                "posted": standup is not None,
                "tasks": standup.tasks if standup else [],
                "timestamp": standup.timestamp if standup else None
            },

            # Channels to check
            "channels_to_check": [
                {
                    "channel": ch.channel,
                    "priority": ch.priority,
                    "reason": ch.reason,
                    "client": ch.client
                }
                for ch in channel_checklist
            ],

            # High priority channels
            "high_priority_channels": [ch.channel for ch in priority_channels],

            # Discrepancies
            "discrepancies": task_data.get("discrepancies", [])
        }

        return summary

    def get_priority_tasks(
        self,
        name: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get top priority tasks for a team member.

        Prioritizes:
        1. In-progress tasks
        2. High priority pending tasks
        3. Tasks due today
        4. Standup-mentioned tasks

        Args:
            name: Team member name
            limit: Maximum number of tasks to return

        Returns:
            List of priority task dictionaries
        """
        today = datetime.now().strftime("%Y-%m-%d")
        priority_tasks = []
        seen_ids = set()

        # 1. In-progress tasks first
        for task in self.memory.get_tasks_by_assignee(name, status=TaskStatus.IN_PROGRESS.value):
            if task.task_id not in seen_ids:
                priority_tasks.append({
                    "name": task.task_name,
                    "status": "in_progress",
                    "reason": "Currently working on",
                    "priority": task.priority or "medium"
                })
                seen_ids.add(task.task_id)

        # 2. High priority tasks
        for task in self.memory.get_tasks_by_assignee(name):
            if task.task_id not in seen_ids and task.priority == "high":
                if task.status != TaskStatus.COMPLETE.value:
                    priority_tasks.append({
                        "name": task.task_name,
                        "status": task.status,
                        "reason": "High priority",
                        "priority": "high"
                    })
                    seen_ids.add(task.task_id)

        # 3. Tasks due today
        for task in self.memory.get_tasks_by_assignee(name, date=today):
            if task.task_id not in seen_ids:
                if task.status != TaskStatus.COMPLETE.value:
                    priority_tasks.append({
                        "name": task.task_name,
                        "status": task.status,
                        "reason": "Due today",
                        "priority": task.priority or "medium"
                    })
                    seen_ids.add(task.task_id)

        return priority_tasks[:limit]

    # ==================== Team Overview ====================

    def get_team_overview(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get overview of all team members' status.

        Args:
            date: Date in YYYY-MM-DD format (defaults to today)

        Returns:
            Dictionary with team-wide information
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        team_members = self.channels.get_team_members()
        overview = {
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "team_members": {},
            "totals": {
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "standups_posted": 0
            }
        }

        for name in team_members:
            summary = self.get_daily_summary(name, date)
            overview["team_members"][name] = {
                "task_counts": summary["task_counts"],
                "standup_posted": summary["standup"]["posted"],
                "top_priorities": self.get_priority_tasks(name, limit=3)
            }

            # Update totals
            overview["totals"]["pending"] += summary["task_counts"]["pending"]
            overview["totals"]["in_progress"] += summary["task_counts"]["in_progress"]
            overview["totals"]["completed"] += summary["task_counts"]["completed"]
            if summary["standup"]["posted"]:
                overview["totals"]["standups_posted"] += 1

        return overview

    # ==================== Formatted Reports ====================

    def format_daily_report(self, name: str, date: Optional[str] = None) -> str:
        """
        Generate a formatted daily report for a team member.

        Args:
            name: Team member name
            date: Date (defaults to today)

        Returns:
            Formatted string report
        """
        summary = self.get_daily_summary(name, date)
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append(f"📋 Daily Task Report: {name}")
        lines.append(f"📅 Date: {summary['date']}")
        lines.append("=" * 60)

        # Task counts
        counts = summary["task_counts"]
        lines.append("")
        lines.append("📊 Task Summary:")
        lines.append(f"   • Pending: {counts['pending']}")
        lines.append(f"   • In Progress: {counts['in_progress']}")
        lines.append(f"   • Completed: {counts['completed']}")

        # Standup status
        lines.append("")
        if summary["standup"]["posted"]:
            lines.append("✅ Standup Posted:")
            for task in summary["standup"]["tasks"]:
                lines.append(f"   • {task}")
        else:
            lines.append("⏳ Standup: Not posted yet")

        # In-progress tasks
        if summary["in_progress_tasks"]:
            lines.append("")
            lines.append("🔄 In Progress:")
            for task in summary["in_progress_tasks"]:
                priority = f" [{task['priority']}]" if task.get('priority') else ""
                lines.append(f"   • {task['name']}{priority}")

        # Pending tasks
        if summary["pending_tasks"]:
            lines.append("")
            lines.append("📌 Pending Tasks:")
            for task in summary["pending_tasks"][:10]:  # Limit to 10
                priority = f" [{task['priority']}]" if task.get('priority') else ""
                source = f" ({task['source']})" if task.get('source') else ""
                lines.append(f"   • {task['name']}{priority}{source}")
            if len(summary["pending_tasks"]) > 10:
                lines.append(f"   ... and {len(summary['pending_tasks']) - 10} more")

        # Completed tasks
        if summary["completed_tasks"]:
            lines.append("")
            lines.append("✅ Completed:")
            for task in summary["completed_tasks"]:
                confirmed = f" (confirmed by {task['confirmed_by']})" if task.get('confirmed_by') else ""
                lines.append(f"   ✓ {task['name']}{confirmed}")

        # Channels to check
        lines.append("")
        lines.append("📺 Channels to Check:")
        high_priority = [ch for ch in summary["channels_to_check"] if ch["priority"] == "high"]
        for ch in high_priority[:5]:
            client = f" - {ch['client']}" if ch.get('client') else ""
            lines.append(f"   🔴 {ch['channel']}{client}")

        # Discrepancies
        if summary["discrepancies"]:
            lines.append("")
            lines.append("⚠️ Discrepancies Found:")
            for disc in summary["discrepancies"][:3]:
                lines.append(f"   • {disc.get('description', 'Unknown')}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def format_team_overview(self, date: Optional[str] = None) -> str:
        """
        Generate a formatted team overview report.

        Args:
            date: Date (defaults to today)

        Returns:
            Formatted string report
        """
        overview = self.get_team_overview(date)
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("📊 Team Daily Overview")
        lines.append(f"📅 Date: {overview['date']}")
        lines.append("=" * 60)

        # Totals
        totals = overview["totals"]
        lines.append("")
        lines.append("📈 Team Totals:")
        lines.append(f"   • Pending tasks: {totals['pending']}")
        lines.append(f"   • In progress: {totals['in_progress']}")
        lines.append(f"   • Completed: {totals['completed']}")
        lines.append(f"   • Standups posted: {totals['standups_posted']}/{len(overview['team_members'])}")

        # Per-member summary
        lines.append("")
        lines.append("-" * 60)

        for name, data in overview["team_members"].items():
            lines.append("")
            standup_icon = "✅" if data["standup_posted"] else "⏳"
            lines.append(f"👤 {name} {standup_icon}")

            counts = data["task_counts"]
            lines.append(f"   Tasks: {counts['pending']} pending | {counts['in_progress']} active | {counts['completed']} done")

            if data["top_priorities"]:
                lines.append("   Top priorities:")
                for task in data["top_priorities"]:
                    lines.append(f"      • {task['name']} ({task['reason']})")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    # ==================== Quick Actions ====================

    def what_should_i_check(self, name: str) -> List[str]:
        """
        Get quick list of what a team member should check.

        Returns prioritized list of actions.
        """
        actions = []
        summary = self.get_daily_summary(name)

        # Check standup
        if not summary["standup"]["posted"]:
            actions.append("📝 Post your standup in #standup")

        # High priority channels
        for ch in summary["high_priority_channels"][:3]:
            actions.append(f"📺 Check {ch} for updates")

        # In-progress tasks
        for task in summary["in_progress_tasks"][:2]:
            actions.append(f"🔄 Continue: {task['name']}")

        # Pending high priority
        high_priority = [t for t in summary["pending_tasks"] if t.get("priority") == "high"]
        for task in high_priority[:2]:
            actions.append(f"⚡ Start: {task['name']}")

        return actions

    def get_completion_summary(self, name: str) -> Dict[str, Any]:
        """
        Get summary focused on completions and confirmations.

        Useful for end-of-day review.
        """
        summary = self.get_daily_summary(name)
        completed = summary["completed_tasks"]

        return {
            "team_member": name,
            "completed_count": len(completed),
            "completed_tasks": completed,
            "pending_for_tomorrow": [
                t for t in summary["pending_tasks"]
                if t.get("status") != TaskStatus.COMPLETE.value
            ],
            "in_progress_carryover": summary["in_progress_tasks"]
        }


# ==================== Convenience Functions ====================

def get_aggregator() -> DailyAggregator:
    """Get or create a DailyAggregator instance."""
    return DailyAggregator()


def quick_status(name: str) -> str:
    """Get quick status for a team member."""
    aggregator = DailyAggregator()
    return aggregator.format_daily_report(name)


def team_status() -> str:
    """Get quick team status."""
    aggregator = DailyAggregator()
    return aggregator.format_team_overview()
