"""Scalers Slack automation package."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

# Export TaskMemory for easy access
from .task_memory import (
    TaskMemory,
    TaskRecord,
    TeamMember,
    StandupEntry,
    TaskStatus,
    TaskSource,
    get_task_memory,
    setup_default_team,
)

# Export ChannelManager for channel lookups
from .channel_manager import (
    ChannelManager,
    ChannelInfo,
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
