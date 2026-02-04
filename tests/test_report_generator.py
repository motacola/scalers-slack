"""Tests for report generator module."""

import json
import tempfile
from pathlib import Path

from src.report_generator import ReportGenerator
from src.task_processor import Task


def create_test_tasks() -> list[Task]:
    """Create sample tasks for testing."""
    return [
        Task(
            text="Fix the login bug",
            channel="C123",
            owner="Alice",
            timestamp="2024-01-01T10:00:00",
            permalink="https://example.slack.com/archives/C123/p1234567890123",
            source="slack",
            status="Open",
            priority="high",
            client="Client A",
            tags=["bug", "urgent"],
            is_actionable=True,
        ),
        Task(
            text="Update documentation",
            channel="C456",
            owner="Bob",
            timestamp="2024-01-01T11:00:00",
            permalink="https://example.slack.com/archives/C456/p1234567891456",
            source="slack",
            status="Open",
            priority="low",
            client="Client B",
            tags=["documentation"],
            is_actionable=True,
        ),
    ]


def test_report_generator_initialization():
    """Test ReportGenerator initialization."""
    tasks = create_test_tasks()
    gen = ReportGenerator(tasks)
    assert len(gen.tasks) == 2
    assert gen.date is not None


def test_csv_report_generation():
    """Test CSV report generation."""
    tasks = create_test_tasks()
    gen = ReportGenerator(tasks)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_report.csv"
        gen.to_csv(str(output_path))

        assert output_path.exists()
        content = output_path.read_text()
        assert "Fix the login bug" in content
        assert "Update documentation" in content
        assert "Alice" in content
        assert "Bob" in content


def test_json_report_generation():
    """Test JSON report generation."""
    tasks = create_test_tasks()
    gen = ReportGenerator(tasks)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_report.json"
        gen.to_json(str(output_path))

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        # JSON format includes metadata and tasks list
        assert "tasks" in data
        assert len(data["tasks"]) == 2
        assert data["tasks"][0]["text"] == "Fix the login bug"
        assert data["tasks"][1]["owner"] == "Bob"


def test_markdown_report_generation():
    """Test Markdown report generation."""
    tasks = create_test_tasks()
    gen = ReportGenerator(tasks)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_report.md"
        gen.to_markdown(str(output_path))

        assert output_path.exists()
        content = output_path.read_text()
        assert "# Daily Task Report" in content or "Task Report" in content
        assert "Fix the login bug" in content
        assert "Alice" in content


def test_html_report_generation():
    """Test HTML report generation."""
    tasks = create_test_tasks()
    gen = ReportGenerator(tasks, date="2024-01-01")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_report.html"
        gen.to_html(str(output_path))

        assert output_path.exists()
        content = output_path.read_text()
        assert "<html" in content
        assert "Fix the login bug" in content
        assert "2024-01-01" in content


def test_report_with_custom_date():
    """Test report generation with custom date."""
    tasks = create_test_tasks()
    gen = ReportGenerator(tasks, date="2024-02-15")

    assert gen.date == "2024-02-15"


def test_empty_task_list():
    """Test report generation with empty task list."""
    gen = ReportGenerator([])

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "empty_report.json"
        gen.to_json(str(output_path))

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert "tasks" in data
        assert len(data["tasks"]) == 0
