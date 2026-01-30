"""Configuration management for daily task reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class OutputConfig:
    """Output configuration."""

    directory: str = "output"
    formats: list[str] = field(default_factory=lambda: ["csv", "json", "markdown", "html"])
    default_format: str = "all"
    group_by: str = "owner"


@dataclass
class FilteringConfig:
    """Filtering configuration."""

    actionable_only: bool = False
    include_mentions_search: bool = True
    min_text_length: int = 20
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class CacheConfig:
    """Cache configuration."""

    enabled: bool = True
    directory: str = ".cache"
    ttl_seconds: int = 3600


@dataclass
class BrowserAutomationConfig:
    """Browser automation configuration."""

    enabled: bool = True
    headless: bool = False
    slow_mo_ms: int = 0
    timeout_ms: int = 30000
    max_retries: int = 3
    retry_delay_ms: int = 1000
    storage_state_path: str = "browser_storage_state.json"
    slack_workspace_id: str = ""
    slack_client_url: str = "https://app.slack.com/client"
    slack_api_base_url: str = "https://slack.com/api"


@dataclass
class HistoricalTrackingConfig:
    """Historical tracking configuration."""

    enabled: bool = True
    snapshots_directory: str = "output/snapshots"
    compare_with_previous: bool = True


@dataclass
class NotionConfig:
    """Notion integration configuration."""

    enabled: bool = False
    sync_tasks: bool = False
    database_id: str = ""
    base_url: str = "https://www.notion.so"


@dataclass
class DailyReportConfig:
    """Complete daily report configuration."""

    channels: list[str] = field(default_factory=list)
    project_channels: list[str] = field(default_factory=list)
    team_members: list[str] = field(default_factory=list)
    output: OutputConfig = field(default_factory=OutputConfig)
    filtering: FilteringConfig = field(default_factory=FilteringConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    browser_automation: BrowserAutomationConfig = field(default_factory=BrowserAutomationConfig)
    historical_tracking: HistoricalTrackingConfig = field(default_factory=HistoricalTrackingConfig)
    notion: NotionConfig = field(default_factory=NotionConfig)


class ConfigManager:
    """Manage configuration loading and access."""

    DEFAULT_CONFIG_PATH = "config/daily_report_defaults.json"

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: DailyReportConfig | None = None

    def load(self) -> DailyReportConfig:
        """Load configuration from file."""
        if self._config is not None:
            return self._config

        path = Path(self.config_path)
        if not path.exists():
            # Return default configuration
            self._config = DailyReportConfig()
            return self._config

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._config = self._parse_config(data)
            return self._config
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            self._config = DailyReportConfig()
            return self._config

    def _parse_config(self, data: dict[str, Any]) -> DailyReportConfig:
        """Parse configuration dictionary into dataclasses."""
        return DailyReportConfig(
            channels=data.get("channels", []),
            project_channels=data.get("project_channels", []),
            team_members=data.get("team_members", []),
            output=OutputConfig(**data.get("output", {})),
            filtering=FilteringConfig(**data.get("filtering", {})),
            cache=CacheConfig(**data.get("cache", {})),
            browser_automation=BrowserAutomationConfig(**data.get("browser_automation", {})),
            historical_tracking=HistoricalTrackingConfig(**data.get("historical_tracking", {})),
            notion=NotionConfig(**data.get("notion", {})),
        )

    def save(self, config: DailyReportConfig | None = None) -> None:
        """Save configuration to file."""
        if config is None:
            config = self._config or DailyReportConfig()

        path = Path(self.config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "channels": config.channels,
            "project_channels": config.project_channels,
            "team_members": config.team_members,
            "output": {
                "directory": config.output.directory,
                "formats": config.output.formats,
                "default_format": config.output.default_format,
                "group_by": config.output.group_by,
            },
            "filtering": {
                "actionable_only": config.filtering.actionable_only,
                "include_mentions_search": config.filtering.include_mentions_search,
                "min_text_length": config.filtering.min_text_length,
                "exclude_patterns": config.filtering.exclude_patterns,
            },
            "cache": {
                "enabled": config.cache.enabled,
                "directory": config.cache.directory,
                "ttl_seconds": config.cache.ttl_seconds,
            },
            "browser_automation": {
                "enabled": config.browser_automation.enabled,
                "headless": config.browser_automation.headless,
                "slow_mo_ms": config.browser_automation.slow_mo_ms,
                "timeout_ms": config.browser_automation.timeout_ms,
                "max_retries": config.browser_automation.max_retries,
                "retry_delay_ms": config.browser_automation.retry_delay_ms,
                "storage_state_path": config.browser_automation.storage_state_path,
                "slack_workspace_id": config.browser_automation.slack_workspace_id,
                "slack_client_url": config.browser_automation.slack_client_url,
                "slack_api_base_url": config.browser_automation.slack_api_base_url,
            },
            "historical_tracking": {
                "enabled": config.historical_tracking.enabled,
                "snapshots_directory": config.historical_tracking.snapshots_directory,
                "compare_with_previous": config.historical_tracking.compare_with_previous,
            },
            "notion": {
                "enabled": config.notion.enabled,
                "sync_tasks": config.notion.sync_tasks,
                "database_id": config.notion.database_id,
                "base_url": config.notion.base_url,
            },
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_all_channels(self) -> list[str]:
        """Get all channels (regular + project)."""
        config = self.load()
        return config.channels + config.project_channels

    def merge_with_args(self, args: Any) -> DailyReportConfig:
        """Merge configuration with command-line arguments."""
        config = self.load()

        # Override with command-line args if provided
        if hasattr(args, "channels") and args.channels:
            config.channels = args.channels.split(",")
        if hasattr(args, "project_channels") and args.project_channels:
            config.project_channels = args.project_channels.split(",")
        if hasattr(args, "team_members") and args.team_members:
            config.team_members = args.team_members.split(",")
        if hasattr(args, "actionable_only") and args.actionable_only:
            config.filtering.actionable_only = True
        if hasattr(args, "include_mentions_search") and args.include_mentions_search:
            config.filtering.include_mentions_search = True
        if hasattr(args, "format") and args.format:
            config.output.default_format = args.format
        if hasattr(args, "group_by") and args.group_by:
            config.output.group_by = args.group_by
        if hasattr(args, "no_cache") and args.no_cache:
            config.cache.enabled = False

        return config


def get_default_config() -> DailyReportConfig:
    """Get default configuration."""
    return DailyReportConfig(
        channels=[
            "ss-website-pod",
            "ss-website-tickets",
            "standup",
        ],
        project_channels=[
            "ss-magnify-website-management-and-hosting-wp",
            "ss-eds-pumps-website-management",
            "ss-seaside-toolbox-website",
        ],
        team_members=[
            "Christopher Belgrave",
            "Francisco",
            "Italo Germando",
            "Lisa Appleby",
            "Craig Noonan",
        ],
        filtering=FilteringConfig(
            exclude_patterns=[
                r"^\s*thank",
                r"^\s*thx",
                r"^\s*ok\s*$",
                r"^\s*okay\s*$",
                r"^\s*brb",
                r"^\s*got it",
                r"^\s*done\s*$",
                r"^\s*lol",
                r"^\s*haha",
            ]
        ),
    )