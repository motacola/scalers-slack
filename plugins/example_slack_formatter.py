"""
Example Slack Block Formatter Plugin
Demonstrates custom report formatting for Slack.
"""

from typing import Any

from src.plugin_system import PluginMetadata, ReportFormatterPlugin


class SlackBlockFormatter(ReportFormatterPlugin):
    """Format reports as Slack Block Kit JSON."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Slack Block Formatter",
            version="1.0.0",
            description="Formats reports as Slack Block Kit JSON for rich messages",
            author="Scalers Team",
        )

    def get_format_name(self) -> str:
        return "slack"

    def get_file_extension(self) -> str:
        return ".json"

    def format_report(self, data: dict[str, Any], output_path: str | None = None) -> str:
        """Format report as Slack blocks."""
        import json

        tasks = data.get("tasks", [])
        summary = data.get("summary", {})

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 Daily Task Report", "emoji": True},
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total Tasks:*\n{summary.get('total_tasks', 0)}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*High Priority:*\n{summary.get('high_priority_count', 0)}",
                    },
                ],
            },
        ]

        # Add task list
        if tasks:
            blocks.append({"type": "divider"})
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Recent Tasks:*"},
                }
            )

            for task in tasks[:10]:  # Limit to 10
                priority_emoji = "🔴" if task.get("priority") == "high" else "🟡"
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{priority_emoji} {task.get('text', 'No description')}\n"
                            f"_Channel: #{task.get('channel', 'unknown')}_",
                        },
                    }
                )

        result = {"blocks": blocks}

        if output_path:
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            return output_path

        return json.dumps(result, indent=2)
