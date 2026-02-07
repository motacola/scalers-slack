#!/usr/bin/env python3
"""
Test script to verify TaskMemory, ChannelManager, and DailyAggregator integration.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (
    TaskMemory,
    ChannelManager,
    DailyAggregator,
    get_task_memory,
    get_channel_manager,
    get_aggregator,
)


def test_task_memory():
    """Test TaskMemory functionality."""
    print("\n" + "=" * 60)
    print("📋 Testing TaskMemory")
    print("=" * 60)

    memory = get_task_memory()

    # Get summary
    summary = memory.get_summary()
    print(f"\n✅ TaskMemory loaded successfully!")
    print(f"   • Tasks tracked: {summary['total_tasks']}")
    print(f"   • Completed: {summary['completed_tasks']}")
    print(f"   • Team members: {summary['team_members']}")
    print(f"   • Standups recorded: {summary['standups_recorded']}")

    # Get tasks for a team member
    for member in ["Italo Germando", "Francisco Oliveira", "Christopher Belgrave"]:
        tasks = memory.get_tasks_by_assignee(member)
        print(f"\n   📌 {member}: {len(tasks)} tasks")

    return True


def test_channel_manager():
    """Test ChannelManager functionality."""
    print("\n" + "=" * 60)
    print("📺 Testing ChannelManager")
    print("=" * 60)

    manager = get_channel_manager()

    # Get summary
    summary = manager.get_summary()
    print(f"\n✅ ChannelManager loaded successfully!")
    print(f"   • Team members: {summary['team_members']}")
    print(f"   • Total channels: {summary['total_channels']}")
    print(f"   • Categories: {', '.join(summary['categories'])}")

    # Get channels for each member
    for member in manager.get_team_members():
        channels = manager.get_channels_for_member(member)
        high_priority = [ch for ch in channels if ch.priority == "high"]
        print(f"\n   📌 {member}:")
        print(f"      Total channels: {len(channels)}")
        print(f"      High priority: {len(high_priority)}")

    # Test pattern detection
    print("\n   🔍 Pattern Detection Tests:")
    test_messages = [
        ("Done! All pages published.", "completion"),
        ("Blocked waiting on client content", "blocker"),
        ("Is this the right approach?", "question"),
        ("Need this ASAP", "urgent")
    ]

    for msg, expected in test_messages:
        types = manager.detect_message_type(msg)
        status = "✓" if expected in types else "✗"
        print(f"      {status} '{msg[:30]}...' -> {types}")

    return True


def test_daily_aggregator():
    """Test DailyAggregator functionality."""
    print("\n" + "=" * 60)
    print("📊 Testing DailyAggregator")
    print("=" * 60)

    aggregator = get_aggregator()

    print("\n✅ DailyAggregator initialized!")

    # Test for each team member
    for name in ["Italo Germando", "Francisco Oliveira", "Christopher Belgrave"]:
        print(f"\n--- {name} ---")

        # Get priority tasks
        priorities = aggregator.get_priority_tasks(name, limit=3)
        print(f"   Top priorities: {len(priorities)}")
        for p in priorities:
            print(f"      • {p['name'][:40]}... ({p['reason']})")

        # What should they check?
        actions = aggregator.what_should_i_check(name)
        print(f"   Quick actions: {len(actions)}")
        for action in actions[:3]:
            print(f"      • {action}")

    return True


def test_formatted_reports():
    """Test formatted report generation."""
    print("\n" + "=" * 60)
    print("📄 Testing Formatted Reports")
    print("=" * 60)

    aggregator = get_aggregator()

    # Generate a daily report for one member
    print("\n📋 Sample Daily Report (Christopher Belgrave):")
    print("-" * 60)
    report = aggregator.format_daily_report("Christopher Belgrave")
    # Print first 30 lines
    lines = report.split('\n')
    for line in lines[:25]:
        print(line)
    if len(lines) > 25:
        print(f"   ... ({len(lines) - 25} more lines)")

    return True


def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("🚀 SCALERS SLACK AUTOMATION - INTEGRATION TEST")
    print("=" * 60)

    tests = [
        ("TaskMemory", test_task_memory),
        ("ChannelManager", test_channel_manager),
        ("DailyAggregator", test_daily_aggregator),
        ("Formatted Reports", test_formatted_reports),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")

    print(f"\n   Total: {passed}/{total} tests passed")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
