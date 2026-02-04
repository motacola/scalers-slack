# Plugin System Guide

The Scalers Slack automation includes a comprehensive plugin system for extending functionality without modifying core code.

## Overview

The plugin system supports four types of plugins:

1. **Task Processors** - Custom task detection and processing logic
2. **Report Formatters** - New output formats (PDF, Slack blocks, etc.)
3. **Notification Channels** - Email, SMS, webhooks, etc.
4. **LLM Providers** - Additional AI providers beyond OpenAI/Anthropic/Ollama

## Quick Start

### 1. Create a Plugin

Create a new Python file in the `plugins/` directory:

```python
# plugins/my_plugin.py
from src.plugin_system import ReportFormatterPlugin, PluginMetadata
from typing import Any

class MyFormatter(ReportFormatterPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="My Custom Formatter",
            version="1.0.0",
            description="Formats reports in my custom way",
            author="Your Name"
        )

    def get_format_name(self) -> str:
        return "myformat"

    def format_report(self, data: dict[str, Any], output_path: str | None = None) -> str:
        # Your formatting logic here
        return "formatted output"
```

### 2. Load Plugins

```python
from src.plugin_system import get_plugin_manager

# Load all plugins from plugins/ directory
manager = get_plugin_manager()
manager.load_all_plugins("plugins")

# Get summary
print(manager.get_summary())
```

### 3. Use Plugins

```python
# Get a specific formatter
formatter = manager.get_report_formatter("myformat")
if formatter:
    result = formatter.format_report({"tasks": tasks})
```

## Plugin Types

### Task Processor Plugins

Process and modify tasks during collection.

```python
from src.plugin_system import TaskProcessorPlugin, PluginMetadata
from typing import Any

class MyProcessor(TaskProcessorPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="My Task Processor",
            version="1.0.0",
            description="Custom task processing"
        )

    def should_process(self, task: Any) -> bool:
        """Return True if this plugin should process the task."""
        return task.get("type") == "urgent"

    def process_task(self, task: Any) -> Any:
        """Modify and return the task."""
        task["processed"] = True
        return task
```

**Use Cases:**
- Auto-tag tasks based on keywords
- Boost priority for certain patterns
- Extract and categorize mentions
- Add custom metadata
- Filter spam/noise

### Report Formatter Plugins

Generate reports in custom formats.

```python
from src.plugin_system import ReportFormatterPlugin, PluginMetadata
from typing import Any

class PDFFormatter(ReportFormatterPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="PDF Report Formatter",
            version="1.0.0",
            description="Generates PDF reports",
            dependencies=["reportlab"]
        )

    def get_format_name(self) -> str:
        return "pdf"

    def get_file_extension(self) -> str:
        return ".pdf"

    def format_report(self, data: dict[str, Any], output_path: str | None = None) -> str:
        # Generate PDF using reportlab
        from reportlab.pdfgen import canvas

        if not output_path:
            output_path = "report.pdf"

        c = canvas.Canvas(output_path)
        c.drawString(100, 750, "Task Report")
        # ... add content
        c.save()

        return output_path
```

**Use Cases:**
- PDF reports
- Slack Block Kit JSON
- Excel/CSV exports
- Custom dashboards
- Email templates

### Notification Plugins

Send notifications via custom channels.

```python
from src.plugin_system import NotificationPlugin, PluginMetadata
from typing import Any

class WebhookNotifier(NotificationPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Webhook Notifier",
            version="1.0.0",
            description="Sends notifications via HTTP webhooks"
        )

    def get_channel_name(self) -> str:
        return "webhook"

    def send_notification(self, message: str, metadata: dict[str, Any] | None = None) -> bool:
        import requests

        webhook_url = metadata.get("webhook_url") if metadata else None
        if not webhook_url:
            return False

        response = requests.post(webhook_url, json={"text": message})
        return response.status_code == 200
```

**Use Cases:**
- Email notifications
- SMS via Twilio
- Discord/Slack webhooks
- PagerDuty/OpsGenie alerts
- Custom HTTP webhooks
- Push notifications

### LLM Provider Plugins

Add support for additional AI providers.

```python
from src.plugin_system import LLMProviderPlugin, PluginMetadata

class GeminiProvider(LLMProviderPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Google Gemini Provider",
            version="1.0.0",
            description="Google Gemini LLM integration",
            dependencies=["google-generativeai"]
        )

    def get_provider_name(self) -> str:
        return "gemini"

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        import google.generativeai as genai

        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text
```

**Use Cases:**
- Google Gemini
- Cohere
- Hugging Face models
- Custom self-hosted models
- Specialized domain models

## Advanced Features

### Auto-Registration Decorator

Use the decorator for automatic plugin registration:

```python
from src.plugin_system import register_plugin_hook, TaskProcessorPlugin

@register_plugin_hook("task_processor")
class AutoRegisteredProcessor(TaskProcessorPlugin):
    # Plugin automatically loads when module imports
    pass
```

### Plugin Dependencies

Specify dependencies in metadata:

```python
def get_metadata(self) -> PluginMetadata:
    return PluginMetadata(
        name="My Plugin",
        version="1.0.0",
        description="Requires external packages",
        dependencies=["reportlab", "pillow", "requests"]
    )
```

### Plugin Lifecycle

Plugins have initialization and cleanup hooks:

