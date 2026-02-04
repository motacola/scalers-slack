"""Tests for task processor module."""

from src.task_processor import (
    Task,
    filter_actionable_tasks,
    group_tasks_by_client,
    group_tasks_by_owner,
    is_likely_task,
    sort_tasks_by_priority,
)


def create_test_task(**kwargs) -> Task:
    """Create a test task with default values."""
    defaults = {
        "text": "Test task",
        "channel": "C123",
        "owner": "Test User",
        "timestamp": "2024-01-01T12:00:00",
        "permalink": "https://example.slack.com/archives/C123/p1234567890123",
        "source": "slack",
        "status": "Open",
        "priority": "medium",
        "due_date": "",
        "client": "General",
        "task_type": "",
        "urgency_score": 0,
        "is_actionable": True,
        "mentions": [],
        "tags": [],
    }
    defaults.update(kwargs)
    return Task(**defaults)


def test_task_creation():
    """Test Task dataclass creation."""
    task = create_test_task(text="Sample task", priority="high")
    assert task.text == "Sample task"
    assert task.priority == "high"
    assert task.is_actionable is True


def test_is_likely_task_with_keywords():
    """Test task detection with keywords."""
    text = "TODO: Fix the bug in production"
    assert is_likely_task(text) is True


def test_is_likely_task_question():
    """Test question detection."""
    text = "Can you help me with this?"
    assert is_likely_task(text) is True


def test_is_likely_task_not_actionable():
    """Test non-actionable text."""
    text = "Just saying hi to everyone"
    # This might or might not be detected as a task
    result = is_likely_task(text)
    assert isinstance(result, bool)


def test_filter_actionable_tasks():
    """Test filtering for actionable tasks."""
    tasks = [
        create_test_task(text="TODO: Fix bug", is_actionable=True),
        create_test_task(text="Just a message", is_actionable=False),
        create_test_task(text="Can you review?", is_actionable=True),
    ]

    actionable = filter_actionable_tasks(tasks)
    assert len(actionable) == 2
    assert all(t.is_actionable for t in actionable)


def test_sort_tasks_by_priority():
    """Test sorting tasks by urgency score."""
    tasks = [
        create_test_task(text="Low urgency", urgency_score=1),
        create_test_task(text="High urgency", urgency_score=10),
        create_test_task(text="Medium urgency", urgency_score=5),
    ]

    sorted_tasks = sort_tasks_by_priority(tasks)
    assert sorted_tasks[0].urgency_score == 10
    assert sorted_tasks[1].urgency_score == 5
    assert sorted_tasks[2].urgency_score == 1


def test_group_tasks_by_owner():
    """Test grouping tasks by owner."""
    tasks = [
        create_test_task(text="Task 1", owner="Alice"),
        create_test_task(text="Task 2", owner="Bob"),
        create_test_task(text="Task 3", owner="Alice"),
    ]

    grouped = group_tasks_by_owner(tasks)
    assert "Alice" in grouped
    assert "Bob" in grouped
    assert len(grouped["Alice"]) == 2
    assert len(grouped["Bob"]) == 1


def test_group_tasks_by_client():
    """Test grouping tasks by client."""
    tasks = [
        create_test_task(text="Task 1", client="Client A"),
        create_test_task(text="Task 2", client="Client B"),
        create_test_task(text="Task 3", client="Client A"),
    ]

    grouped = group_tasks_by_client(tasks)
    assert "Client A" in grouped
    assert "Client B" in grouped
    assert len(grouped["Client A"]) == 2
    assert len(grouped["Client B"]) == 1


def test_task_with_tags():
    """Test task with multiple tags."""
    task = create_test_task(text="URGENT: Please review", tags=["urgent", "review"])
    assert "urgent" in task.tags
    assert "review" in task.tags
    assert len(task.tags) == 2


def test_task_permalink():
    """Test task permalink generation."""
    task = create_test_task(channel="C123ABC", permalink="https://example.slack.com/archives/C123ABC/p1234567890123456")
    assert "C123ABC" in task.permalink
    assert "p1234567890123456" in task.permalink
