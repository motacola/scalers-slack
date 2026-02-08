from scripts.init_task_memory import _apply_seed_date_defaults, apply_seed, build_default_seed
from src.task_memory import TaskMemory


def test_build_default_seed_uses_requested_date():
    seed = build_default_seed("2026-02-07")

    assert seed["snapshot_date"] == "2026-02-07"
    due_dates = [task.get("due_date") for task in seed["tasks"] if "due_date" in task]
    assert due_dates
    assert all(value == "2026-02-07" for value in due_dates)


def test_apply_seed_date_defaults_fills_missing_fields():
    seed = {
        "standups": [{"team_member": "Alice", "tasks": ["Task A"]}],
        "tasks": [{"task_name": "Task B", "assignee": "Alice", "status": "pending"}],
    }

    result = _apply_seed_date_defaults(seed, "2026-02-07")

    assert result["snapshot_date"] == "2026-02-07"
    assert result["standups"][0]["date"] == "2026-02-07"
    assert result["tasks"][0]["due_date"] == "2026-02-07"


def test_apply_seed_dry_run_does_not_write_data(tmp_path):
    memory_path = tmp_path / "task_memory.json"
    memory = TaskMemory(str(memory_path))

    seed = {
        "setup_default_team": False,
        "completed_tasks": [
            {
                "task_name": "Homepage polish",
                "assignee": "Alice",
            }
        ],
        "tasks": [],
        "standups": [],
        "snapshot_date": "2026-02-07",
    }

    summary = apply_seed(memory, seed, dry_run=True)

    assert summary["completed_tasks"] == 1
    assert memory.get_task("homepage_polish_alice") is None


def test_apply_seed_writes_when_not_dry_run(tmp_path):
    memory_path = tmp_path / "task_memory.json"
    memory = TaskMemory(str(memory_path))

    seed = {
        "setup_default_team": False,
        "completed_tasks": [],
        "standups": [
            {
                "team_member": "Alice",
                "tasks": ["Task A"],
                "date": "2026-02-07",
                "timestamp": "2026-02-07T09:00:00",
            }
        ],
        "tasks": [
            {
                "task_name": "Task A",
                "assignee": "Alice",
                "status": "pending",
                "source": "manual",
                "due_date": "2026-02-07",
            }
        ],
        "snapshot_date": "2026-02-07",
    }

    apply_seed(memory, seed, dry_run=False)

    tasks = memory.get_tasks_by_assignee("Alice")
    assert len(tasks) == 1
    assert memory.get_standup("Alice", "2026-02-07") is not None
    assert memory.get_daily_snapshot("2026-02-07") is not None
