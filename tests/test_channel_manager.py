"""Tests for channel manager behavior."""

import json

from src.channel_manager import ChannelManager


def test_get_channels_for_member_respects_include_shared(tmp_path):
    """Shared channels should only be included when include_shared=True."""
    config_path = tmp_path / "team_channels.json"
    config_path.write_text(
        json.dumps(
            {
                "team_members": {
                    "Alice": {
                        "client_channels": [{"channel": "client-a", "priority": "high"}],
                        "always_check": [],
                    }
                },
                "shared_channels": {
                    "channels": {
                        "shared-a": ["Alice"],
                    }
                },
                "channel_categories": {},
                "thread_patterns": {
                    "completion_indicators": ["done"],
                    "blocker_indicators": ["blocked"],
                    "question_indicators": ["?"],
                    "urgent_indicators": ["asap"],
                },
            }
        ),
        encoding="utf-8",
    )

    manager = ChannelManager(str(config_path))

    with_shared = [c.channel for c in manager.get_channels_for_member("Alice", include_shared=True, include_always_check=False)]
    without_shared = [
        c.channel for c in manager.get_channels_for_member("Alice", include_shared=False, include_always_check=False)
    ]

    assert "client-a" in with_shared
    assert "client-a" in without_shared
    assert "shared-a" in with_shared
    assert "shared-a" not in without_shared
