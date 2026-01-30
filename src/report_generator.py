"""Report generation utilities for creating formatted task reports."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.task_processor import Task, group_tasks_by_owner, group_tasks_by_client, sort_tasks_by_priority


class ReportGenerator:
    """Generate reports in various formats."""

    def __init__(self, tasks: list[Task], date: str | None = None):
        self.tasks = tasks
        self.date = date or datetime.now().strftime("%Y-%m-%d")

    def to_csv(self, output_path: str) -> None:
        """Generate CSV report."""
        fieldnames = [
            "Status",
            "Priority",
            "Due Date",
            "Task",
            "Channel",
            "Owner",
            "Client",
            "Task Type",
            "Urgency Score",
            "Is Actionable",
            "Tags",
            "Link",
            "Source",
        ]

        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for task in self.tasks:
                writer.writerow({
                    "Status": task.status,
                    "Priority": task.priority,
                    "Due Date": task.due_date,
                    "Task": task.text,
                    "Channel": task.channel,
                    "Owner": task.owner,
                    "Client": task.client,
                    "Task Type": task.task_type,
                    "Urgency Score": task.urgency_score,
                    "Is Actionable": task.is_actionable,
                    "Tags": ", ".join(task.tags),
                    "Link": task.permalink,
                    "Source": task.source,
                })

        print(f"Wrote {len(self.tasks)} rows to {output_path}")

    def to_json(self, output_path: str) -> None:
        """Generate JSON report."""
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "date": self.date,
            "total_tasks": len(self.tasks),
            "actionable_tasks": sum(1 for t in self.tasks if t.is_actionable),
            "high_priority_tasks": sum(1 for t in self.tasks if t.priority == "High"),
            "tasks": [asdict(task) for task in self.tasks],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        print(f"Wrote JSON report to {output_path}")

    def to_markdown(self, output_path: str, group_by: str = "owner") -> None:
        """Generate Markdown report with grouping."""
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# Daily Task Report - {self.date}",
            "",
            f"**Total Tasks:** {len(self.tasks)}",
            f"**Actionable Tasks:** {sum(1 for t in self.tasks if t.is_actionable)}",
            f"**High Priority:** {sum(1 for t in self.tasks if t.priority == 'High')}",
            "",
            "---",
            "",
        ]

        if group_by == "owner":
            lines.extend(self._generate_owner_section())
        elif group_by == "client":
            lines.extend(self._generate_client_section())
        else:
            lines.extend(self._generate_flat_section())

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"Wrote Markdown report to {output_path}")

    def _generate_owner_section(self) -> list[str]:
        """Generate tasks grouped by owner."""
        lines = []
        grouped = group_tasks_by_owner(self.tasks)

        for owner in sorted(grouped.keys()):
            tasks = sort_tasks_by_priority(grouped[owner])
            lines.append(f"## {owner}")
            lines.append("")

            actionable = [t for t in tasks if t.is_actionable]
            if actionable:
                lines.append("### Action Items")
                lines.append("")
                for task in actionable:
                    lines.extend(self._format_task_markdown(task))
                lines.append("")

            non_actionable = [t for t in tasks if not t.is_actionable]
            if non_actionable:
                lines.append("### Updates/Notes")
                lines.append("")
                for task in non_actionable:
                    lines.extend(self._format_task_markdown(task, compact=True))
                lines.append("")

        return lines

    def _generate_client_section(self) -> list[str]:
        """Generate tasks grouped by client."""
        lines = []
        grouped = group_tasks_by_client(self.tasks)

        for client in sorted(grouped.keys()):
            tasks = sort_tasks_by_priority(grouped[client])
            lines.append(f"## {client}")
            lines.append("")

            for task in tasks:
                lines.extend(self._format_task_markdown(task))
            lines.append("")

        return lines

    def _generate_flat_section(self) -> list[str]:
        """Generate flat list of tasks."""
        lines = []
        sorted_tasks = sort_tasks_by_priority(self.tasks)

        for task in sorted_tasks:
            lines.extend(self._format_task_markdown(task))

        return lines

    def _format_task_markdown(self, task: Task, compact: bool = False) -> list[str]:
        """Format a single task as markdown."""
        lines = []

        # Priority indicator
        priority_emoji = ""
        if task.priority == "High":
            priority_emoji = "🔴 "
        elif task.priority == "Medium":
            priority_emoji = "🟡 "
        elif task.priority == "Low":
            priority_emoji = "🟢 "

        # Task type emoji
        type_emoji = self._get_task_type_emoji(task.task_type)

        lines.append(f"{priority_emoji}{type_emoji} {task.text}")

        if not compact:
            meta = []
            if task.client:
                meta.append(f"**Client:** {task.client}")
            if task.owner:
                meta.append(f"**Owner:** {task.owner}")
            if task.due_date:
                meta.append(f"**Due:** {task.due_date}")
            if task.tags:
                meta.append(f"**Tags:** {', '.join(task.tags)}")

            if meta:
                lines.append(" | ".join(meta))

            if task.permalink:
                lines.append(f"[View in Slack]({task.permalink})")

        lines.append("")

        return lines

    def _get_task_type_emoji(self, task_type: str) -> str:
        """Get emoji for task type."""
        emojis = {
            "bug": "🐛",
            "feature": "✨",
            "content": "📝",
            "design": "🎨",
            "review": "👀",
            "deployment": "🚀",
            "update": "🔄",
            "seo": "🔍",
            "integration": "🔌",
            "general": "📋",
        }
        return emojis.get(task_type, "📋")

    def to_html(self, output_path: str, group_by: str = "owner") -> None:
        """Generate HTML report with grouping."""
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>Daily Task Report - {self.date}</title>",
            self._get_html_styles(),
            "</head>",
            "<body>",
            f"<h1>Daily Task Report - {self.date}</h1>",
            "<div class='summary'>",
            f"<p><strong>Total Tasks:</strong> {len(self.tasks)}</p>",
            f"<p><strong>Actionable Tasks:</strong> {sum(1 for t in self.tasks if t.is_actionable)}</p>",
            f"<p><strong>High Priority:</strong> {sum(1 for t in self.tasks if t.priority == 'High')}</p>",
            "</div>",
        ]

        if group_by == "owner":
            html_parts.extend(self._generate_owner_html())
        elif group_by == "client":
            html_parts.extend(self._generate_client_html())
        else:
            html_parts.extend(self._generate_flat_html())

        html_parts.extend([
            "</body>",
            "</html>",
        ])

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(html_parts))

        print(f"Wrote HTML report to {output_path}")

    def _get_html_styles(self) -> str:
        """Get CSS styles for HTML report."""
        return """
