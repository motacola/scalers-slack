# Project Structure Analysis Summary
**Date:** February 4, 2026

## Current Module Usage Analysis

### Browser Automation Modules

#### 1. `src/browser_automation.py` (41KB - MOST USED)
**Status:** ✅ **ACTIVE - Primary Module**

**Used by:**
- `scripts/monitor_projects.py`
- `scripts/browser_health_check.py`
- `scripts/dm_daily_digest.py`
- `scripts/daily_task_report.py`
- `scripts/check_slack_history.py`
- `scripts/check_slack_tasks.py`
- `scripts/check_my_tasks.py`
- `src/engine.py` (main engine)

**Recommendation:** **KEEP** - This is the primary, stable browser automation module.

---

#### 2. `src/enhanced_browser_automation.py` (13KB)
**Status:** ⚠️ **PARTIALLY USED**

**Used by:**
- `scripts/enhanced_daily_task_report.py`
- `scripts/daily_report_v2.py`
- Imports from `browser_automation.py` (extends it)

**Purpose:** Appears to add enhanced features on top of base browser_automation

**Recommendation:** **EVALUATE**
- If `enhanced_daily_task_report.py` and `daily_report_v2.py` are deprecated, can move this to `src/deprecated/`
- If still needed, keep but add clear documentation about when to use vs base module

---

#### 3. `src/pure_browser_automation.py` (21KB)
**Status:** ⚠️ **MINIMALLY USED**

**Used by:**
- `scripts/daily_report_pure_browser.py` only

**Git History:**
- Recent commit (12f0c20): "Refactor browser automation to pure browser-based approach without API keys"

**Recommendation:** **EVALUATE**
- This appears to be a newer "pure" approach without API keys
- Only one script uses it
- Options:
  - If this is the future direction: Migrate other scripts to it, deprecate old modules
  - If experimental: Move to `src/experimental/` with clear docs
  - If abandoned: Move to `src/deprecated/`

---

### Daily Report Scripts

#### 1. `scripts/dm_daily_digest.py`
**Status:** ✅ **RECOMMENDED**

**Features:**
- HTML/Markdown output
- Filter by channels/DMs
- Hour-based filtering
- Auto-open capability

**Used in README examples** - This appears to be the canonical script

**Recommendation:** **PRIMARY SCRIPT** - This should be the one users run

---

#### 2. `scripts/daily_task_report.py` (8.7KB)
**Status:** ⚠️ **UNCLEAR**

**Output:** CSV format
**Uses:** Base `browser_automation.py`

**Recommendation:** **EVALUATE**
- If CSV output is needed, keep
- Otherwise, deprecate in favor of `dm_daily_digest.py`

---

#### 3. `scripts/enhanced_daily_task_report.py`
**Status:** ⚠️ **UNCLEAR**

**Uses:** `enhanced_browser_automation.py`

**Recommendation:** **LIKELY DEPRECATED**
- Similar to daily_task_report but uses enhanced module
- Likely superseded by `dm_daily_digest.py`
- Move to `scripts/deprecated/`

---

#### 4. `scripts/daily_report_v2.py` (11.8KB)
**Status:** ⚠️ **UNCLEAR**

**Uses:**
- `enhanced_browser_automation.py`
- Custom config file: `config/daily_report_defaults.json`

**Recommendation:** **EVALUATE**
- "v2" suggests it's a version iteration
- If superseded by `dm_daily_digest.py`, deprecate
- Check if `daily_report_defaults.json` exists and is used elsewhere

---

#### 5. `scripts/daily_report_pure_browser.py` (11.3KB)
**Status:** ⚠️ **EXPERIMENTAL?**

**Uses:** `pure_browser_automation.py`

**Recommendation:** **EVALUATE**
- Recent approach (based on git history)
- If this is the future, document it clearly
- If experimental, move to `scripts/experimental/`

---

## File Move Priority

### HIGH PRIORITY (Do First)
1. ✅ `config.json` → `config/config.json`
2. ✅ `browser_storage_state.json` → `config/browser_storage_state.json`
3. ✅ `chrome_profile/` → `.cache/browser/chrome_profile/`
4. ✅ `migrate_to_supabase.py` → `scripts/migrate_to_supabase.py`
5. ✅ `supabase_credentials_helper.py` → `scripts/supabase_credentials_helper.py`

