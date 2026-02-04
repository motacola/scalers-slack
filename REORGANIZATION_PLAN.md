# Project Reorganization Plan
**Created:** February 4, 2026
**Status:** DRAFT - Review before executing

## Objective
Clean up project structure while maintaining all functionality and without data loss.

---

## Phase 1: Root Directory Cleanup

### 1.1 Move Configuration Files
```bash
# Move main config to config directory
mv config.json config/config.json

# Move browser state to config directory
mv browser_storage_state.json config/browser_storage_state.json

# Update references in code that use these paths
```

**Files to update:**
- `src/config_loader.py` - Update default config path
- `src/browser_automation.py` - Update storage_state path
- `src/enhanced_browser_automation.py` - Update storage_state path
- `src/pure_browser_automation.py` - Update storage_state path
- All scripts that reference these files
- README.md - Update example paths

### 1.2 Move Utility Scripts
```bash
# Move migration scripts to scripts directory
mv migrate_to_supabase.py scripts/migrate_to_supabase.py
mv supabase_credentials_helper.py scripts/supabase_credentials_helper.py
```

### 1.3 Move/Archive Temporary Files
```bash
# Move temporary files to output directory (or delete if obsolete)
mv tasks_2026_01_28.txt output/archive/tasks_2026_01_28.txt
mv suspect_projects.json output/archive/suspect_projects.json

# Create archive directory first
mkdir -p output/archive
```

### 1.4 Move Browser Profile
```bash
# Move chrome profile to a hidden cache directory
mv chrome_profile .cache/chrome_profile

# Update gitignore if needed
```

**Files to update:**
- Any scripts/code referencing `./chrome_profile`
- `.gitignore` - Update chrome_profile path

---

## Phase 2: Source Code Consolidation

### 2.1 Browser Automation Module Consolidation

**Current State:**
- `src/browser_automation.py` (original)
- `src/enhanced_browser_automation.py` (enhanced version)
- `src/pure_browser_automation.py` (pure browser approach)

**Recommended Action:**
1. Analyze which module is actively used
2. Determine if modules serve different purposes or are iterations
3. Options:
   - **Option A:** Keep all if they serve different use cases, add clear docstrings
   - **Option B:** Deprecate old versions, move to `src/deprecated/` directory
   - **Option C:** Merge functionality into single module with feature flags

**Analysis Needed:**
- Check which scripts import which browser automation module
- Review git history to understand evolution
- Test to ensure the "pure" version is complete replacement

### 2.2 Daily Report Script Consolidation

**Current State:**
- `scripts/daily_task_report.py`
- `scripts/enhanced_daily_task_report.py`
- `scripts/daily_report_v2.py`
- `scripts/daily_report_pure_browser.py`

**Recommended Action:**
1. Identify the "canonical" daily report script
2. Move deprecated versions to `scripts/deprecated/` or `scripts/archive/`
3. Add clear documentation about which script to use

**Create:**
```bash
mkdir -p scripts/deprecated
# Move old versions here after identifying current version
```

---

## Phase 3: Directory Structure Enhancement

### 3.1 Create New Directories
```bash
# For deprecated code
mkdir -p src/deprecated
mkdir -p scripts/deprecated

# For archived outputs
mkdir -p output/archive

# For browser-related cache
mkdir -p .cache/browser
```

