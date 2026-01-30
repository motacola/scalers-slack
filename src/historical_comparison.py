"""Historical comparison utilities for tracking task changes over time."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.task_processor import Task


@dataclass
class DailySnapshot:
    """Snapshot of tasks for a specific day."""

    date: str
    total_tasks: int
    actionable_tasks: int
    high_priority_tasks: int
    tasks: list[dict[str, Any]]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TaskChanges:
    """Changes between two snapshots."""

    new_tasks: list[Task]
    completed_tasks: list[Task]
    updated_tasks: list[tuple[Task, Task]]  # (old, new)
    unchanged_tasks: list[Task]


def load_snapshot(snapshot_path: str) -> DailySnapshot | None:
    """Load a daily snapshot from file."""
    path = Path(snapshot_path)
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return DailySnapshot(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def save_snapshot(tasks: list[Task], output_path: str, date: str | None = None) -> None:
    """Save a daily snapshot to file."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    snapshot = DailySnapshot(
        date=date,
        total_tasks=len(tasks),
        actionable_tasks=sum(1 for t in tasks if t.is_actionable),
        high_priority_tasks=sum(1 for t in tasks if t.priority == "High"),
        tasks=[asdict(t) for t in tasks],
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(snapshot), f, indent=2, default=str)


def get_snapshot_path(base_dir: str, date: str) -> str:
    """Get the path for a snapshot file."""
    return str(Path(base_dir) / f"snapshot_{date}.json")


def compare_tasks(current: list[Task], previous: list[Task]) -> TaskChanges:
    """Compare current tasks with previous snapshot to identify changes."""
    current_dict = {task_key(t): t for t in current}
    previous_dict = {task_key(t): t for t in previous}

    new_tasks: list[Task] = []
    completed_tasks: list[Task] = []
    updated_tasks: list[tuple[Task, Task]] = []
    unchanged_tasks: list[Task] = []

    # Find new tasks
    for key, task in current_dict.items():
        if key not in previous_dict:
            new_tasks.append(task)
        else:
            old_task = previous_dict[key]
            if tasks_equal(task, old_task):
                unchanged_tasks.append(task)
            else:
                updated_tasks.append((old_task, task))

    # Find completed tasks (in previous but not in current)
    for key, task in previous_dict.items():
        if key not in current_dict:
            completed_tasks.append(task)

    return TaskChanges(
        new_tasks=new_tasks,
        completed_tasks=completed_tasks,
        updated_tasks=updated_tasks,
        unchanged_tasks=unchanged_tasks,
    )


def task_key(task: Task) -> str:
    """Generate a unique key for a task."""
    # Use text + channel + owner as unique identifier
    return f"{task.channel}:{task.owner}:{task.text[:100]}"


def tasks_equal(a: Task, b: Task) -> bool:
    """Check if two tasks are equal (ignoring timestamp)."""
    return (
        a.text == b.text
        and a.channel == b.channel
        and a.owner == b.owner
        and a.status == b.status
        and a.priority == b.priority
        and a.due_date == b.due_date
    )


def generate_comparison_report(
    changes: TaskChanges,
    current_date: str,
    previous_date: str,
) -> str:
    """Generate a markdown comparison report."""
    lines = [
        f"# Task Comparison: {previous_date} → {current_date}",
        "",
        "## Summary",
        "",
        f"- **New Tasks:** {len(changes.new_tasks)}",
        f"- **Completed Tasks:** {len(changes.completed_tasks)}",
        f"- **Updated Tasks:** {len(changes.updated_tasks)}",
        f"- **Unchanged Tasks:** {len(changes.unchanged_tasks)}",
        "",
    ]

    if changes.new_tasks:
        lines.extend([
            "## 🆕 New Tasks",
            "",
        ])
        for task in changes.new_tasks:
            lines.extend([
                f"### {task.owner or 'Unknown'}",
                f"- {task.text}",
                f"  - **Client:** {task.client}",
                f"  - **Priority:** {task.priority}",
                f"  - **Channel:** {task.channel}",
                "",
            ])

    if changes.completed_tasks:
        lines.extend([
            "## ✅ Completed Tasks",
            "",
        ])
        for task in changes.completed_tasks:
            lines.extend([
                f"- ~~{task.text}~~ (was: {task.owner})",
                "",
            ])

    if changes.updated_tasks:
        lines.extend([
            "## 📝 Updated Tasks",
            "",
        ])
        for old, new in changes.updated_tasks:
            lines.append(f"### {new.owner or 'Unknown'}")
            lines.append(f"- {new.text}")

            if old.priority != new.priority:
                lines.append(f"  - **Priority:** {old.priority} → {new.priority}")
            if old.status != new.status:
                lines.append(f"  - **Status:** {old.status} → {new.status}")
            if old.due_date != new.due_date:
                lines.append(f"  - **Due Date:** {old.due_date} → {new.due_date}")

            lines.append("")

    return "\n".join(lines)


def get_previous_working_day(date_str: str) -> str:
    """Get the previous working day (skipping weekends)."""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    previous = date - timedelta(days=1)

    # Skip weekends
    while previous.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        previous -= timedelta(days=1)

    return previous.strftime("%Y-%m-%d")


class HistoricalTracker:
    """Track task history and generate comparisons."""

    def __init__(self, snapshots_dir: str = "output/snapshots"):
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def save(self, tasks: list[Task], date: str | None = None) -> str:
        """Save a snapshot and return the path."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        snapshot_path = self.snapshots_dir / f"snapshot_{date}.json"
        save_snapshot(tasks, str(snapshot_path), date)
        return str(snapshot_path)

    def load(self, date: str) -> list[Task] | None:
        """Load tasks from a snapshot."""
        snapshot_path = self.snapshots_dir / f"snapshot_{date}.json"
        snapshot = load_snapshot(str(snapshot_path))

        if snapshot is None:
            return None

        return [Task(**t) for t in snapshot.tasks]

    def compare(self, current_date: str, previous_date: str | None = None) -> TaskChanges | None:
        """Compare tasks between two dates."""
        current_tasks = self.load(current_date)
        if current_tasks is None:
            return None

        if previous_date is None:
            previous_date = get_previous_working_day(current_date)

        previous_tasks = self.load(previous_date)
        if previous_tasks is None:
            return None

        return compare_tasks(current_tasks, previous_tasks)

    def generate_report(
        self,
        current_date: str,
        previous_date: str | None = None,
        output_path: str | None = None,
    ) -> str | None:
        """Generate and save a comparison report."""
        changes = self.compare(current_date, previous_date)
        if changes is None:
            return None

        if previous_date is None:
            previous_date = get_previous_working_day(current_date)

        report = generate_comparison_report(changes, current_date, previous_date)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"Wrote comparison report to {output_path}")

        return report

    def list_available_dates(self) -> list[str]:
        """List all available snapshot dates."""
        dates = []
        for snapshot_file in self.snapshots_dir.glob("snapshot_*.json"):
            date = snapshot_file.stem.replace("snapshot_", "")
            dates.append(date)
        return sorted(dates, reverse=True)