```python
class MyPlugin(Plugin):
    def initialize(self) -> None:
        """Called when plugin is loaded."""
        super().initialize()
        # Set up resources, connections, etc.
        self.connection = setup_connection()

    def cleanup(self) -> None:
        """Called when plugin is unloaded."""
        # Clean up resources
        self.connection.close()
        super().cleanup()
```

### Plugin Discovery

Plugins are auto-discovered from the `plugins/` directory:

```python
manager = get_plugin_manager()

# Discover plugins (returns module names)
discovered = manager.discover_plugins("plugins")

# Load all discovered plugins
count = manager.load_all_plugins("plugins")
print(f"Loaded {count} plugins")
```

### Plugin Management

```python
manager = get_plugin_manager()

# Get specific plugin
plugin = manager.get_plugin("plugins.my_plugin.MyFormatter")

# Get plugins by type
formatters = manager.get_plugins_by_type("report_formatter")
processors = manager.get_plugins_by_type("task_processor")

# Unload plugin
manager.unload_plugin("plugins.my_plugin.MyFormatter")

# Unload all
manager.unload_all_plugins()
```

## Example Plugins

### 1. Priority Booster

Automatically increases priority for urgent keywords:

```bash
# plugins/example_priority_processor.py
```

**Features:**
- Detects urgent keywords (urgent, asap, critical, etc.)
- Auto-boosts priority to "critical"
- Adds `auto_boosted` flag

### 2. Slack Block Formatter

Formats reports as Slack Block Kit JSON:

```bash
# plugins/example_slack_formatter.py
```

**Features:**
- Rich Slack message formatting
- Header, dividers, sections
- Emoji support
- Task list with priorities

### 3. Email Notifier

Sends notifications via email:

```bash
# plugins/example_email_notifier.py
```

**Features:**
- SMTP email sending
- HTML/plain text support
- Attachment support (extensible)

## Best Practices

### 1. Error Handling

Always handle errors gracefully:

```python
def process_task(self, task: Any) -> Any:
    try:
        # Processing logic
        return modified_task
    except Exception as e:
        logger.error("Plugin error: %s", e)
        return task  # Return original on error
```

### 2. Logging

Use proper logging instead of print:

```python
import logging

logger = logging.getLogger(__name__)

class MyPlugin(Plugin):
    def process_task(self, task: Any) -> Any:
        logger.info("Processing task: %s", task.get("id"))
        logger.debug("Task details: %s", task)
        return task
```

### 3. Configuration

Use environment variables or config files:

```python
import os

class MyPlugin(Plugin):
    def initialize(self) -> None:
        super().initialize()
        self.api_key = os.getenv("MY_PLUGIN_API_KEY")
        if not self.api_key:
            logger.warning("MY_PLUGIN_API_KEY not set")
```

### 4. Testing

Create tests for your plugins:

```python
# tests/test_my_plugin.py
from plugins.my_plugin import MyFormatter

def test_my_formatter():
    formatter = MyFormatter()
    result = formatter.format_report({"tasks": []})
    assert result is not None
```

### 5. Documentation

Document your plugin in the module docstring:

```python
"""
My Custom Plugin

Description: Detailed description of what this plugin does

Configuration:
- MY_PLUGIN_API_KEY: API key for service (required)
- MY_PLUGIN_TIMEOUT: Timeout in seconds (optional, default: 30)

Usage:
    formatter = MyFormatter()
    result = formatter.format_report(data)
"""
```

## Integration with Core

### Using Plugins in Scripts

```python
#!/usr/bin/env python3
from src.plugin_system import get_plugin_manager

# Load plugins
manager = get_plugin_manager()
manager.load_all_plugins()

# Process tasks with plugins
task_processors = manager.get_plugins_by_type("task_processor")
for processor in task_processors:
    if processor.should_process(task):
        task = processor.process_task(task)

# Format with plugin
formatter = manager.get_report_formatter("slack")
if formatter:
    result = formatter.format_report(data)

# Send notification
notifier = manager.get_notification_channel("email")
if notifier:
    notifier.send_notification("Task completed!", {"recipient": "admin@example.com"})
```

## Troubleshooting

### Plugin Not Loading

1. Check plugin file is in `plugins/` directory
2. Ensure it inherits from correct base class
3. Check for syntax errors: `python -m py_compile plugins/my_plugin.py`
4. Enable debug logging: `logging.getLogger().setLevel(logging.DEBUG)`

### Dependencies Missing

Install plugin dependencies:

```bash
pip install -r plugins/requirements.txt
```

Or install specific dependencies:

```bash
pip install reportlab pillow twilio
```

### Plugin Errors

Check logs for detailed error messages:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing Plugins

To share your plugin:

1. Create plugin file in `plugins/`
2. Add tests in `tests/test_plugins/`
3. Document in plugin docstring
4. Add dependencies to `plugins/requirements.txt`
5. Submit PR with example usage

## Resources

- Base Plugin Classes: `src/plugin_system.py`
- Example Plugins: `plugins/example_*.py`
- Tests: `tests/test_plugin_system.py`
- Plugin Manager: `src.plugin_system.get_plugin_manager()`

## Support

For questions or issues:
- Check example plugins in `plugins/`
- Review tests in `tests/test_plugin_system.py`
- Open an issue on GitHub
