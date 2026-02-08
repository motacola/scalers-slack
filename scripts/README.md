# Scripts Directory

This directory contains utility scripts for the Scalers Slack automation project.

## 📋 Active Scripts (Use These!)

### Daily Reports & Digests

#### `dm_daily_digest.py` ⭐ **RECOMMENDED**
Generate a daily digest of Slack activity in HTML or Markdown format.

```bash
# HTML format (best for reading)
python3 scripts/dm_daily_digest.py --hours 24 --format html --open

# Markdown format
python3 scripts/dm_daily_digest.py --hours 24 --format markdown

# Include DMs (noisier)
python3 scripts/dm_daily_digest.py --hours 24 --format html --include-dms --open

# Important channels only
python3 scripts/dm_daily_digest.py --hours 24 --format html --important --open
```

**Features:**
- HTML/Markdown output
- Filter by channels or DMs
- Auto-open in browser
- Actionable items highlighting
- Hour-based filtering

---

### Monitoring & Health Checks

#### `browser_no_api_smoke.py` ⭐ **Browser-only fallback check**
Validate Slack/Notion browser flows when API keys are unavailable.

```bash
# Preferred: force DOM fallbacks and print diagnostics
python3 scripts/browser_no_api_smoke.py --force-dom

# JSON output for CI/logging
python3 scripts/browser_no_api_smoke.py --force-dom --json

# Faster Slack-only smoke run (skip Notion/thread checks)
python3 scripts/browser_no_api_smoke.py --force-dom --skip-thread --skip-notion

# Tune runtime ceilings when sessions are slow
python3 scripts/browser_no_api_smoke.py --force-dom --interactive-timeout-ms 7000 --page-timeout-ms 12000 --smart-wait-timeout-ms 6000

# Force full thread-pane extraction (slower, but stricter)
python3 scripts/browser_no_api_smoke.py --force-dom --strict-thread
```

**Checks:**
- Slack auth fallback (`auth_test`)
- Conversations/history/thread extraction via browser DOM
- Notion page access with browser session

---

#### `browser_health_check.py`
Test browser automation setup and connectivity.

```bash
python3 scripts/browser_health_check.py --config config/config.json
```

**Checks:**
- Browser automation configuration
- Slack/Notion connectivity
- Storage state validity
- DOM selectors

---

#### `monitor_projects.py`
Monitor project status and health.

```bash
python3 scripts/monitor_projects.py
```

---

### Task Management

#### `check_my_tasks.py`
Check your personal tasks from Slack.

```bash
python3 scripts/check_my_tasks.py
```

---

#### `check_slack_tasks.py`
Check all Slack tasks across channels.

```bash
python3 scripts/check_slack_tasks.py
```

---

#### `check_slack_history.py`
Review Slack channel history.

```bash
python3 scripts/check_slack_history.py
```

---

### Setup & Configuration

#### `create_storage_state.py`
Create browser storage state for authentication.

```bash
python3 scripts/create_storage_state.py --output config/browser_storage_state.json
```

---

### Database Utilities

#### `migrate_to_supabase.py`
Migrate data to Supabase database.

```bash
python3 scripts/migrate_to_supabase.py
```

---

#### `supabase_credentials_helper.py`
Helper for managing Supabase credentials.

```bash
python3 scripts/supabase_credentials_helper.py
```

---

## 🗂️ Deprecated Scripts

The following scripts are **deprecated** and maintained for backward compatibility only.
**Do not use these** - use `dm_daily_digest.py` instead.

Located in `scripts/deprecated/`:
- `daily_task_report.py` - Use `dm_daily_digest.py` instead
- `enhanced_daily_task_report.py` - Use `dm_daily_digest.py` instead
- `daily_report_v2.py` - Use `dm_daily_digest.py` instead
- `daily_report_pure_browser.py` - Use `dm_daily_digest.py` instead

---

## 🚀 Common Workflows

### Morning Routine
```bash
# Get yesterday's digest
python3 scripts/dm_daily_digest.py --hours 24 --format html --important --open

# Check your tasks
python3 scripts/check_my_tasks.py
```

### Weekly Review
```bash
# Get week's digest
python3 scripts/dm_daily_digest.py --hours 168 --format html --open

# Monitor project health
python3 scripts/monitor_projects.py
```

### Troubleshooting
```bash
# Test browser automation
python3 scripts/browser_health_check.py --config config/config.json

# Recreate storage state
python3 scripts/create_storage_state.py --output config/browser_storage_state.json
```

---

## 💡 Script Development Guidelines

### Adding a New Script

1. **Name it clearly**: Use descriptive names like `action_subject.py`
2. **Add docstring**: Explain purpose, usage, and examples
3. **Use argparse**: For command-line arguments
4. **Add to this README**: Document it here
5. **Add tests**: In `tests/` directory

### Script Template

```python
#!/usr/bin/env python3
"""
Brief description of what this script does.

Usage:
    python3 scripts/my_script.py [options]

Examples:
    python3 scripts/my_script.py --config config/config.json
"""

import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="My script")
    parser.add_argument("--config", default="config/config.json", help="Config file")
    args = parser.parse_args()

    # Your code here
    print("Script running...")

if __name__ == "__main__":
    main()
```

---

## 📚 Additional Resources

- **Main Documentation**: See `README.md` in project root
- **Configuration Guide**: See `config/config.json` for settings
- **Browser Automation**: See `docs/browser_automation.md`
- **LLM Integration**: See `docs/LLM_INTEGRATION.md`
- **Project Rules**: See `PROJECT_RULES.md`

---

## ❓ Need Help?

- **General usage**: Check `README.md`
- **Configuration issues**: Run `python -m src.engine --validate-config`
- **Browser automation**: Run `python3 scripts/browser_health_check.py`
- **API issues**: Check `.env` for valid tokens

---

## 🔄 Script Migration Notes

If you were using old scripts, here's how to migrate:

| Old Script | New Command | Notes |
|------------|-------------|-------|
| `daily_task_report.py` | `dm_daily_digest.py --format html` | Better formatting |
| `enhanced_daily_task_report.py` | `dm_daily_digest.py --format html` | Same features |
| `daily_report_v2.py` | `dm_daily_digest.py --format html` | Unified interface |
| `daily_report_pure_browser.py` | `dm_daily_digest.py` | Auto browser fallback |

---

**Last Updated**: February 4, 2026
