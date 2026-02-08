import json
import logging
import os
from typing import Any, Dict, List, Optional, cast

logger = logging.getLogger(__name__)


class ProjectMemory:
    """Persistent memory system for tracking project sync progress and avoiding redundant work."""

    def __init__(self, memory_path: str = "config/project_memory.json"):
        self.memory_path = memory_path
        self.data: Dict[str, Any] = {
            "projects": {},
            "global": {"last_run": None, "total_runs": 0, "token_savings_estimate": 0},
        }
        self.load()

    def load(self) -> None:
        """Load memory from disk."""
        if not os.path.exists(self.memory_path):
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            self.save()
            return

        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load project memory: {e}. Starting fresh.")

    def save(self) -> None:
        """Save memory to disk."""
        try:
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save project memory: {e}")

    def get_project_state(self, project_name: str) -> Dict[str, Any]:
        """Get the last known state for a project."""
        state = self.data["projects"].get(
            project_name,
            {
                "last_sync": None,
                "processed_count": 0,
                "failed_count": 0,
                "last_error": None,
                "seen_threads": [],
            },
        )
        return cast(Dict[str, Any], state)

    def update_project_sync(
        self, project_name: str, sync_ts: str, thread_count: int, threads: Optional[List[str]] = None
    ) -> None:
        """Update the synced state for a project."""
        state = self.get_project_state(project_name)
        state["last_sync"] = sync_ts
        state["processed_count"] += thread_count

        # Maintain a buffer of seen threads (rolling window of last 500)
        seen = state.get("seen_threads", [])
        if threads:
            for t in threads:
                if t not in seen:
                    seen.append(t)
            state["seen_threads"] = seen[-500:]  # Keep last 500

        self.data["projects"][project_name] = state
        self.data["global"]["last_run"] = sync_ts
        self.data["global"]["total_runs"] += 1
        self.save()

    def mark_failed(self, project_name: str, error: str) -> None:
        """Record a failure for a project."""
        state = self.get_project_state(project_name)
        state["failed_count"] += 1
        state["last_error"] = error
        self.data["projects"][project_name] = state
        self.save()

    def is_thread_processed(self, project_name: str, thread_ts: str) -> bool:
        """Check if a specific thread timestamp has already been processed for this project."""
        state = self.get_project_state(project_name)
        return thread_ts in state.get("seen_threads", [])
