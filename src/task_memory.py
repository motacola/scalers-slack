"""
TaskMemory - Persistent memory system for tracking task states across Notion and Slack.

This module provides intelligent task tracking that remembers:
- Task completion confirmations from Slack threads
- User confirmations from conversations
- Team member assignments and their relevant channels
- Discrepancies between Notion tasks and Slack standups
- Daily task snapshots for quick retrieval

Usage:
    from src.task_memory import TaskMemory

    memory = TaskMemory()

    # Mark a task as complete
    memory.mark_task_complete(
        task_id="captain_clean_location_pages",
        task_name="Captain Clean Location Pages",
        assignee="Italo Germando",
        confirmed_by="Emily A",
        source="slack_thread",
        channel="ss-captain-clean-website-edits"
    )

    # Get tasks for a team member
    tasks = memory.get_team_member_tasks("Italo Germando", date="2026-02-06")

    # Check if task is already done
    if memory.is_task_complete("captain_clean_location_pages"):
        print("Task already completed!")
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskSource(Enum):
    """Source of task information."""
    NOTION = "notion"
    SLACK_STANDUP = "slack_standup"
    SLACK_THREAD = "slack_thread"
    USER_CONFIRMATION = "user_confirmation"
    MANUAL = "manual"


@dataclass
class TaskRecord:
    """Represents a task record with all relevant metadata."""
    task_id: str
    task_name: str
    assignee: str
    status: str
    due_date: Optional[str] = None
    confirmed_by: Optional[str] = None
    confirmed_date: Optional[str] = None
    source: str = "manual"
    channel: Optional[str] = None
    notion_url: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRecord":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TeamMember:
    """Represents a team member with their channel mappings."""
    name: str
    slack_user_id: Optional[str] = None
    channels: Optional[List[str]] = None
    role: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamMember":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StandupEntry:
    """Represents a standup entry from Slack."""
    team_member: str
    date: str
    tasks: List[str]
    timestamp: str
    channel: str = "standup"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandupEntry":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class TaskMemory:
    """
    Persistent memory system for tracking task states across Notion and Slack.

    This class maintains a JSON-based persistent store of:
    - Completed tasks with confirmation metadata
    - Team member configurations and channel mappings
    - Daily standup entries
    - Task discrepancies between systems
    - Daily snapshots for quick retrieval
    """

    DEFAULT_MEMORY_PATH = "config/task_memory.json"

    def __init__(self, memory_path: Optional[str] = None):
        """
        Initialize TaskMemory.

        Args:
            memory_path: Path to the JSON memory file. Defaults to config/task_memory.json
        """
        self.memory_path = memory_path or self.DEFAULT_MEMORY_PATH
        self.data: Dict[str, Any] = self._get_default_data()
        self.load()

    def _get_default_data(self) -> Dict[str, Any]:
        """Return default data structure."""
        return {
            "version": "1.0.0",
            "tasks": {},  # task_id -> TaskRecord
            "team_members": {},  # name -> TeamMember
            "standups": {},  # date -> {team_member -> StandupEntry}
            "daily_snapshots": {},  # date -> snapshot data
            "discrepancies": [],  # List of detected discrepancies
            "confirmations": [],  # User confirmations from chat
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "total_tasks_tracked": 0,
                "total_completions": 0
            }
        }

    # ==================== Persistence Methods ====================

    def load(self) -> None:
        """Load memory from disk."""
        if not os.path.exists(self.memory_path):
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            self.save()
            logger.info(f"Created new task memory file at {self.memory_path}")
            return

        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                # Merge with defaults to handle schema updates
                self.data = {**self._get_default_data(), **loaded_data}
            logger.info(f"Loaded task memory from {self.memory_path}")
        except Exception as e:
            logger.warning(f"Failed to load task memory: {e}. Starting fresh.")
            self.data = self._get_default_data()

    def save(self) -> None:
        """Save memory to disk."""
        try:
            self.data["metadata"]["updated_at"] = datetime.now().isoformat()
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, default=str)
            logger.debug(f"Saved task memory to {self.memory_path}")
        except Exception as e:
            logger.error(f"Failed to save task memory: {e}")

    # ==================== Task Management ====================

    def _generate_task_id(self, task_name: str, assignee: str) -> str:
        """Generate a unique task ID from name and assignee."""
        clean_name = task_name.lower().replace(" ", "_").replace("-", "_")
        clean_name = "".join(c for c in clean_name if c.isalnum() or c == "_")
        clean_assignee = assignee.lower().split()[0] if assignee else "unknown"
        return f"{clean_name}_{clean_assignee}"

    def add_task(
        self,
        task_name: str,
        assignee: str,
        task_id: Optional[str] = None,
        status: str = TaskStatus.PENDING.value,
        due_date: Optional[str] = None,
        source: str = TaskSource.MANUAL.value,
        channel: Optional[str] = None,
        notion_url: Optional[str] = None,
        priority: Optional[str] = None,
        notes: Optional[str] = None
    ) -> TaskRecord:
        """
        Add or update a task in memory.

        Args:
            task_name: Name of the task
            assignee: Person assigned to the task
            task_id: Optional custom task ID (auto-generated if not provided)
            status: Task status (pending, in_progress, complete, blocked)
            due_date: Due date in YYYY-MM-DD format
            source: Source of the task (notion, slack_standup, etc.)
            channel: Slack channel associated with the task
            notion_url: URL to Notion task
            priority: Task priority (high, medium, low, urgent)
            notes: Additional notes

        Returns:
            TaskRecord of the added/updated task
        """
        if not task_id:
            task_id = self._generate_task_id(task_name, assignee)

        now = datetime.now().isoformat()
        existing = self.data["tasks"].get(task_id)

        task = TaskRecord(
            task_id=task_id,
            task_name=task_name,
            assignee=assignee,
            status=status,
            due_date=due_date,
            source=source,
            channel=channel,
            notion_url=notion_url,
            priority=priority,
            notes=notes,
            created_at=existing.get("created_at", now) if existing else now,
            updated_at=now
        )

        self.data["tasks"][task_id] = task.to_dict()
        self.data["metadata"]["total_tasks_tracked"] += 1 if not existing else 0
        self.save()

        logger.info(f"Added/updated task: {task_id} for {assignee}")
        return task

    def mark_task_complete(
        self,
        task_name: str,
        assignee: str,
        task_id: Optional[str] = None,
        confirmed_by: Optional[str] = None,
        source: str = TaskSource.SLACK_THREAD.value,
        channel: Optional[str] = None,
        notes: Optional[str] = None
    ) -> TaskRecord:
        """
        Mark a task as complete with confirmation metadata.

        Args:
            task_name: Name of the task
            assignee: Person who completed the task
            task_id: Optional task ID (auto-generated if not provided)
            confirmed_by: Person who confirmed completion (e.g., "Emily A")
            source: Source of confirmation (slack_thread, user_confirmation, etc.)
            channel: Channel where confirmation occurred
            notes: Additional notes about completion

        Returns:
            TaskRecord of the completed task
        """
        if not task_id:
            task_id = self._generate_task_id(task_name, assignee)

        now = datetime.now().isoformat()
        existing = self.data["tasks"].get(task_id, {})
        was_complete = existing.get("status") == TaskStatus.COMPLETE.value if existing else False

        task = TaskRecord(
            task_id=task_id,
            task_name=task_name,
            assignee=assignee,
            status=TaskStatus.COMPLETE.value,
            due_date=existing.get("due_date"),
            confirmed_by=confirmed_by,
            confirmed_date=now,
            source=source,
            channel=channel,
            notion_url=existing.get("notion_url"),
            priority=existing.get("priority"),
            notes=notes,
            created_at=existing.get("created_at", now),
            updated_at=now
        )

        self.data["tasks"][task_id] = task.to_dict()
        if not existing:
            self.data["metadata"]["total_tasks_tracked"] += 1
        if not was_complete:
            self.data["metadata"]["total_completions"] += 1
        self.save()

        logger.info(f"Marked task complete: {task_id} (confirmed by {confirmed_by})")
        return task

    def is_task_complete(self, task_id: str = None, task_name: str = None, assignee: str = None) -> bool:
        """
        Check if a task is marked as complete.

        Args:
            task_id: Task ID to check
            task_name: Task name (used with assignee to generate ID if task_id not provided)
            assignee: Assignee name

        Returns:
            True if task is complete, False otherwise
        """
        if not task_id and task_name and assignee:
            task_id = self._generate_task_id(task_name, assignee)

        if not task_id:
            return False

        task = self.data["tasks"].get(task_id)
        return task is not None and task.get("status") == TaskStatus.COMPLETE.value

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Get a task by ID."""
        task_data = self.data["tasks"].get(task_id)
        if task_data:
            return TaskRecord.from_dict(task_data)
        return None

    def get_tasks_by_assignee(
        self,
        assignee: str,
        status: Optional[str] = None,
        date: Optional[str] = None
    ) -> List[TaskRecord]:
        """
        Get all tasks for a specific assignee.

        Args:
            assignee: Name of the assignee
            status: Optional status filter
            date: Optional due date filter (YYYY-MM-DD)

        Returns:
            List of TaskRecord objects
        """
        tasks = []
        for task_data in self.data["tasks"].values():
            if task_data["assignee"].lower() == assignee.lower():
                if status and task_data["status"] != status:
                    continue
                if date and task_data.get("due_date") != date:
                    continue
                tasks.append(TaskRecord.from_dict(task_data))
        return tasks

    def get_incomplete_tasks(self, assignee: Optional[str] = None) -> List[TaskRecord]:
        """Get all incomplete tasks, optionally filtered by assignee."""
        tasks = []
        for task_data in self.data["tasks"].values():
            if task_data["status"] != TaskStatus.COMPLETE.value:
                if assignee and task_data["assignee"].lower() != assignee.lower():
                    continue
                tasks.append(TaskRecord.from_dict(task_data))
        return tasks

    # ==================== Team Member Management ====================

    def add_team_member(
        self,
        name: str,
        channels: Optional[List[str]] = None,
        slack_user_id: Optional[str] = None,
        role: Optional[str] = None
    ) -> TeamMember:
        """
        Add or update a team member with their channel mappings.

        Args:
            name: Team member name
            channels: List of Slack channels relevant to this member
            slack_user_id: Slack user ID
            role: Role/title

        Returns:
            TeamMember object
        """
        member = TeamMember(
            name=name,
            slack_user_id=slack_user_id,
            channels=channels or [],
            role=role
        )

        self.data["team_members"][name] = member.to_dict()
        self.save()

        logger.info(f"Added/updated team member: {name}")
        return member

    def get_team_member(self, name: str) -> Optional[TeamMember]:
        """Get a team member by name."""
        member_data = self.data["team_members"].get(name)
        if member_data:
            return TeamMember.from_dict(member_data)
        return None

    def get_channels_for_member(self, name: str) -> List[str]:
        """Get the list of relevant channels for a team member."""
        member = self.get_team_member(name)
        return member.channels if member and member.channels else []

    def get_all_team_members(self) -> List[TeamMember]:
        """Get all team members."""
        return [TeamMember.from_dict(m) for m in self.data["team_members"].values()]

    # ==================== Standup Management ====================

    def record_standup(
        self,
        team_member: str,
        tasks: List[str],
        date: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> StandupEntry:
        """
        Record a standup entry for a team member.

        Args:
            team_member: Name of the team member
            tasks: List of tasks mentioned in standup
            date: Date of standup (defaults to today)
            timestamp: Slack message timestamp

        Returns:
            StandupEntry object
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        entry = StandupEntry(
            team_member=team_member,
            date=date,
            tasks=tasks,
            timestamp=timestamp or datetime.now().isoformat(),
            channel="standup"
        )

        if date not in self.data["standups"]:
            self.data["standups"][date] = {}

        self.data["standups"][date][team_member] = entry.to_dict()
        self.save()

        logger.info(f"Recorded standup for {team_member} on {date}")
        return entry

    def get_standup(self, team_member: str, date: Optional[str] = None) -> Optional[StandupEntry]:
        """Get standup entry for a team member on a specific date."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        day_standups = self.data["standups"].get(date, {})
        entry_data = day_standups.get(team_member)

        if entry_data:
            return StandupEntry.from_dict(entry_data)
        return None

    def get_all_standups_for_date(self, date: Optional[str] = None) -> Dict[str, StandupEntry]:
        """Get all standups for a specific date."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        day_standups = self.data["standups"].get(date, {})
        return {name: StandupEntry.from_dict(data) for name, data in day_standups.items()}

    # ==================== Discrepancy Detection ====================

    def detect_discrepancies(
        self,
        notion_tasks: List[Dict[str, Any]],
        standup_tasks: List[str],
        team_member: str,
        date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect discrepancies between Notion tasks and standup tasks.

        Args:
            notion_tasks: List of tasks from Notion (with task_name, due_date, status)
            standup_tasks: List of task names from standup
            team_member: Team member name
            date: Date to check (defaults to today)

        Returns:
            List of discrepancy records
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        discrepancies = []

        # Normalize task names for comparison
        def normalize(name: str) -> str:
            return name.lower().strip().replace("-", " ").replace("_", " ")

        notion_names = {normalize(t.get("task_name", "")): t for t in notion_tasks}
        standup_names = {normalize(t): t for t in standup_tasks}

        # Tasks in Notion but not in standup
        for norm_name, task in notion_names.items():
            if norm_name and norm_name not in standup_names:
                discrepancies.append({
                    "type": "notion_not_in_standup",
                    "team_member": team_member,
                    "date": date,
                    "task_name": task.get("task_name"),
                    "notion_due_date": task.get("due_date"),
                    "description": f"Task '{task.get('task_name')}' is in Notion (due {task.get('due_date')}) but not mentioned in standup",
                    "detected_at": datetime.now().isoformat()
                })

        # Tasks in standup but not in Notion
        for norm_name, task_name in standup_names.items():
            if norm_name and norm_name not in notion_names:
                discrepancies.append({
                    "type": "standup_not_in_notion",
                    "team_member": team_member,
                    "date": date,
                    "task_name": task_name,
                    "description": f"Task '{task_name}' mentioned in standup but not found in Notion for this date",
                    "detected_at": datetime.now().isoformat()
                })

        # Store discrepancies
        if discrepancies:
            self.data["discrepancies"].extend(discrepancies)
            # Keep only last 100 discrepancies
            self.data["discrepancies"] = self.data["discrepancies"][-100:]
            self.save()

        return discrepancies

    def get_recent_discrepancies(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent discrepancies."""
        return self.data["discrepancies"][-limit:]

    # ==================== User Confirmations ====================

    def record_user_confirmation(
        self,
        message: str,
        task_name: Optional[str] = None,
        assignee: Optional[str] = None,
        action: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record a user confirmation from chat.

        Args:
            message: The user's message (e.g., "Unified is done")
            task_name: Extracted task name
            assignee: Extracted assignee
            action: Action type (e.g., "mark_complete", "update_status")

        Returns:
            Confirmation record
        """
        confirmation = {
            "message": message,
            "task_name": task_name,
            "assignee": assignee,
            "action": action,
            "timestamp": datetime.now().isoformat()
        }

        self.data["confirmations"].append(confirmation)
        # Keep only last 50 confirmations
        self.data["confirmations"] = self.data["confirmations"][-50:]
        self.save()

        logger.info(f"Recorded user confirmation: {message}")

        # If we have enough info, mark the task complete
        if task_name and action == "mark_complete":
            self.mark_task_complete(
                task_name=task_name,
                assignee=assignee or "Unknown",
                source=TaskSource.USER_CONFIRMATION.value,
                notes=f"User said: {message}"
            )

        return confirmation

    # ==================== Daily Snapshots ====================

    def create_daily_snapshot(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a snapshot of all tasks for a specific date.

        Args:
            date: Date for snapshot (defaults to today)

        Returns:
            Snapshot data
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        snapshot = {
            "date": date,
            "created_at": datetime.now().isoformat(),
            "tasks_by_assignee": {},
            "standups": self.data["standups"].get(date, {}),
            "completed_today": [],
            "summary": {}
        }

        # Group tasks by assignee
        for task_data in self.data["tasks"].values():
            assignee = task_data["assignee"]
            if assignee not in snapshot["tasks_by_assignee"]:
                snapshot["tasks_by_assignee"][assignee] = []

            # Include if due today or completed today
            if task_data.get("due_date") == date:
                snapshot["tasks_by_assignee"][assignee].append(task_data)

            if (task_data.get("status") == TaskStatus.COMPLETE.value and
                task_data.get("confirmed_date", "").startswith(date)):
                snapshot["completed_today"].append(task_data)

        # Summary stats
        snapshot["summary"] = {
            "total_tasks_due": sum(len(tasks) for tasks in snapshot["tasks_by_assignee"].values()),
            "total_completed": len(snapshot["completed_today"]),
            "team_members_with_tasks": list(snapshot["tasks_by_assignee"].keys()),
            "standups_recorded": len(snapshot["standups"])
        }

        self.data["daily_snapshots"][date] = snapshot
        # Keep only last 30 days of snapshots
        dates = sorted(self.data["daily_snapshots"].keys())
        if len(dates) > 30:
            for old_date in dates[:-30]:
                del self.data["daily_snapshots"][old_date]

        self.save()
        logger.info(f"Created daily snapshot for {date}")

        return snapshot

    def get_daily_snapshot(self, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get daily snapshot for a specific date."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        return self.data["daily_snapshots"].get(date)

    # ==================== Utility Methods ====================

    def get_team_member_tasks(
        self,
        name: str,
        date: Optional[str] = None,
        include_completed: bool = False
    ) -> Dict[str, Any]:
        """
        Get comprehensive task information for a team member.

        Args:
            name: Team member name
            date: Date to filter by (defaults to today)
            include_completed: Whether to include completed tasks

        Returns:
            Dictionary with tasks from various sources
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        result = {
            "team_member": name,
            "date": date,
            "notion_tasks": [],
            "standup_tasks": [],
            "completed_tasks": [],
            "channels": self.get_channels_for_member(name),
            "discrepancies": []
        }

        # Get tasks from memory
        for task_data in self.data["tasks"].values():
            if task_data["assignee"].lower() == name.lower():
                if task_data.get("due_date") == date or not task_data.get("due_date"):
                    if task_data["status"] == TaskStatus.COMPLETE.value:
                        if include_completed:
                            result["completed_tasks"].append(task_data)
                    else:
                        if task_data.get("source") == TaskSource.NOTION.value:
                            result["notion_tasks"].append(task_data)

        # Get standup tasks
        standup = self.get_standup(name, date)
        if standup:
            result["standup_tasks"] = standup.tasks

        # Get relevant discrepancies
        for disc in self.data["discrepancies"]:
            if disc.get("team_member", "").lower() == name.lower() and disc.get("date") == date:
                result["discrepancies"].append(disc)

        return result

    def clear_old_data(self, days_to_keep: int = 30) -> int:
        """
        Clear data older than specified days.

        Args:
            days_to_keep: Number of days of data to retain

        Returns:
            Number of records cleared
        """
        cutoff = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")
        cleared = 0

        # Clear old standups
        dates_to_remove = [d for d in self.data["standups"].keys() if d < cutoff]
        for date in dates_to_remove:
            del self.data["standups"][date]
            cleared += 1

        # Clear old snapshots
        dates_to_remove = [d for d in self.data["daily_snapshots"].keys() if d < cutoff]
        for date in dates_to_remove:
            del self.data["daily_snapshots"][date]
            cleared += 1

        # Clear old discrepancies
        self.data["discrepancies"] = [
            d for d in self.data["discrepancies"]
            if d.get("date", "") >= cutoff
        ]

        if cleared > 0:
            self.save()
            logger.info(f"Cleared {cleared} old records")

        return cleared

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "total_tasks": len(self.data["tasks"]),
            "total_completions": self.data["metadata"]["total_completions"],
            "team_members": len(self.data["team_members"]),
            "standup_days": len(self.data["standups"]),
            "discrepancies": len(self.data["discrepancies"]),
            "snapshots": len(self.data["daily_snapshots"]),
            "last_updated": self.data["metadata"]["updated_at"]
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of the task memory."""
        completed_count = sum(
            1 for t in self.data["tasks"].values()
            if t.get("status") == TaskStatus.COMPLETE.value
        )

        # Count standups recorded today
        today = datetime.now().strftime("%Y-%m-%d")
        today_standups = self.data["standups"].get(today, {})

        return {
            "total_tasks": len(self.data["tasks"]),
            "completed_tasks": completed_count,
            "pending_tasks": len(self.data["tasks"]) - completed_count,
            "team_members": len(self.data["team_members"]),
            "standups_recorded": len(today_standups),
            "total_completions": self.data["metadata"]["total_completions"],
            "discrepancies": len(self.data["discrepancies"]),
            "last_updated": self.data["metadata"]["updated_at"]
        }


# ==================== Convenience Functions ====================

def get_task_memory(memory_path: Optional[str] = None) -> TaskMemory:
    """Get or create a TaskMemory instance."""
    return TaskMemory(memory_path)


# Pre-configure team members (can be customized)
def setup_default_team(memory: TaskMemory) -> None:
    """Set up default team member configurations."""

    memory.add_team_member(
        name="Italo Germando",
        channels=[
            "ss-captain-clean-website-edits",
            "ss-eds-pumps-website-management",
            "ss-awful-nice-guys-website-management",
            "ss-aaa-electrical-website-management",
            "standup"
        ],
        role="Web Developer"
    )

    memory.add_team_member(
        name="Francisco Oliveira",
        channels=[
            "ss-ark-home-website-management",
            "ss-calgary-website-management",
            "ss-spence-and-daves-website-management",
            "ss-parker-and-co-website-management",
            "standup"
        ],
        role="Web Developer"
    )

    memory.add_team_member(
        name="Christopher Belgrave",
        channels=[
            "ss-eds-pumps-website-management",
            "ss-lake-county-mechanical-website-hosting",
            "ss-trips-website-management",
            "ss-performance-of-maine-website-management",
            "standup"
        ],
        role="Web Developer"
    )

    logger.info("Set up default team members")
