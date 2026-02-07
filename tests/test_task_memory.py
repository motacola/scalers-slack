"""Tests for task memory behavior."""

from src.task_memory import TaskMemory


def test_mark_task_complete_counts_once_for_same_task(tmp_path):
    """Completing the same task repeatedly should not inflate completion counters."""
    memory_path = tmp_path / "task_memory.json"
    memory = TaskMemory(str(memory_path))

    memory.mark_task_complete(task_name="Homepage polish", assignee="Alice")
    memory.mark_task_complete(task_name="Homepage polish", assignee="Alice")

    stats = memory.get_stats()
    assert stats["total_tasks"] == 1
    assert stats["total_completions"] == 1
    assert memory.data["metadata"]["total_tasks_tracked"] == 1

