"""Tests for plugin system."""

from __future__ import annotations

from src.plugin_system import (
    LLMProviderPlugin,
    NotificationPlugin,
    PluginManager,
    PluginMetadata,
    ReportFormatterPlugin,
    TaskProcessorPlugin,
    get_plugin_manager,
)


# Test plugin implementations
class TestTaskProcessor(TaskProcessorPlugin):
    """Test task processor."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(name="Test Processor", version="1.0.0", description="Test")

    def process_task(self, task):
        task["processed"] = True
        return task


class TestReportFormatter(ReportFormatterPlugin):
    """Test report formatter."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(name="Test Formatter", version="1.0.0", description="Test")

    def get_format_name(self) -> str:
        return "test"

    def format_report(self, data, output_path=None):
        return "formatted"


class TestNotifier(NotificationPlugin):
    """Test notifier."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(name="Test Notifier", version="1.0.0", description="Test")

    def get_channel_name(self) -> str:
        return "test"

    def send_notification(self, message, metadata=None):
        return True


class TestLLMProvider(LLMProviderPlugin):
    """Test LLM provider."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(name="Test LLM", version="1.0.0", description="Test")

    def get_provider_name(self) -> str:
        return "test"

    def generate(self, prompt, system_prompt=None):
        return "generated"


class TestPluginMetadata:
    """Test PluginMetadata class."""

    def test_create_metadata(self):
        """Test creating plugin metadata."""
        metadata = PluginMetadata(name="Test", version="1.0.0", description="Test plugin")

        assert metadata.name == "Test"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test plugin"
        assert metadata.enabled is True
        assert metadata.dependencies == []

    def test_metadata_with_dependencies(self):
        """Test metadata with dependencies."""
        metadata = PluginMetadata(
            name="Test", version="1.0.0", description="Test", dependencies=["requests", "pytest"]
        )

        assert len(metadata.dependencies) == 2
        assert "requests" in metadata.dependencies


class TestPluginManager:
    """Test PluginManager class."""

    def test_create_manager(self):
        """Test creating plugin manager."""
        manager = PluginManager()

        assert len(manager.plugins) == 0
        assert len(manager.plugin_types) == 4

    def test_register_task_processor(self):
        """Test registering task processor plugin."""
        manager = PluginManager()
        plugin = TestTaskProcessor()
        plugin.initialize()

        manager.plugins["test.processor"] = plugin
        manager.plugin_types["task_processor"].append(plugin)

        assert "test.processor" in manager.plugins
        assert plugin in manager.plugin_types["task_processor"]

    def test_get_plugin(self):
        """Test getting plugin by ID."""
        manager = PluginManager()
        plugin = TestTaskProcessor()

        manager.plugins["test.processor"] = plugin

        retrieved = manager.get_plugin("test.processor")
        assert retrieved is plugin

    def test_get_plugins_by_type(self):
        """Test getting plugins by type."""
        manager = PluginManager()

        processor = TestTaskProcessor()
        formatter = TestReportFormatter()

        manager.plugin_types["task_processor"].append(processor)
        manager.plugin_types["report_formatter"].append(formatter)

        processors = manager.get_plugins_by_type("task_processor")
        assert len(processors) == 1
        assert processors[0] is processor

    def test_get_report_formatter(self):
        """Test getting report formatter by name."""
        manager = PluginManager()
        formatter = TestReportFormatter()

        manager.plugin_types["report_formatter"].append(formatter)

        retrieved = manager.get_report_formatter("test")
        assert retrieved is formatter

    def test_get_notification_channel(self):
        """Test getting notification channel by name."""
        manager = PluginManager()
        notifier = TestNotifier()

        manager.plugin_types["notification"].append(notifier)

        retrieved = manager.get_notification_channel("test")
        assert retrieved is notifier

    def test_get_llm_provider(self):
        """Test getting LLM provider by name."""
        manager = PluginManager()
        provider = TestLLMProvider()

        manager.plugin_types["llm_provider"].append(provider)

        retrieved = manager.get_llm_provider("test")
        assert retrieved is provider

    def test_unload_plugin(self):
        """Test unloading a plugin."""
        manager = PluginManager()
        plugin = TestTaskProcessor()

        manager.plugins["test.processor"] = plugin
        manager.plugin_types["task_processor"].append(plugin)

        result = manager.unload_plugin("test.processor")

        assert result is True
        assert "test.processor" not in manager.plugins
        assert plugin not in manager.plugin_types["task_processor"]

    def test_get_summary(self):
        """Test getting plugin summary."""
        manager = PluginManager()

        processor = TestTaskProcessor()
        manager.plugins["test.processor"] = processor
        manager.plugin_types["task_processor"].append(processor)

        summary = manager.get_summary()

        assert "Plugin System Summary" in summary
        assert "Test Processor" in summary


class TestPluginImplementations:
    """Test plugin implementations."""

    def test_task_processor(self):
        """Test task processor plugin."""
        processor = TestTaskProcessor()
        task = {"id": 1, "text": "Test task"}

        processed = processor.process_task(task)

        assert processed["processed"] is True

    def test_report_formatter(self):
        """Test report formatter plugin."""
        formatter = TestReportFormatter()

        result = formatter.format_report({"tasks": []})

        assert result == "formatted"
        assert formatter.get_format_name() == "test"

    def test_notifier(self):
        """Test notification plugin."""
        notifier = TestNotifier()

        result = notifier.send_notification("Test message")

        assert result is True
        assert notifier.get_channel_name() == "test"

    def test_llm_provider(self):
        """Test LLM provider plugin."""
        provider = TestLLMProvider()

        result = provider.generate("Test prompt")

        assert result == "generated"
        assert provider.get_provider_name() == "test"


class TestGlobalPluginManager:
    """Test global plugin manager."""

    def test_get_global_manager(self):
        """Test getting global plugin manager."""
        manager1 = get_plugin_manager()
        manager2 = get_plugin_manager()

        assert manager1 is manager2