### MEDIUM PRIORITY
6. ⚠️ `tasks_2026_01_28.txt` → `output/archive/` (or delete if obsolete)
7. ⚠️ `suspect_projects.json` → `output/archive/` or `config/`

### LOW PRIORITY (Code Consolidation)
8. Evaluate and deprecate unused browser automation modules
9. Consolidate daily report scripts
10. Add deprecation warnings to old modules

---

## Questions to Answer

### Critical Questions (Block reorganization)
1. ❓ **Is `pure_browser_automation.py` the future direction?**
   - If YES: Plan migration of all scripts to use it
   - If NO: Move to experimental/deprecated

2. ❓ **Which daily report should users run?**
   - Current answer: Likely `dm_daily_digest.py` (in README)
   - Confirm other scripts are truly deprecated

3. ❓ **Does `config.json` contain secrets?**
   - Check if it should be gitignored
   - Use `.env` for all secrets instead

### Non-blocking Questions (Can answer during cleanup)
4. ❓ **Is `config/daily_report_defaults.json` used?**
5. ❓ **Are `enhanced_daily_task_report.py` and `daily_report_v2.py` still needed?**
6. ❓ **Is `enhanced_browser_automation.py` providing value over base module?**

---

## Recommended Execution Order

### Stage 1: Safe Moves (No code changes needed)
```bash
# Create directories
mkdir -p config/.gitkeep
mkdir -p .cache/browser
mkdir -p output/archive
mkdir -p src/deprecated
mkdir -p scripts/deprecated

# Move files
git mv migrate_to_supabase.py scripts/
git mv supabase_credentials_helper.py scripts/
mv tasks_2026_01_28.txt output/archive/
mv suspect_projects.json output/archive/
```

### Stage 2: Config File Moves (Requires code updates)
```bash
# Move configs
git mv config.json config/
git mv browser_storage_state.json config/

# Move browser profile
mv chrome_profile .cache/browser/

# Update all file references in code
# (See REORGANIZATION_PLAN.md Phase 4)
```

### Stage 3: Module Consolidation (Requires analysis)
```bash
# Answer questions above first
# Then move deprecated modules
# Add deprecation warnings
# Update documentation
```

---

## Risk Assessment

### LOW RISK ✅
- Moving config files (with code updates)
- Moving chrome_profile to .cache
- Moving utility scripts to scripts/
- Archiving temporary files

### MEDIUM RISK ⚠️
- Deprecating browser automation modules
  - Risk: May break external scripts
  - Mitigation: Keep for now, add deprecation warnings

### HIGH RISK 🔴
- Deleting any browser automation modules
  - Risk: Unknown dependencies
  - Mitigation: NEVER delete, only move to deprecated/

---

## Success Metrics

✅ **Reorganization is successful if:**
1. All tests pass (`pytest`)
2. Main engine runs: `python3 -m src.engine --validate-config`
3. Daily digest works: `python3 scripts/dm_daily_digest.py --hours 24 --format html`
4. Browser health check passes: `python3 scripts/browser_health_check.py --config config/config.json`
5. No files lost (verify with `find` before/after)
6. Git history preserved (used `git mv` where possible)

---

## Next Steps

1. **Review this analysis** - Validate findings
2. **Answer critical questions** - Especially about pure_browser_automation.py direction
3. **Execute Stage 1** - Safe moves (no code changes)
4. **Test Stage 1** - Verify nothing broke
5. **Execute Stage 2** - Config moves with code updates
6. **Test Stage 2** - Run full test suite
7. **Plan Stage 3** - After understanding module purposes

---

## Git Workflow

```bash
# Create branch
git checkout -b reorganize-project-structure

# Stage 1
git add -A
git commit -m "refactor: move utility scripts to scripts/"

# Stage 2
git add -A
git commit -m "refactor: move config files to config/ directory"

# Stage 3 (if done)
git add -A
git commit -m "refactor: deprecate old browser automation modules"

# After all testing passes
git checkout main
git merge reorganize-project-structure
```