### 3.2 Proposed Final Structure
```
scalers-slack/
├── .cache/                      # All cache and temporary browser data
│   ├── browser/
│   │   ├── chrome_profile/
│   │   └── recordings/
│   └── ...
├── .env                         # Environment variables (stays in root)
├── .git/
├── .gitignore
├── .venv/
├── README.md
├── PROJECT_RULES.md
├── REORGANIZATION_PLAN.md      # This file
├── pyproject.toml
├── requirements.txt
├── requirements-browser.txt
├── requirements-dev.txt
│
├── audit/                       # Audit logs and database
│   ├── audit.db
│   └── audit.jsonl
│
├── config/                      # All configuration files
│   ├── config.json              # MOVED from root
│   ├── browser_storage_state.json  # MOVED from root
│   └── (other config files)
│
├── docs/                        # Documentation
│
├── output/                      # Generated outputs
│   ├── archive/                 # OLD: tasks_2026_01_28.txt, suspect_projects.json
│   ├── auto-improve/
│   ├── run_reports/
│   ├── snapshots/
│   └── test_run_reports/
│
├── scripts/                     # Executable scripts
│   ├── deprecated/              # OLD: older versions of scripts
│   ├── browser_health_check.py
│   ├── check_my_tasks.py
│   ├── check_slack_history.py
│   ├── check_slack_tasks.py
│   ├── dm_daily_digest.py       # Current daily digest script
│   ├── migrate_to_supabase.py   # MOVED from root
│   ├── supabase_credentials_helper.py  # MOVED from root
│   └── ...
│
├── src/                         # Core library code
│   ├── deprecated/              # OLD: browser automation iterations
│   ├── __init__.py
│   ├── audit_logger.py
│   ├── browser_automation.py    # Current/active version
│   ├── cache_manager.py
│   ├── config_loader.py         # UPDATE: default paths
│   ├── config_manager.py
│   ├── config_validation.py
│   ├── dom_selectors.py
│   ├── engine.py
│   ├── historical_comparison.py
│   ├── models.py
│   ├── notion_client.py
│   ├── report_generator.py
│   ├── slack_client.py
│   ├── summarizer.py
│   ├── task_processor.py
│   ├── thread_extractor.py
│   ├── ticket_manager.py
│   └── utils.py
│
└── tests/                       # Test files
```

---

## Phase 4: Code Updates Required

### 4.1 Update Config Loader
**File:** `src/config_loader.py`

Change default config path:
```python
# OLD: config.json
# NEW: config/config.json
```

### 4.2 Update Browser Automation Paths
**Files:**
- `src/browser_automation.py`
- `src/enhanced_browser_automation.py`
- `src/pure_browser_automation.py`

Change default storage state path:
```python
# OLD: browser_storage_state.json
# NEW: config/browser_storage_state.json
```

Change chrome profile path:
```python
# OLD: ./chrome_profile
# NEW: .cache/browser/chrome_profile
```

### 4.3 Update README.md
Update all command examples to reference new paths:
```bash
# OLD: python3 -m src.engine --project scalers-slack
# NEW: (same, but note config is in config/)

# OLD: browser_storage_state.json
# NEW: config/browser_storage_state.json

# OLD: --user-data-dir ./chrome_profile
# NEW: --user-data-dir .cache/browser/chrome_profile
```

### 4.4 Update .gitignore
```gitignore
# Browser artifacts
.cache/
chrome_profile/
config/browser_storage_state.json
config/config.json  # If it contains secrets

# Keep configs directory but ignore sensitive files
config/*.local.json
```

### 4.5 Update All Scripts
Search and replace in all scripts:
- `config.json` → `config/config.json`
- `browser_storage_state.json` → `config/browser_storage_state.json`
- `./chrome_profile` → `.cache/browser/chrome_profile`

---

## Phase 5: Cleanup and Deprecation

### 5.1 Identify Active vs Deprecated Modules

**Analysis Required:**
```bash
# Find which browser automation module is most used
grep -r "from.*browser_automation import\|import browser_automation" scripts/ src/

# Find which daily report is most used
grep -r "daily.*report" scripts/ src/
```

### 5.2 Mark Deprecated Files

Add deprecation notices to old files:
```python
"""
DEPRECATED: This module has been superseded by <new_module>.
Kept for backward compatibility. Will be removed in version X.X.X

Use <new_module> instead.
"""
import warnings
warnings.warn("module_name is deprecated, use <new_module> instead", DeprecationWarning)
```

---

## Phase 6: Documentation Updates

