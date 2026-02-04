"""
Example Priority Processor Plugin
Demonstrates custom task processing logic.
"""

from typing import Any

from src.plugin_system import PluginMetadata, TaskProcessorPlugin


class PriorityBoostProcessor(TaskProcessorPlugin):
    """Boost priority of tasks with specific keywords."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Priority Booster",
            version="1.0.0",
            description="Automatically boosts priority for urgent keywords",
            author="Scalers Team",
        )

    def __init__(self):
        super().__init__()
        self.urgent_keywords = ["urgent", "asap", "critical", "blocker", "emergency", "p0"]

    def should_process(self, task: Any) -> bool:
        """Process tasks that contain urgent keywords."""
        if isinstance(task, dict):
            text = task.get("text", "").lower()
            return any(keyword in text for keyword in self.urgent_keywords)
        return False

    def process_task(self, task: Any) -> Any:
        """Boost task priority to critical."""
        if isinstance(task, dict):
            # Add urgency marker
            task["priority"] = "critical"
            task["auto_boosted"] = True

            # Log the boost
            import logging

            logger = logging.getLogger(__name__)
            logger.info("🚨 Boosted task priority: %s", task.get("text", "")[:50])

        return task


class MentionProcessor(TaskProcessorPlugin):
    """Extract and tag tasks with user mentions."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Mention Processor",
            version="1.0.0",
            description="Extracts and tags @mentions in tasks",
            author="Scalers Team",
        )

    def should_process(self, task: Any) -> bool:
        """Process all tasks."""
        return isinstance(task, dict)

    def process_task(self, task: Any) -> Any:
        """Extract mentions from task text."""
        import re

        if isinstance(task, dict):
            text = task.get("text", "")

            # Find all @mentions
            mentions = re.findall(r"@(\w+)", text)

            if mentions:
                task["mentions"] = mentions
                task["has_mentions"] = True

                import logging

                logger = logging.getLogger(__name__)
                logger.debug("Found mentions in task: %s", mentions)

        return task
