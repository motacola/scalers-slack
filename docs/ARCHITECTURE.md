# System Architecture

This document provides a high-level overview of the Scalers Slack automation system architecture.

## Overview

The system automates the extraction of Slack threads, processing them into structured tasks, and syncing them to Notion for project management.

```
┌─────────────┐         ┌──────────────┐         ┌────────────┐
│    Slack    │────────▶│  Processing  │────────▶│   Notion   │
│  Channels   │         │    Engine    │         │  Database  │
└─────────────┘         └──────────────┘         └────────────┘
       │                       │                        │
       │                       ▼                        │
       │                  ┌─────────┐                  │
       │                  │  Audit  │                  │
       │                  │  Logger │                  │
       │                  └─────────┘                  │
       │                                                │
       └────────────────────────────────────────────────┘
                  Alternative: Browser Automation
```

## Core Components

### 1. Data Sources

#### Slack Client (`src/slack_client.py`)
- **Purpose**: Fetch messages from Slack channels
- **Methods**:
  - API-based (requires `SLACK_BOT_TOKEN`)
  - Browser automation fallback (no API key needed)
- **Features**:
  - Thread extraction
  - Pagination handling
  - Rate limiting & retries
  - User/channel metadata

#### Browser Automation (`src/browser_automation.py`)
- **Purpose**: Headless browser control when API unavailable
- **Technology**: Playwright
- **Capabilities**:
  - Slack login via stored session
  - DOM extraction
  - Network interception
  - Dynamic content loading

**Alternative Implementations**:
- `enhanced_browser_automation.py` - Enhanced reliability
- `pure_browser_automation.py` - Pure browser approach (no API)

---

### 2. Processing Layer

#### Engine (`src/engine.py`)
- **Purpose**: Main orchestration and workflow
- **Key Functions**:
  - `run_sync()` - Full sync workflow
  - `run_summarize()` - Generate activity summaries
  - `run_ticket_update()` - Update Notion tickets
- **Features**:
  - Project configuration
  - Dry-run mode
  - Concurrent processing
  - Run ID idempotency

#### Thread Extractor (`src/thread_extractor.py`)
- **Purpose**: Extract and structure Slack threads
- **Process**:
  1. Fetch messages from channels
  2. Group into conversation threads
  3. Extract metadata (users, timestamps, links)
  4. Filter by time range/query

#### Task Processor (`src/task_processor.py`)
- **Purpose**: Convert messages to structured tasks
- **Process**:
  1. Detect actionable content
  2. Calculate urgency scores
  3. Extract mentions, due dates
  4. Assign owners, priorities
  5. Group and deduplicate
- **Key Functions**:
  - `is_likely_task()` - Detect actionable messages
  - `process_message()` - Convert to Task object
  - `group_tasks_by_owner/client()` - Organize tasks

---

### 3. Output Layer

#### Notion Client (`src/notion_client.py`)
- **Purpose**: Write structured data to Notion
- **Methods**:
  - API-based (requires `NOTION_API_KEY`)
  - Browser automation fallback
- **Operations**:
  - Append blocks to pages
  - Update page properties
  - Query databases
  - Rate limiting & retries

#### Report Generator (`src/report_generator.py`)
- **Purpose**: Generate human-readable reports
- **Formats**:
  - CSV - Spreadsheet import
  - JSON - Programmatic access
  - Markdown - GitHub/documentation
  - HTML - Interactive browser view
- **Features**:
  - Grouping (by owner, client, priority)
  - Filtering (actionable only)
  - Styling and formatting

#### Ticket Manager (`src/ticket_manager.py`)
- **Purpose**: Create/update Notion database entries
- **Features**:
  - Template-based ticket creation
  - Field mapping
  - Duplicate detection

---

### 4. Cross-Cutting Concerns

#### Audit Logger (`src/audit_logger.py`)
- **Purpose**: Track all operations for debugging/compliance
- **Storage**:
  - Primary: SQLite (`audit/audit.db`)
  - Fallback: JSONL (`audit/audit.jsonl`)
- **Data Logged**:
  - Timestamps
  - Operations performed
  - Success/failure status
  - Duration metrics

#### Config Loader (`src/config_loader.py`)
- **Purpose**: Load and validate configuration
- **Sources**:
  - `config/config.json` - Main config
  - Environment variables (`.env`)
  - Command-line arguments
- **Features**:
  - Schema validation
  - Environment variable substitution
  - Per-project overrides

#### LLM Client (`src/llm_client.py`) 🆕
- **Purpose**: Multi-provider AI integration
- **Providers**:
  - OpenAI (GPT-4, GPT-3.5)
  - Anthropic (Claude)
  - Ollama (Local LLMs)
