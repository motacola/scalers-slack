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

Dev tools:
```bash
pip install -r requirements-dev.txt
ruff check .
mypy src
pytest
```

Optional browser automation dependencies (for running without API keys):
```bash
pip install -r requirements-browser.txt
python -m playwright install chromium
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
High-traffic channels can be tightened further (some presets are already applied in `config.json`).
Use `settings.slack.retries` / `settings.notion.retries` to adjust retry behavior and rate-limit handling.

The sync run uses a deterministic Run ID (based on project, since/query, and date) to avoid duplicate Notion writes.

Structured logs (JSON by default) include project, action, status, duration, and API stats.
Configure via:
```json
\"logging\": { \"json\": true, \"level\": \"INFO\" }
```
Thread summaries now include timestamps, preview text, and permalinks (when available).

Feature toggles:
```json
\"features\": {
  \"enable_notion_audit_note\": true,
  \"enable_notion_last_synced\": true,
  \"enable_slack_topic_update\": true,
  \"enable_audit\": true,
  \"enable_run_id_idempotency\": true
}
```
Each project can override these flags by adding the same keys to the project object.

Config validation runs on startup (set `settings.validate_config_on_startup` to `false` to skip).
If Notion page IDs are not yet configured, keep `enable_notion_audit_note` / `enable_notion_last_synced` disabled to avoid validation failures.

Validate config only:
```bash
python -m src.engine --validate-config
```

### Browser Automation Fallback
If API keys are not available, enable the browser fallback in `config.json`:
```json
\"browser_automation\": {
  \"enabled\": true,
  \"storage_state_path\": \"browser_storage_state.json\",
  \"slack_workspace_id\": \"TBLCQAFEG\",
  \"headless\": false,
  \"verbose_logging\": false,
  \"keep_open\": false,
  \"interactive_login\": true,
  \"interactive_login_timeout_ms\": 120000,
  \"auto_save_storage_state\": true
}
```

Create a storage state file by logging into Slack/Notion in an automated browser session:
```bash
python -m playwright codegen --save-storage browser_storage_state.json https://app.slack.com/client/TBLCQAFEG
```

Or refresh it interactively during a run:
```bash
python -m src.engine --project <name> --headed --refresh-storage-state
```

Run a quick health check:
```bash
python scripts/browser_health_check.py --config config.json
```

Notes:
- Slack browser fallback uses your logged-in session cookies to call Slack Web API endpoints.
- Notion browser fallback attempts to set the date property by UI automation; verify the update if the UI changes.
- Use `--keep-browser-open` to keep the browser session open after the run (useful for debugging).

## Notes
- The Slack and Notion APIs require their respective permissions.
- The project intentionally keeps the thread extraction logic modular so you can plug in custom
  routing rules or ticket creation later.
