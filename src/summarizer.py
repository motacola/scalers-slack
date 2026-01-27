from typing import Any

from .models import Thread


class ActivitySummarizer:
    def __init__(self, engine: Any):
        self.engine = engine

    def format_activity(self, activity_map: dict[str, list[Thread]]) -> str:
        report = []
        report.append("# Daily Project Activity Context\n")

        for project_name, threads in activity_map.items():
            if not threads:
                continue

            report.append(f"## Project: {project_name}")
            report.append(f"Total entries: {len(threads)}")

            for thread in threads[:10]:  # Limit to 10 most recent to keep context manageable
                user_name = self.engine._resolve_user_name(thread.user_id) if thread.user_id else "unknown"
                timestamp = thread.created_at or "unknown time"
                text = thread.text.replace("\n", " ")

                line = f"- [{timestamp}] **{user_name}**: {text}"
                if thread.reply_count:
                    line += f" ({thread.reply_count} replies)"
                report.append(line)

            report.append("")  # Spacer

        return "\n".join(report)

    def synthesize_standup(self, activity_map: dict[str, list[Thread]]) -> str:
        """
        Generates a summary focusing on:
        1. Accomplishments
        2. Blockers
        3. Next Steps
        """
        context = self.format_activity(activity_map)

        # In a real production app, you'd call an LLM here with the context.
        # Since we are building this for the user, we'll provide the structured data
        # and a prompt template.

        prompt = f"""
Please analyze the following project activity and provide a 'Daily Standup' summary.
Focus on:
- What has been updated/completed?
- What are the outstanding blockers or wait-states?
- What are the recommended next steps for 'Christopher Belgrave'?

ACTIVITY CONTEXT:
{context}
"""
        return prompt