- **Use Cases**:
  - Thread summarization
  - Action item extraction
  - Message categorization
  - Auto-responses

---

## Data Flow

### Primary Flow: Slack → Processing → Notion

```
1. Configuration Load
   ├─ Read config.json
   ├─ Load environment variables
   └─ Validate settings

2. Slack Data Extraction
   ├─ Connect to Slack (API or Browser)
   ├─ Fetch messages from channels
   ├─ Extract threads
   └─ Get user/channel metadata

3. Task Processing
   ├─ Filter messages by time/query
   ├─ Detect actionable content
   ├─ Calculate priorities
   ├─ Assign owners
   └─ Group and deduplicate

4. Output Generation
   ├─ Create Notion audit notes
   ├─ Update Last Synced timestamps
   ├─ Generate reports (HTML/MD/CSV/JSON)
   └─ Log audit trail

5. Verification
   ├─ Verify Notion writes
   ├─ Check Slack topic updates
   └─ Record run metadata
```

### Browser Automation Flow (Fallback)

When API tokens unavailable:

```
1. Load Browser Session
   ├─ Read storage_state.json
   ├─ Launch browser (Chrome/Chromium)
   └─ Restore cookies/localStorage

2. Navigate & Extract
   ├─ Navigate to Slack workspace
   ├─ Find target channels
   ├─ Scroll to load history
   ├─ Extract DOM elements
   └─ Intercept network requests

3. Data Processing
   ├─ Parse extracted data
   ├─ Same as API flow
   └─ Continue to output

4. Session Management
   ├─ Auto-refresh if needed
   ├─ Handle rate limits
   ├─ Save updated session
   └─ Cleanup
```

---

## Key Design Decisions

### 1. API First, Browser Fallback
**Decision**: Prefer Slack/Notion APIs, use browser automation as fallback

**Rationale**:
- APIs are faster and more reliable
- Browser automation handles API quota limits
- Enables use without API access
- Provides redundancy

**Trade-offs**:
- More code to maintain
- Browser automation is slower
- DOM selectors can break

---

### 2. Multiple Browser Automation Modules
**Current State**: 3 implementations
- `browser_automation.py` (1,072 lines) - Primary
- `enhanced_browser_automation.py` (395 lines) - Enhanced features
- `pure_browser_automation.py` (581 lines) - API-free approach

**Rationale**:
- Evolution of approach
- Different use cases
- Experimentation

**Future**: Consolidate or clearly differentiate

---

### 3. Run ID Idempotency
**Decision**: Use deterministic Run IDs to prevent duplicate writes

**Implementation**:
```python
run_id = hash(project_name + since + query + date)
```

**Benefits**:
- Prevents duplicate Notion notes
- Safe to re-run syncs
- Audit trail linkage

---

### 4. Structured Logging
**Decision**: Use Python logging framework instead of print statements

**Implementation**:
- JSON-formatted logs
- Severity levels (DEBUG, INFO, WARNING, ERROR)
- Contextual data (project, duration, API stats)
- File + console output

**Benefits**:
- Filterable logs
- Structured data for analysis
- Better debugging

---

### 5. Config-Driven Architecture
**Decision**: Externalize all configuration to `config.json`

**Structure**:
```json
{
  "settings": {
    "slack": {...},
    "notion": {...},
    "browser_automation": {...},
    "llm": {...}
  },
  "projects": [
    {
      "name": "project-name",
      "slack_channels": [...],
      "notion_page_ids": {...}
    }
  ]
}
```

**Benefits**:
- No code changes for new projects
- Easy to version control
- Environment-specific configs
- Per-project overrides

---

## Module Relationships

### Dependency Graph

```
┌────────────┐
│   Engine   │────────────┐
└────────────┘            │
      │                   │
      ├──────────┬────────┼────────┬─────────┐
      ▼          ▼        ▼        ▼         ▼
┌──────────┐  ┌────┐  ┌──────┐  ┌──────┐  ┌──────┐
│  Thread  │  │Task│  │Notion│  │Report│  │Audit │
│Extractor │  │Proc│  │Client│  │ Gen  │  │Logger│
└──────────┘  └────┘  └──────┘  └──────┘  └──────┘
      │         │        │          │          │
      ▼         ▼        ▼          ▼          ▼
┌──────────┐  ┌────┐  ┌──────┐  ┌──────┐  ┌──────┐
│  Slack   │  │Task│  │Browser│ │ Task │  │SQLite│
│  Client  │  │ │  │Autom.│  │Proc. │  │/JSONL│
└──────────┘  └────┘  └──────┘  └──────┘  └──────┘
      │                  │
      └──────────────────┘
     Browser Automation
```

### Module Interactions

1. **Config Loading** (Start)
   - `config_loader.py` → All modules
   - `config_validation.py` → Validates structure

