"""
ChannelManager - Centralized channel lookup and management for team task tracking.

This module provides efficient channel lookups based on:
- Team member assignments
- Client projects
- Priority levels
- Thread pattern detection

Usage:
    from src.channel_manager import ChannelManager

    manager = ChannelManager()

    # Get channels for a team member
    channels = manager.get_channels_for_member("Italo Germando")

    # Get priority channels to check first
    priority_channels = manager.get_priority_channels("Christopher Belgrave")

    # Find which team member owns a channel
    owner = manager.get_channel_owner("ss-captain-clean-website-edits")

    # Check if a message indicates task completion
    if manager.is_completion_message("Done! @Emily A"):
        print("Task completed!")
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, cast

from .config_validation import validate_team_channels_config

logger = logging.getLogger(__name__)


@dataclass
class ChannelInfo:
    """Information about a Slack channel."""

    channel: str
    client: Optional[str] = None
    priority: str = "medium"
    notes: Optional[str] = None
    team_members: Optional[List[str]] = None


@dataclass
class ChecklistItem:
    """A channel to check with context."""

    channel: str
    reason: str
    priority: str
    client: Optional[str] = None


class ChannelManager:
    """
    Manages team-channel mappings and provides efficient lookups.

    This class loads configuration from config/team_channels.json and provides
    methods for:
    - Finding channels for team members
    - Determining channel priorities
    - Detecting completion/blocker patterns in messages
    - Generating daily check lists
    """

    DEFAULT_CONFIG_PATH = "config/team_channels.json"

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize ChannelManager.

        Args:
            config_path: Path to team_channels.json. Defaults to config/team_channels.json
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config: Dict[str, Any] = {}
        self._channel_to_members: Dict[str, List[str]] = {}
        self._member_channels_cache: Dict[str, List[ChannelInfo]] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from disk."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config not found at {self.config_path}. Using defaults.")
            self.config = self._get_default_config()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            validation_errors = validate_team_channels_config(self.config)
            if validation_errors:
                error_text = "; ".join(validation_errors[:5])
                if len(validation_errors) > 5:
                    error_text += f" (and {len(validation_errors) - 5} more)"
                raise ValueError(f"Invalid team channel config: {error_text}")
            self._build_indexes()
            logger.info(f"Loaded channel config from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load channel config: {e}")
            self.config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Return minimal default configuration."""
        return {
            "version": "1.0.0",
            "channel_categories": {},
            "team_members": {},
            "shared_channels": {"channels": {}},
            "thread_patterns": {
                "completion_indicators": ["done", "complete", "finished"],
                "blocker_indicators": ["blocked", "waiting"],
                "question_indicators": ["?"],
                "urgent_indicators": ["urgent", "asap"],
            },
        }

    def _build_indexes(self) -> None:
        """Build reverse indexes for efficient lookups."""
        self._channel_to_members = {}
        self._member_channels_cache = {}

        # Build channel -> members mapping
        for member_name, member_data in self.config.get("team_members", {}).items():
            for channel_info in member_data.get("client_channels", []):
                channel = channel_info.get("channel")
                if channel:
                    if channel not in self._channel_to_members:
                        self._channel_to_members[channel] = []
                    self._channel_to_members[channel].append(member_name)

        # Add shared channels
        for channel, members in self.config.get("shared_channels", {}).get("channels", {}).items():
            if channel not in self._channel_to_members:
                self._channel_to_members[channel] = []
            for member in members:
                if member not in self._channel_to_members[channel]:
                    self._channel_to_members[channel].append(member)

    # ==================== Team Member Lookups ====================

    def get_team_members(self) -> List[str]:
        """Get list of all team member names."""
        return list(self.config.get("team_members", {}).keys())

    def get_member_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get full configuration for a team member."""
        team_members = self.config.get("team_members", {})
        if not isinstance(team_members, dict):
            return None
        value = team_members.get(name)
        return cast(Optional[Dict[str, Any]], value)

    def get_channels_for_member(
        self, name: str, include_shared: bool = True, include_always_check: bool = True
    ) -> List[ChannelInfo]:
        """
        Get all channels relevant to a team member.

        Args:
            name: Team member name
            include_shared: Include shared channels like standup
            include_always_check: Include channels from always_check list

        Returns:
            List of ChannelInfo objects
        """
        member = self.get_member_config(name)
        if not member:
            return []

        channels = []
        seen = set()

        # Add client channels
        for ch in member.get("client_channels", []):
            channel_name = ch.get("channel")
            if channel_name and channel_name not in seen:
                channels.append(
                    ChannelInfo(
                        channel=channel_name,
                        client=ch.get("client"),
                        priority=ch.get("priority", "medium"),
                        notes=ch.get("notes"),
                    )
                )
                seen.add(channel_name)

        # Add always_check channels
        if include_always_check:
            for channel_name in member.get("always_check", []):
                if channel_name not in seen:
                    channels.append(ChannelInfo(channel=channel_name, priority="high", notes="Always check"))
                    seen.add(channel_name)

        # Add shared channels from shared_channels mapping
        if include_shared:
            shared_channels = self.config.get("shared_channels", {}).get("channels", {})
            for channel_name, members in shared_channels.items():
                if channel_name in seen:
                    continue
                if not isinstance(members, list) or name not in members:
                    continue
                channels.append(
                    ChannelInfo(channel=channel_name, priority="medium", notes="Shared channel", team_members=members)
                )
                seen.add(channel_name)

        return channels

    def get_priority_channels(self, name: str, priority: str = "high") -> List[ChannelInfo]:
        """
        Get channels of a specific priority for a team member.

        Args:
            name: Team member name
            priority: Priority level (high, medium, low)

        Returns:
            List of ChannelInfo objects matching the priority
        """
        all_channels = self.get_channels_for_member(name)
        return [ch for ch in all_channels if ch.priority == priority]

    def get_client_channels(self, name: str, client: str) -> List[ChannelInfo]:
        """Get channels for a specific client assigned to a team member."""
        all_channels = self.get_channels_for_member(name)
        return [ch for ch in all_channels if ch.client and client.lower() in ch.client.lower()]

    # ==================== Channel Lookups ====================

    def get_channel_owner(self, channel: str) -> List[str]:
        """Get team member(s) responsible for a channel."""
        return self._channel_to_members.get(channel, [])

    def get_channel_info(self, channel: str) -> Optional[ChannelInfo]:
        """Get information about a specific channel."""
        owners = self.get_channel_owner(channel)
        if not owners:
            return None

        # Get info from first owner's config
        for owner in owners:
            member = self.get_member_config(owner)
            if member:
                for ch in member.get("client_channels", []):
                    if ch.get("channel") == channel:
                        return ChannelInfo(
                            channel=channel,
                            client=ch.get("client"),
                            priority=ch.get("priority", "medium"),
                            notes=ch.get("notes"),
                            team_members=owners,
                        )

        return ChannelInfo(channel=channel, team_members=owners)

    def is_shared_channel(self, channel: str) -> bool:
        """Check if a channel is shared between multiple team members."""
        return len(self._channel_to_members.get(channel, [])) > 1

    # ==================== Category Lookups ====================

    def get_category_channels(self, category: str) -> List[str]:
        """Get channels in a specific category (standup, pods, tickets, etc.)."""
        cat_data = self.config.get("channel_categories", {}).get(category, {})
        channels = cat_data.get("channels", []) if isinstance(cat_data, dict) else []
        if not isinstance(channels, list):
            return []
        return [channel for channel in channels if isinstance(channel, str)]

    def get_all_categories(self) -> List[str]:
        """Get list of all channel categories."""
        return list(self.config.get("channel_categories", {}).keys())

    # ==================== Pattern Detection ====================

    def is_completion_message(self, text: str) -> bool:
        """
        Check if a message indicates task completion.

        Args:
            text: Message text to check

        Returns:
            True if message contains completion indicators
        """
        patterns = self.config.get("thread_patterns", {}).get("completion_indicators", [])
        text_lower = text.lower()
        return any(pattern.lower() in text_lower for pattern in patterns)

    def is_blocker_message(self, text: str) -> bool:
        """Check if a message indicates a blocker."""
        patterns = self.config.get("thread_patterns", {}).get("blocker_indicators", [])
        text_lower = text.lower()
        return any(pattern.lower() in text_lower for pattern in patterns)

    def is_question_message(self, text: str) -> bool:
        """Check if a message is a question."""
        patterns = self.config.get("thread_patterns", {}).get("question_indicators", [])
        return any(pattern in text for pattern in patterns)

    def is_urgent_message(self, text: str) -> bool:
        """Check if a message indicates urgency."""
        patterns = self.config.get("thread_patterns", {}).get("urgent_indicators", [])
        text_lower = text.lower()
        return any(pattern.lower() in text_lower for pattern in patterns)

    def detect_message_type(self, text: str) -> List[str]:
        """
        Detect all applicable types for a message.

        Returns:
            List of types: completion, blocker, question, urgent
        """
        types = []
        if self.is_completion_message(text):
            types.append("completion")
        if self.is_blocker_message(text):
            types.append("blocker")
        if self.is_question_message(text):
            types.append("question")
        if self.is_urgent_message(text):
            types.append("urgent")
        return types

    # ==================== Daily Checklist Generation ====================

    def generate_daily_checklist(
        self, name: str, include_priorities: Optional[List[str]] = None
    ) -> List[ChecklistItem]:
        """
        Generate an ordered checklist of channels to review.

        Args:
            name: Team member name
            include_priorities: Priority levels to include (default: all)

        Returns:
            Ordered list of ChecklistItem objects
        """
        if include_priorities is None:
            include_priorities = ["high", "medium", "low"]

        checklist = []
        seen = set()

        # 1. Always check channels first (standup, pods)
        member = self.get_member_config(name)
        if member:
            for channel in member.get("always_check", []):
                if channel not in seen:
                    checklist.append(ChecklistItem(channel=channel, reason="Daily check", priority="high"))
                    seen.add(channel)

        # 2. Ticket channels
        for channel in self.get_category_channels("tickets"):
            if channel not in seen:
                checklist.append(ChecklistItem(channel=channel, reason="Task notifications", priority="high"))
                seen.add(channel)

        # 3. Client channels by priority
        for priority in ["high", "medium", "low"]:
            if priority not in include_priorities:
                continue
            for ch_info in self.get_priority_channels(name, priority):
                if ch_info.channel not in seen:
                    checklist.append(
                        ChecklistItem(
                            channel=ch_info.channel,
                            reason=f"{ch_info.client or 'Client'} channel",
                            priority=priority,
                            client=ch_info.client,
                        )
                    )
                    seen.add(ch_info.channel)

        return checklist

    def get_quick_check_channels(self, name: str) -> List[str]:
        """
        Get minimal set of channels for a quick status check.

        Returns only standup and high-priority client channels.
        """
        channels = []

        member = self.get_member_config(name)
        if member:
            # Standup first
            if "standup" in member.get("always_check", []):
                channels.append("standup")

            # High priority clients
            for ch_info in self.get_priority_channels(name, "high"):
                channels.append(ch_info.channel)

        return channels

    # ==================== Keyword Monitoring ====================

    def get_keywords_for_member(self, name: str) -> List[str]:
        """Get keywords to watch for a team member."""
        member = self.get_member_config(name)
        if member:
            keywords = member.get("keywords_to_watch", [])
            if isinstance(keywords, list):
                return [keyword for keyword in keywords if isinstance(keyword, str)]
        return []

    def find_mentions(self, text: str, name: str) -> bool:
        """Check if text mentions a specific team member."""
        keywords = self.get_keywords_for_member(name)
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    # ==================== Utility Methods ====================

    def get_all_channels(self) -> Set[str]:
        """Get set of all known channels."""
        channels = set()

        # From team members
        for member_data in self.config.get("team_members", {}).values():
            for ch in member_data.get("client_channels", []):
                channels.add(ch.get("channel"))
            for ch in member_data.get("always_check", []):
                channels.add(ch)

        # From categories
        for cat_data in self.config.get("channel_categories", {}).values():
            for ch in cat_data.get("channels", []):
                channels.add(ch)

        # From shared
        for ch in self.config.get("shared_channels", {}).get("channels", {}).keys():
            channels.add(ch)

        return {ch for ch in channels if ch}

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of channel configuration."""
        return {
            "team_members": len(self.config.get("team_members", {})),
            "total_channels": len(self.get_all_channels()),
            "categories": self.get_all_categories(),
            "shared_channels": len(self.config.get("shared_channels", {}).get("channels", {})),
        }

    def print_member_summary(self, name: str) -> str:
        """Generate a formatted summary for a team member."""
        member = self.get_member_config(name)
        if not member:
            return f"Unknown team member: {name}"

        lines = [
            f"📋 Channel Summary for {name}",
            f"   Role: {member.get('role', 'N/A')}",
            "",
            "   🔴 High Priority Channels:",
        ]

        for ch in self.get_priority_channels(name, "high"):
            lines.append(f"      • {ch.channel} ({ch.client or 'N/A'})")

        lines.append("")
        lines.append("   🟡 Medium Priority Channels:")
        for ch in self.get_priority_channels(name, "medium"):
            lines.append(f"      • {ch.channel} ({ch.client or 'N/A'})")

        lines.append("")
        lines.append("   ✅ Always Check:")
        for ch in member.get("always_check", []):
            lines.append(f"      • {ch}")

        return "\n".join(lines)


# ==================== Convenience Functions ====================


def get_channel_manager(config_path: Optional[str] = None) -> ChannelManager:
    """Get or create a ChannelManager instance."""
    return ChannelManager(config_path)


def quick_channel_lookup(member_name: str) -> List[str]:
    """Quick lookup of channels for a team member."""
    manager = ChannelManager()
    return [ch.channel for ch in manager.get_channels_for_member(member_name)]
