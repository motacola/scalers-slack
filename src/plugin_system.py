"""
Plugin System
Extensible architecture for custom task processors, formatters, and integrations.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""

    name: str
    version: str
    description: str
    author: str = "Unknown"
    enabled: bool = True
    dependencies: list[str] = None  # type: ignore

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class Plugin(ABC):
    """Base class for all plugins."""

    def __init__(self):
        self.metadata = self.get_metadata()

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass

    def initialize(self) -> None:
        """Initialize the plugin. Called when plugin is loaded."""
        logger.info("Initializing plugin: %s v%s", self.metadata.name, self.metadata.version)

    def cleanup(self) -> None:
        """Cleanup plugin resources. Called when plugin is unloaded."""
        logger.info("Cleaning up plugin: %s", self.metadata.name)


class TaskProcessorPlugin(Plugin):
    """Plugin for custom task processing logic."""

    @abstractmethod
    def process_task(self, task: Any) -> Any:
        """
        Process a task and return modified task.

        Args:
            task: Task object to process

        Returns:
            Processed task object
        """
        pass

    def should_process(self, task: Any) -> bool:
        """
        Determine if this plugin should process the task.

        Args:
            task: Task to check

        Returns:
            True if plugin should process this task
        """
        return True


class ReportFormatterPlugin(Plugin):
    """Plugin for custom report formatting."""

    @abstractmethod
    def get_format_name(self) -> str:
        """Return the name of this format (e.g., 'pdf', 'slack')."""
        pass

    @abstractmethod
    def format_report(self, data: dict[str, Any], output_path: str | None = None) -> str:
        """
        Format report data.

        Args:
            data: Report data dictionary
            output_path: Optional output file path

        Returns:
            Formatted report as string or file path
        """
        pass

    def get_file_extension(self) -> str:
        """Return file extension for this format."""
        return ".txt"


class NotificationPlugin(Plugin):
    """Plugin for custom notification channels."""

    @abstractmethod
    def get_channel_name(self) -> str:
        """Return the name of this notification channel."""
        pass

    @abstractmethod
    def send_notification(self, message: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Send a notification.

        Args:
            message: Notification message
            metadata: Additional metadata

        Returns:
            True if notification was sent successfully
        """
        pass