2. **Data Acquisition**
   - `slack_client.py` → `thread_extractor.py`
   - `browser_automation.py` → `slack_client.py` (fallback)

3. **Processing**
   - `thread_extractor.py` → `task_processor.py`
   - `task_processor.py` → `report_generator.py`
   - `task_processor.py` → `ticket_manager.py`

4. **Output**
   - `notion_client.py` → Notion API
   - `report_generator.py` → File system
   - `audit_logger.py` → Database

5. **Utilities** (Used everywhere)
   - `utils.py` - Common functions
   - `logging_utils.py` - Logging setup
   - `models.py` - Data structures

---

## Configuration

### Environment Variables

```bash
# Required
SLACK_BOT_TOKEN=xoxb-...
NOTION_API_KEY=secret_...

# Optional (LLM)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional (Database)
SUPABASE_URL=https://...
SUPABASE_KEY=...
```

### Project Configuration

```json
{
  "name": "project-name",
  "slack_channels": ["C123ABC", "C456DEF"],
  "notion_audit_page_id": "28e1c9f5...",
  "enable_slack_topic_update": true,
  "slack_pagination": {
    "history_max_pages": 3
  }
}
```

---

## Extension Points

### Adding New Data Sources
1. Create client in `src/` (e.g., `discord_client.py`)
2. Implement same interface as `slack_client.py`
3. Update `thread_extractor.py` to support new source
4. Add config section

### Adding New Output Formats
1. Add method to `report_generator.py`
2. Follow pattern: `to_<format>(output_path)`
3. Update tests

### Adding New LLM Providers
1. Create class inheriting from `LLMClient`
2. Implement `generate()` and `generate_with_context()`
3. Add to factory in `create_llm_client()`
4. Update docs

### Custom Task Processors
1. Add detection function to `task_processor.py`
2. Update `process_message()` to use new logic
3. Add tests

---

## Performance Considerations

### Bottlenecks
1. **Slack API Rate Limits** - 50-100 req/min
   - Mitigation: Pagination caps, retry logic
2. **Browser Automation Speed** - 2-3x slower than API
   - Mitigation: Use API when available, smart waits
3. **Notion API Rate Limits** - 3 req/sec
   - Mitigation: Batch operations, exponential backoff

### Optimization Strategies
- **Concurrent Processing**: `ThreadPoolExecutor` for multi-project syncs
- **Caching**: Historical comparison snapshots
- **Smart Pagination**: Cap pages for high-traffic channels
- **Run ID Deduplication**: Skip redundant Notion writes

---

## Security

### Secrets Management
- **Storage**: `.env` file (gitignored)
- **Access**: `os.getenv()` only
- **Browser Sessions**: `config/browser_storage_state.json` (gitignored)

### Data Privacy
- **Audit Logs**: Local only (`audit/`)
- **Reports**: Local only (`output/`)
- **No Cloud Storage**: Everything stays on your machine

### API Permissions
- **Slack**: `channels:history`, `channels:read`, `chat:write`, `users:read`
- **Notion**: Read/write access to specific pages/databases

---

## Monitoring & Debugging

### Logs
- **Location**: Console + `output/run_reports/`
- **Format**: JSON (structured) or text
- **Levels**: DEBUG, INFO, WARNING, ERROR

### Audit Trail
- **Database**: `audit/audit.db` (SQLite)
- **Fields**: timestamp, action, status, duration, metadata
- **Query**: Standard SQL

### Health Checks
- **Config Validation**: `python -m src.engine --validate-config`
- **Browser Check**: `python scripts/browser_health_check.py`
- **Tests**: `pytest`

---

## Future Architecture

### Planned Improvements
1. **Modular Browser Automation**: Consolidate 3 modules into 1
2. **Plugin System**: Load custom processors at runtime
3. **Webhook Support**: Real-time Slack events
4. **Database Backend**: Replace JSON config with SQLite/PostgreSQL
5. **Web Dashboard**: Flask/FastAPI UI for management
6. **CI/CD Pipeline**: Automated testing and deployment

### Migration Path
1. Deprecate old browser modules → `src/deprecated/`
2. Add plugin loader → `src/plugins/`
3. Create DB schema → `src/database/`
4. Build API layer → `src/api/`
5. Create frontend → `frontend/`

---

## Related Documentation

- **Setup**: See `README.md`
- **Contributing**: See `CONTRIBUTING.md`
- **LLM Integration**: See `docs/LLM_INTEGRATION.md`
- **Browser Automation**: See `docs/browser_automation.md`
- **Scripts**: See `scripts/README.md`

---

**Last Updated**: February 4, 2026
**Maintainer**: See `CONTRIBUTING.md`