<style>
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    background: #f5f5f5;
}
h1 {
    color: #333;
    border-bottom: 2px solid #4CAF50;
    padding-bottom: 10px;
}
h2 {
    color: #555;
    margin-top: 30px;
    background: #e8e8e8;
    padding: 10px;
    border-radius: 5px;
}
h3 {
    color: #666;
    margin-top: 20px;
}
.summary {
    background: white;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.task {
    background: white;
    padding: 15px;
    margin: 10px 0;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    border-left: 4px solid #ddd;
}
.task.high-priority {
    border-left-color: #f44336;
}
.task.medium-priority {
    border-left-color: #ff9800;
}
.task.low-priority {
    border-left-color: #4CAF50;
}
.task-text {
    font-size: 16px;
    margin-bottom: 8px;
}
.task-meta {
    font-size: 13px;
    color: #666;
}
.tag {
    display: inline-block;
    background: #e3f2fd;
    color: #1976d2;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    margin-right: 5px;
}
.tag.urgent {
    background: #ffebee;
    color: #c62828;
}
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
    margin-right: 5px;
}
.badge-high {
    background: #f44336;
    color: white;
}
.badge-medium {
    background: #ff9800;
    color: white;
}
.badge-low {
    background: #4CAF50;
    color: white;
}
a {
    color: #1976d2;
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}
</style>
"""

    def _generate_owner_html(self) -> list[str]:
        """Generate HTML grouped by owner."""
        parts = []
        grouped = group_tasks_by_owner(self.tasks)

        for owner in sorted(grouped.keys()):
            tasks = sort_tasks_by_priority(grouped[owner])
            parts.append(f"<h2>{owner}</h2>")

            actionable = [t for t in tasks if t.is_actionable]
            if actionable:
                parts.append("<h3>Action Items</h3>")
                for task in actionable:
                    parts.extend(self._format_task_html(task))

            non_actionable = [t for t in tasks if not t.is_actionable]
            if non_actionable:
                parts.append("<h3>Updates/Notes</h3>")
                for task in non_actionable:
                    parts.extend(self._format_task_html(task, compact=True))

        return parts

    def _generate_client_html(self) -> list[str]:
        """Generate HTML grouped by client."""
        parts = []
        grouped = group_tasks_by_client(self.tasks)

        for client in sorted(grouped.keys()):
            tasks = sort_tasks_by_priority(grouped[client])
            parts.append(f"<h2>{client}</h2>")

            for task in tasks:
                parts.extend(self._format_task_html(task))

        return parts

    def _generate_flat_html(self) -> list[str]:
        """Generate flat HTML list."""
        parts = []
        sorted_tasks = sort_tasks_by_priority(self.tasks)

        for task in sorted_tasks:
            parts.extend(self._format_task_html(task))

        return parts

    def _format_task_html(self, task: Task, compact: bool = False) -> list[str]:
        """Format a single task as HTML."""
        priority_class = ""
        if task.priority == "High":
            priority_class = "high-priority"
        elif task.priority == "Medium":
            priority_class = "medium-priority"
        elif task.priority == "Low":
            priority_class = "low-priority"

        badge = ""
        if task.priority:
            badge_class = f"badge-{task.priority.lower()}"
            badge = f"<span class='badge {badge_class}'>{task.priority}</span>"

        tags = ""
        for tag in task.tags:
            tag_class = "urgent" if tag == "urgent" else ""
            tags += f"<span class='tag {tag_class}'>{tag}</span>"

        meta = []
        if task.client:
            meta.append(f"<strong>Client:</strong> {task.client}")
        if task.owner:
            meta.append(f"<strong>Owner:</strong> {task.owner}")
        if task.due_date:
            meta.append(f"<strong>Due:</strong> {task.due_date}")
        if task.task_type:
            meta.append(f"<strong>Type:</strong> {task.task_type}")

        meta_html = " | ".join(meta) if meta else ""

        link = f"<a href='{task.permalink}' target='_blank'>View in Slack</a>" if task.permalink else ""

        return [
            f"<div class='task {priority_class}'>",
            f"<div class='task-text'>{badge} {task.text}</div>",
            f"<div class='task-meta'>{meta_html} {tags}</div>" if not compact else "",
            f"<div class='task-meta'>{link}</div>" if link and not compact else "",
            "</div>",
        ]