### 6.1 Create Migration Guide
**File:** `docs/MIGRATION_GUIDE.md`

Document:
- Old paths → New paths
- Deprecated modules → Current modules
- How to update custom scripts
- Breaking changes (if any)

### 6.2 Update README.md
- Update all example commands with new paths
- Add "Directory Structure" section
- Link to migration guide

### 6.3 Update PROJECT_RULES.md
- Update file paths if referenced
- Add note about new directory structure

---

## Phase 7: Testing Plan

### 7.1 Before Reorganization
```bash
# Run existing tests
pytest

# Test key scripts
python3 scripts/dm_daily_digest.py --hours 24 --format html --dry-run
python3 scripts/check_my_tasks.py --dry-run

# Backup entire project
tar -czf ../scalers-slack-backup-$(date +%Y%m%d).tar.gz .
```

### 7.2 After Each Phase
```bash
# Verify imports still work
python3 -c "from src import engine; print('OK')"

# Run tests
pytest

# Test configuration loading
python3 -m src.engine --validate-config

# Test browser automation
python3 scripts/browser_health_check.py --config config/config.json
```

---

## Execution Checklist

- [ ] **Phase 0: Backup**
  - [ ] Create full project backup
  - [ ] Commit current state to git
  - [ ] Create reorganization branch

- [ ] **Phase 1: Move Files**
  - [ ] Create new directories
  - [ ] Move config.json
  - [ ] Move browser_storage_state.json
  - [ ] Move chrome_profile
  - [ ] Move utility scripts
  - [ ] Move/archive temporary files

- [ ] **Phase 2: Update Code**
  - [ ] Update config_loader.py
  - [ ] Update browser automation modules
  - [ ] Update all scripts referencing moved files
  - [ ] Update .gitignore

- [ ] **Phase 3: Test**
  - [ ] Run pytest
  - [ ] Test config validation
  - [ ] Test key scripts
  - [ ] Verify browser automation

- [ ] **Phase 4: Consolidate Modules**
  - [ ] Analyze browser automation modules
  - [ ] Deprecate or merge duplicates
  - [ ] Analyze daily report scripts
  - [ ] Move deprecated scripts

- [ ] **Phase 5: Documentation**
  - [ ] Update README.md
  - [ ] Create migration guide
  - [ ] Update PROJECT_RULES.md
  - [ ] Add docstrings to deprecated modules

- [ ] **Phase 6: Final Verification**
  - [ ] Full test suite
  - [ ] Manual testing of key workflows
  - [ ] Review git diff
  - [ ] Update changelog

---

## Rollback Plan

If issues occur:
```bash
# Restore from backup
cd ..
tar -xzf scalers-slack-backup-YYYYMMDD.tar.gz

# Or revert git commits
git reset --hard <commit-before-reorganization>
```

---

## Questions to Answer Before Execution

1. **Which browser automation module is the "current" one?**
   - Check git log, imports, and functionality

2. **Which daily report script should users run?**
   - Identify canonical version

3. **Does config.json contain secrets?**
   - If yes, ensure it stays in .gitignore
   - Consider using .env for all secrets

4. **Are there CI/CD pipelines that reference old paths?**
   - Update GitHub Actions, etc.

5. **Are there external references to file paths?**
   - Documentation elsewhere
   - User scripts
   - Cron jobs

---

## Benefits After Reorganization

1. **Cleaner root directory** - Only essential files visible
2. **Logical grouping** - Config files in config/, cache in .cache/
3. **Easier maintenance** - Deprecated code clearly marked
4. **Better git hygiene** - Cache and generated files properly ignored
5. **Clearer documentation** - Users know which script to run
6. **Safer development** - Less risk of accidentally committing secrets

---

## Notes

- All moves should preserve git history (use `git mv` when possible)
- Test thoroughly after each phase
- Consider doing this in small PRs rather than one big change
- Keep backup until fully verified
