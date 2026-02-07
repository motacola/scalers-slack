#!/usr/bin/env python3
"""
Initialize Task Memory with data from today's session.

This script populates the task memory with:
- Team member configurations
- Completed tasks discovered from Slack threads
- Today's standup entries
- Known task states

Run this to bootstrap the task memory system.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.task_memory import TaskMemory, TaskStatus, TaskSource, setup_default_team


def init_task_memory():
    """Initialize task memory with today's findings."""

    print("🧠 Initializing Task Memory System...")
    print("=" * 50)

    # Create memory instance
    memory = TaskMemory()

    # Set up team members with their channel mappings
    print("\n📋 Setting up team members...")
    setup_default_team(memory)

    # Record completed tasks discovered from Slack threads
    print("\n✅ Recording completed tasks...")

    # Captain Clean Location Pages - confirmed complete by Emily A
    memory.mark_task_complete(
        task_name="Captain Clean Location Pages",
        assignee="Italo Germando",
        confirmed_by="Emily A",
        source=TaskSource.SLACK_THREAD.value,
        channel="ss-captain-clean-website-edits",
        notes="Emily confirmed 'you're all done' on Feb 5, 2026. Location pages: La Connor, Camano Island, Stanwood, Sedro Wooley, Bow"
    )
    print("  ✓ Captain Clean Location Pages (Italo) - Complete")

    # Captain Clean Service Area page
    memory.mark_task_complete(
        task_name="Captain Clean Service Area Page",
        assignee="Italo Germando",
        confirmed_by="Emily A",
        source=TaskSource.SLACK_THREAD.value,
        channel="ss-captain-clean-website-edits",
        notes="Italo said 'Done!' on Feb 4, live with backup"
    )
    print("  ✓ Captain Clean Service Area Page (Italo) - Complete")

    # Unified Designs - user confirmed
    memory.mark_task_complete(
        task_name="Unified Designs",
        assignee="Italo Germando",
        confirmed_by="Christopher Belgrave",
        source=TaskSource.USER_CONFIRMATION.value,
        notes="User said: 'Unified is done, we had the design call with the client yesterday'"
    )
    print("  ✓ Unified Designs (Italo) - Complete")

    # EDS Services subdomain published
    memory.mark_task_complete(
        task_name="EDS Pumps Services Site Publish",
        assignee="Italo Germando",
        confirmed_by="Emily A",
        source=TaskSource.SLACK_THREAD.value,
        channel="ss-eds-pumps-website-management",
        notes="Published at https://services.edspumps.com/ on Feb 4, 2026"
    )
    print("  ✓ EDS Pumps Services Site Publish (Italo) - Complete")

    # Record today's standups
    print("\n📝 Recording today's standups (Feb 6, 2026)...")

    # Italo's standup
    memory.record_standup(
        team_member="Italo Germando",
        tasks=[
            "EDS build",
            "Awful nice guys - promo",
            "AAA Electrical edits"
        ],
        date="2026-02-06",
        timestamp="2026-02-06T09:14:00"
    )
    print("  ✓ Italo Germando standup recorded")

    # Francisco's standup
    memory.record_standup(
        team_member="Francisco Oliveira",
        tasks=[
            "My Calgary build - finish up",
            "Spence and Daves build",
            "Parker and Co",
            "Ark Home website checks"
        ],
        date="2026-02-06",
        timestamp="2026-02-06T09:44:00"
    )
    print("  ✓ Francisco Oliveira standup recorded")

    # Christopher's standup
    memory.record_standup(
        team_member="Christopher Belgrave",
        tasks=[
            "Performance of Maine",
            "Lake Country",
            "EDS"
        ],
        date="2026-02-06",
        timestamp="2026-02-06T10:46:00"
    )
    print("  ✓ Christopher Belgrave standup recorded")

    # Add pending tasks from Notion
    print("\n📌 Recording pending Notion tasks...")

    # Italo's pending tasks
    memory.add_task(
        task_name="EDS Build",
        assignee="Italo Germando",
        status=TaskStatus.IN_PROGRESS.value,
        source=TaskSource.NOTION.value,
        priority="high",
        notes="Main site build - design/content to share by end of week"
    )

    memory.add_task(
        task_name="Awful Nice Guys Promo",
        assignee="Italo Germando",
        status=TaskStatus.PENDING.value,
        source=TaskSource.SLACK_STANDUP.value,
        due_date="2026-02-06"
    )

    memory.add_task(
        task_name="AAA Electrical Edits",
        assignee="Italo Germando",
        status=TaskStatus.PENDING.value,
        source=TaskSource.SLACK_STANDUP.value,
        due_date="2026-02-06"
    )

    # Francisco's pending tasks
    for task in ["My Calgary Build", "Spence and Daves Build", "Parker and Co", "Ark Home Website Checks"]:
        memory.add_task(
            task_name=task,
            assignee="Francisco Oliveira",
            status=TaskStatus.PENDING.value,
            source=TaskSource.SLACK_STANDUP.value,
            due_date="2026-02-06"
        )

    # From Notion for Francisco
    for task in ["RH Coatings", "Buzz Electrical SEO", "Buzz Electrical LSA"]:
        memory.add_task(
            task_name=task,
            assignee="Francisco Oliveira",
            status=TaskStatus.PENDING.value,
            source=TaskSource.NOTION.value,
            due_date="2026-02-06"
        )

    # Christopher's pending tasks
    memory.add_task(
        task_name="Performance of Maine",
        assignee="Christopher Belgrave",
        status=TaskStatus.PENDING.value,
        source=TaskSource.SLACK_STANDUP.value,
        due_date="2026-02-06"
    )

    memory.add_task(
        task_name="Lake County Mechanical",
        assignee="Christopher Belgrave",
        status=TaskStatus.PENDING.value,
        source=TaskSource.NOTION.value,
        due_date="2026-02-06",
        priority="high"
    )

    memory.add_task(
        task_name="EDS Content Docs",
        assignee="Christopher Belgrave",
        status=TaskStatus.IN_PROGRESS.value,
        source=TaskSource.NOTION.value,
        priority="high",
        notes="LP edit done yesterday, more content work expected"
    )

    memory.add_task(
        task_name="Trips Change Insurance",
        assignee="Christopher Belgrave",
        status=TaskStatus.PENDING.value,
        source=TaskSource.NOTION.value,
        due_date="2026-02-06",
        priority="high"
    )

    memory.add_task(
        task_name="Content Needed",
        assignee="Christopher Belgrave",
        status=TaskStatus.PENDING.value,
        source=TaskSource.NOTION.value,
        due_date="2026-02-06",
        priority="high"
    )

    print(f"  ✓ Added pending tasks")

    # Create daily snapshot
    print("\n📸 Creating daily snapshot...")
    snapshot = memory.create_daily_snapshot("2026-02-06")
    print(f"  ✓ Snapshot created with {snapshot['summary']['total_tasks_due']} tasks due")

    # Print summary
    print("\n" + "=" * 50)
    print("✨ Task Memory Initialization Complete!")
    print("=" * 50)

    stats = memory.get_stats()
    print(f"\n📊 Memory Stats:")
    print(f"  • Total tasks tracked: {stats['total_tasks']}")
    print(f"  • Completed tasks: {stats['total_completions']}")
    print(f"  • Team members: {stats['team_members']}")
    print(f"  • Standup days recorded: {stats['standup_days']}")

    print(f"\n💾 Memory saved to: {memory.memory_path}")

    return memory


if __name__ == "__main__":
    memory = init_task_memory()

    # Demo: Get tasks for each team member
    print("\n" + "=" * 50)
    print("📋 Quick Demo - Team Member Tasks")
    print("=" * 50)

    for name in ["Italo Germando", "Francisco Oliveira", "Christopher Belgrave"]:
        print(f"\n👤 {name}:")

        # Get incomplete tasks
        tasks = memory.get_tasks_by_assignee(name)
        incomplete = [t for t in tasks if t.status != TaskStatus.COMPLETE.value]
        complete = [t for t in tasks if t.status == TaskStatus.COMPLETE.value]

        print(f"   Incomplete: {len(incomplete)}")
        for t in incomplete[:3]:
            print(f"     • {t.task_name}")

        print(f"   Completed: {len(complete)}")
        for t in complete[:3]:
            print(f"     ✓ {t.task_name}")
