# Scalers Slack Automation

Automation utilities for extracting Slack threads, recording audit trails, and syncing audit notes into Notion.
Inspired by the structure of https://github.com/motacola/Auto-Bugherd, adapted for Slack + Notion workflows.

## Features
- Config-driven Slack channel + Notion page settings.
- Slack thread search + extraction scaffolding for future automations.
- SQLite-backed audit logging with JSONL fallback.
- Post-write verification for Notion audit notes and Slack Last Synced updates.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your API tokens:
```bash
export SLACK_BOT_TOKEN='xoxb-...'
export NOTION_API_KEY='secret_...'
```

## Usage
Run a sync for a configured project:
```bash
python3 -m src.engine --project scalers-slack --since 2024-01-01T00:00:00Z
```

Search for threads by query:
```bash
python3 -m src.engine --project scalers-slack --query "customer escalation" --since 2024-01-01T00:00:00Z
```

Dry run (no external writes):
```bash
python3 -m src.engine --project scalers-slack --since 2024-01-01T00:00:00Z --dry-run
```

## Audit Storage
Audit logs are written to `audit/audit.db` by default. If SQLite is unavailable or locked, the logger
falls back to `audit/audit.jsonl` so you always have a record of what ran and what changed.

## Configuration
Edit `config.json` to set channels and Notion pages. The `audit` settings control storage paths.
Use `settings.slack.pagination` for defaults and `projects[].slack_pagination` to cap page counts per channel.

## Notes
- The Slack and Notion APIs require their respective permissions.
- The project intentionally keeps the thread extraction logic modular so you can plug in custom
  routing rules or ticket creation later.
