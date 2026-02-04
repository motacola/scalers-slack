"""Report generation utilities for creating formatted task reports."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.task_processor import Task, group_tasks_by_client, group_tasks_by_owner, sort_tasks_by_priority


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

        actionable_count = sum(1 for t in self.tasks if t.is_actionable)
        fyi_count = len(self.tasks) - actionable_count
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>Slack Digest • {self.date}</title>",
            "<meta name='viewport' content='width=device-width, initial-scale=1' />",
            self._get_html_styles(),
            "</head>",
            "<body>",
            f"<h1>Slack digest (last 24 hours) • {self.date}</h1>",
            "<div class='summary'>",
            "<p class='summary-lede'>Here’s the useful stuff from your Slack DMs. Nothing is posted automatically.</p>",
            f"<div class='summary-grid'>",
            f"<div class='summary-card'><div class='summary-num'>{actionable_count}</div><div class='summary-label'>Things to do</div></div>",
            f"<div class='summary-card'><div class='summary-num'>{fyi_count}</div><div class='summary-label'>FYI / context</div></div>",
            "</div>",
            "<div class='controls'>",
            "<input id='filter' class='filter' type='search' placeholder='Filter… (type a name or keyword)' oninput='filterTasks()' />",
            "<button class='btn' onclick='toggleAll(true)'>Expand all</button>",
            "<button class='btn' onclick='toggleAll(false)'>Collapse all</button>",
            "</div>",
            "</div>",
        ]

        if group_by == "owner":
            html_parts.extend(self._generate_owner_html())
        elif group_by == "client":
            html_parts.extend(self._generate_client_html())
        else:
            html_parts.extend(self._generate_flat_html())

        html_parts.extend([
            "<script>",
            "function filterTasks(){",
            "  const q=(document.getElementById('filter').value||'').toLowerCase();",
            "  const items=document.querySelectorAll('[data-task]');",
            "  items.forEach(el=>{",
            "    const txt=(el.getAttribute('data-task')||'').toLowerCase();",
            "    el.style.display = (!q || txt.includes(q)) ? '' : 'none';",
            "  });",
            "}",
            "function toggleAll(open){",
            "  document.querySelectorAll('details.owner').forEach(d=>{d.open=open;});",
            "}",
            "</script>",
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
:root{
  --bg:#0b0f14;
  --panel:#111824;
  --muted:#94a3b8;
  --text:#e5e7eb;
  --accent:#60a5fa;
  --border:rgba(148,163,184,0.18);
  --good:#22c55e;
  --warn:#f59e0b;
  --bad:#ef4444;
}
*{box-sizing:border-box;}
body{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,system-ui,sans-serif;
  margin:0;
  padding:18px;
  background:var(--bg);
  color:var(--text);
}
h1{
  font-size:20px;
  margin:0 0 12px 0;
}
.summary{
  background:var(--panel);
  border:1px solid var(--border);
  border-radius:12px;
  padding:14px;
  margin-bottom:14px;
}
.summary-lede{margin:0 0 12px 0; color:var(--muted);}
.summary-grid{display:flex; gap:10px; flex-wrap:wrap;}
.summary-card{
  flex:0 0 auto;
  min-width:140px;
  background:rgba(255,255,255,0.03);
  border:1px solid var(--border);
  border-radius:10px;
  padding:10px 12px;
}
.summary-num{font-size:22px; font-weight:700; line-height:1;}
.summary-label{color:var(--muted); font-size:12px; margin-top:4px;}
.controls{display:flex; gap:8px; flex-wrap:wrap; margin-top:12px;}
.filter{
  flex:1 1 240px;
  background:rgba(255,255,255,0.03);
  border:1px solid var(--border);
  border-radius:10px;
  padding:10px 12px;
  color:var(--text);
}
.btn{
  background:rgba(255,255,255,0.06);
  border:1px solid var(--border);
  color:var(--text);
  border-radius:10px;
  padding:10px 12px;
  cursor:pointer;
}
.btn:hover{border-color:rgba(96,165,250,0.6);}

/* Owners */
details.owner{
  background:var(--panel);
  border:1px solid var(--border);
  border-radius:12px;
  margin:10px 0;
  overflow:hidden;
}
details.owner > summary{
  list-style:none;
  cursor:pointer;
  padding:12px 14px;
  font-weight:700;
}
details.owner > summary::-webkit-details-marker{display:none;}
.owner-meta{color:var(--muted); font-weight:500; font-size:12px; margin-left:8px;}
.section{padding:0 14px 10px 14px;}
.section h3{margin:12px 0 8px 0; font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:0.04em;}

/* Tasks */
.task{
  padding:10px 12px;
  border:1px solid var(--border);
  border-radius:10px;
  margin:8px 0;
  background:rgba(255,255,255,0.02);
}
.taskline{display:flex; gap:10px; align-items:flex-start;}
.pill{
  flex:0 0 auto;
  padding:2px 8px;
  border-radius:999px;
  font-size:12px;
  border:1px solid var(--border);
  color:var(--muted);
}
.pill.todo{color:#0b0f14; background:var(--good); border-color:transparent;}
.pill.fyi{color:var(--muted);}
.tasktext{font-size:14px; line-height:1.35;}
.taskmeta{margin-top:6px; color:var(--muted); font-size:12px;}
.taskmeta a{color:var(--accent); text-decoration:none;}
.taskmeta a:hover{text-decoration:underline;}
</style>
"""

    def _generate_owner_html(self) -> list[str]:
        """Generate friendly HTML grouped by owner."""
        parts: list[str] = []
        grouped = group_tasks_by_owner(self.tasks)

        for owner in sorted(grouped.keys()):
            tasks = sort_tasks_by_priority(grouped[owner])
            actionable = [t for t in tasks if t.is_actionable]
            non_actionable = [t for t in tasks if not t.is_actionable]
            parts.append(
                "<details class='owner' open>"
                f"<summary>{self._escape(owner)}"
                f"<span class='owner-meta'>({len(actionable)} to do • {len(non_actionable)} FYI)</span>"
                "</summary>"
            )
            parts.append("<div class='section'>")

            if actionable:
                parts.append("<h3>Things to do</h3>")
                for task in actionable:
                    parts.extend(self._format_task_html(task, compact=False))

            if non_actionable:
                parts.append("<h3>FYI</h3>")
                for task in non_actionable:
                    parts.extend(self._format_task_html(task, compact=True))

            parts.append("</div>")
            parts.append("</details>")

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

    def _escape(self, text: str) -> str:
        return (
            (text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def _format_task_html(self, task: Task, compact: bool = False) -> list[str]:
        """Format a single item in a friendly, readable way."""
        pill = "To do" if task.is_actionable else "FYI"
        pill_class = "todo" if task.is_actionable else "fyi"

        safe_text = self._escape(task.text)
        data_attr = self._escape(f"{task.owner} {task.channel} {task.client} {task.task_type} {task.text}")

        meta_bits: list[str] = []
        if task.due_date and task.is_actionable:
            meta_bits.append(f"Due: {self._escape(task.due_date)}")
        if task.tags and task.is_actionable:
            meta_bits.append("Tags: " + ", ".join(self._escape(t) for t in task.tags))

        meta = " • ".join(meta_bits)
        link = f"<a href='{self._escape(task.permalink)}' target='_blank'>Open in Slack</a>" if task.permalink else ""

        meta_line = ""
        if not compact:
            if meta and link:
                meta_line = f"<div class='taskmeta'>{meta} • {link}</div>"
            elif meta:
                meta_line = f"<div class='taskmeta'>{meta}</div>"
            elif link:
                meta_line = f"<div class='taskmeta'>{link}</div>"

        return [
            f"<div class='task' data-task='{data_attr}'>",
            "<div class='taskline'>",
            f"<span class='pill {pill_class}'>{pill}</span>",
            f"<div class='tasktext'>{safe_text}</div>",
            "</div>",
            meta_line,
            "</div>",
        ]