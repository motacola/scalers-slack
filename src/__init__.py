"""Scalers Slack automation package."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

# Export TaskMemory for easy access
# Export ChannelManager for channel lookups
from .channel_manager import (
    ChannelInfo,
    ChannelManager,
    ChecklistItem,
    get_channel_manager,
    quick_channel_lookup,
)

# Export DailyAggregator for unified task views
from .daily_aggregator import (
    DailyAggregator,
    get_aggregator,
    quick_status,
    team_status,
)
from .task_memory import (
    StandupEntry,
    TaskMemory,
    TaskRecord,
    TaskSource,
    TaskStatus,
    TeamMember,
    get_task_memory,
    setup_default_team,
)

__all__ = [
    "ChannelInfo",
    "ChannelManager",
    "ChecklistItem",
    "DailyAggregator",
    "StandupEntry",
    "TaskMemory",
    "TaskRecord",
    "TaskSource",
    "TaskStatus",
    "TeamMember",
    "get_aggregator",
    "get_channel_manager",
    "get_task_memory",
    "quick_channel_lookup",
    "quick_status",
    "setup_default_team",
    "team_status",
]