class LLMProviderPlugin(Plugin):
    """Plugin for custom LLM providers."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of this LLM provider."""
        pass

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Generate text from prompt.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text
        """
        pass


class PluginManager:
    """Manages plugin discovery, loading, and execution."""

    def __init__(self):
        self.plugins: dict[str, Plugin] = {}
        self.plugin_types: dict[str, list[Plugin]] = {
            "task_processor": [],
            "report_formatter": [],
            "notification": [],
            "llm_provider": [],
        }

    def discover_plugins(self, plugin_dir: str | Path = "plugins") -> list[str]:
        """
        Discover plugins in the specified directory.

        Args:
            plugin_dir: Directory containing plugin modules

        Returns:
            List of discovered plugin module names
        """
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            logger.warning("Plugin directory not found: %s", plugin_path)
            return []

        discovered = []
        for file_path in plugin_path.glob("*.py"):
            if file_path.stem.startswith("_"):
                continue  # Skip private modules

            module_name = f"{plugin_dir}.{file_path.stem}".replace("/", ".")
            discovered.append(module_name)
            logger.debug("Discovered plugin module: %s", module_name)

        return discovered

    def load_plugin(self, module_name: str) -> Plugin | None:
        """
        Load a plugin from a module.

        Args:
            module_name: Python module name

        Returns:
            Loaded plugin instance or None if loading failed
        """
        try:
            module = importlib.import_module(module_name)

            # Find plugin classes in module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, Plugin) and obj is not Plugin and not inspect.isabstract(obj):
                    # Instantiate plugin
                    plugin = obj()
                    plugin.initialize()

                    # Register plugin
                    plugin_id = f"{module_name}.{name}"
                    self.plugins[plugin_id] = plugin

                    # Categorize plugin
                    if isinstance(plugin, TaskProcessorPlugin):
                        self.plugin_types["task_processor"].append(plugin)
                    if isinstance(plugin, ReportFormatterPlugin):
                        self.plugin_types["report_formatter"].append(plugin)
                    if isinstance(plugin, NotificationPlugin):
                        self.plugin_types["notification"].append(plugin)
                    if isinstance(plugin, LLMProviderPlugin):
                        self.plugin_types["llm_provider"].append(plugin)

                    logger.info("Loaded plugin: %s (%s)", plugin.metadata.name, plugin_id)
                    return plugin

        except Exception as e:
            logger.error("Failed to load plugin from %s: %s", module_name, e, exc_info=True)
            return None

        return None

    def load_all_plugins(self, plugin_dir: str | Path = "plugins") -> int:
        """
        Discover and load all plugins.

        Args:
            plugin_dir: Directory containing plugins

        Returns:
            Number of plugins loaded
        """
        discovered = self.discover_plugins(plugin_dir)
        loaded = 0

        for module_name in discovered:
            if self.load_plugin(module_name):
                loaded += 1

        logger.info("Loaded %d plugins from %s", loaded, plugin_dir)
        return loaded

    def get_plugin(self, plugin_id: str) -> Plugin | None:
        """Get a specific plugin by ID."""
        return self.plugins.get(plugin_id)

    def get_plugins_by_type(self, plugin_type: str) -> list[Plugin]:
        """Get all plugins of a specific type."""
        return self.plugin_types.get(plugin_type, [])

    def unload_plugin(self, plugin_id: str) -> bool:
        """
        Unload a plugin.

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if plugin was unloaded successfully
        """
        plugin = self.plugins.get(plugin_id)
        if not plugin:
            return False

        try:
            plugin.cleanup()

            # Remove from all registries
            del self.plugins[plugin_id]
            for plugins_list in self.plugin_types.values():
                if plugin in plugins_list:
                    plugins_list.remove(plugin)

            logger.info("Unloaded plugin: %s", plugin_id)
            return True

        except Exception as e:
            logger.error("Failed to unload plugin %s: %s", plugin_id, e)
            return False

    def unload_all_plugins(self) -> None:
        """Unload all plugins."""
        for plugin_id in list(self.plugins.keys()):
            self.unload_plugin(plugin_id)

    def get_report_formatter(self, format_name: str) -> ReportFormatterPlugin | None:
        """Get report formatter plugin by format name."""
        for plugin in self.plugin_types["report_formatter"]:
            if isinstance(plugin, ReportFormatterPlugin) and plugin.get_format_name() == format_name:
                return plugin
        return None

    def get_notification_channel(self, channel_name: str) -> NotificationPlugin | None:
        """Get notification plugin by channel name."""
        for plugin in self.plugin_types["notification"]:
            if isinstance(plugin, NotificationPlugin) and plugin.get_channel_name() == channel_name:
                return plugin
        return None

    def get_llm_provider(self, provider_name: str) -> LLMProviderPlugin | None:
        """Get LLM provider plugin by name."""
        for plugin in self.plugin_types["llm_provider"]:
            if isinstance(plugin, LLMProviderPlugin) and plugin.get_provider_name() == provider_name:
                return plugin
        return None

    def get_summary(self) -> str:
        """Get a summary of loaded plugins."""
        lines = ["Plugin System Summary", "=" * 60]

        total = len(self.plugins)
        lines.append(f"Total Plugins Loaded: {total}")
        lines.append("")

        for plugin_type, plugins in self.plugin_types.items():
            if plugins:
                lines.append(f"{plugin_type.replace('_', ' ').title()}: {len(plugins)}")
                for plugin in plugins:
                    lines.append(f"  - {plugin.metadata.name} v{plugin.metadata.version}")

        return "\n".join(lines)


# Global plugin manager
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get or create global plugin manager."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def register_plugin_hook(plugin_type: str) -> Callable[[Type[Plugin]], Type[Plugin]]:
    """
    Decorator to automatically register plugins.

    Example:
        @register_plugin_hook("task_processor")
        class MyProcessor(TaskProcessorPlugin):
            pass
    """

    def decorator(cls: Type[Plugin]) -> Type[Plugin]:
        manager = get_plugin_manager()
        plugin_id = f"auto.{cls.__name__}"

        try:
            plugin = cls()
            plugin.initialize()
            manager.plugins[plugin_id] = plugin

            # Categorize
            if isinstance(plugin, TaskProcessorPlugin):
                manager.plugin_types["task_processor"].append(plugin)
            if isinstance(plugin, ReportFormatterPlugin):
                manager.plugin_types["report_formatter"].append(plugin)
            if isinstance(plugin, NotificationPlugin):
                manager.plugin_types["notification"].append(plugin)
            if isinstance(plugin, LLMProviderPlugin):
                manager.plugin_types["llm_provider"].append(plugin)

            logger.info("Auto-registered plugin: %s", plugin.metadata.name)

        except Exception as e:
            logger.error("Failed to auto-register plugin %s: %s", cls.__name__, e)

        return cls

    return decorator
