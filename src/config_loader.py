import json
import os
import re
from typing import Any, cast

DEFAULT_CONFIG = {
    "settings": {
        "slack": {
            "token_env": "SLACK_BOT_TOKEN",
            "base_url": "https://slack.com/api",
            "default_channel_id": "",
            "timeout_seconds": 30,
            "pagination": {"history_limit": 200, "history_max_pages": 5, "search_limit": 100, "search_max_pages": 3},
            "retries": {
                "max_attempts": 5,
                "backoff_base": 0.5,
                "backoff_max": 8.0,
                "jitter": 0.25,
                "retry_on_status": [408, 429, 500, 502, 503, 504],
                "retry_on_network_error": True,
            },
        },
        "notion": {
            "token_env": "NOTION_API_KEY",
            "version": "2022-06-28",
            "timeout_seconds": 30,
            "retries": {
                "max_attempts": 5,
                "backoff_base": 0.5,
                "backoff_max": 8.0,
                "jitter": 0.25,
                "retry_on_status": [408, 429, 500, 502, 503, 504],
                "retry_on_network_error": True,
                "retry_non_idempotent": False,
            },
        },
        "features": {
            "enable_notion_audit_note": True,
            "enable_notion_last_synced": True,
            "enable_slack_topic_update": True,
            "enable_audit": True,
            "enable_run_id_idempotency": True,
        },
        "validate_config_on_startup": True,
        "logging": {"json": True, "level": "INFO", "run_report_dir": "output/run_reports"},
        "browser_automation": {
            "enabled": False,
            "storage_state_path": "config/browser_storage_state.json",
            "headless": True,
            "slow_mo_ms": 0,
            "timeout_ms": 30000,
            "browser_channel": None,
            "user_data_dir": None,
            "slack_workspace_id": "",
            "slack_client_url": "https://app.slack.com/client",
            "slack_api_base_url": "https://slack.com/api",
            "notion_base_url": "https://www.notion.so",
            "verbose_logging": False,
            "keep_open": False,
            "interactive_login": True,
            "interactive_login_timeout_ms": 120000,
            "auto_save_storage_state": True,
            "auto_recover": True,
            "auto_recover_refresh": True,
            "smart_wait": True,
            "smart_wait_network_idle": True,
            "smart_wait_timeout_ms": 15000,
            "smart_wait_stability_ms": 600,
            "overlay_enabled": False,
            "recordings_dir": "output/browser_recordings",
            "html_snapshot_on_error": True,
            "event_log_path": "output/browser_events.jsonl",
            "screenshot_on_step": False,
            "screenshot_on_error": True,
        },
        "audit": {
            "enabled": True,
            "storage_dir": "audit",
            "sqlite_path": "audit/audit.db",
            "jsonl_path": "audit/audit.jsonl",
            "notion_audit_page_id": "",
            "notion_last_synced_page_id": "",
            "notion_last_synced_property": "Last Synced",
        },
    },
    "projects": [],
}

ENV_VAR_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
NOTION_ID_RE = re.compile(r"[0-9a-fA-F]{32}")
NOTION_ID_DASHED_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _resolve_env_placeholder(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("env:"):
        var_name = stripped[4:].strip()
        return os.getenv(var_name, "") if var_name else ""
    match = ENV_VAR_PATTERN.match(stripped)
    if match:
        return os.getenv(match.group(1), "")
    return value


def _resolve_env_in_config(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env_in_config(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env_in_config(item) for item in value]
    if isinstance(value, str):
        return _resolve_env_placeholder(value)
    return value


def _extract_notion_id(value: str) -> str | None:
    stripped = value.strip()
    if NOTION_ID_RE.fullmatch(stripped):
        return stripped
    if NOTION_ID_DASHED_RE.fullmatch(stripped):
        return stripped.replace("-", "")
    dashed_match = NOTION_ID_DASHED_RE.search(stripped)
    if dashed_match:
        return dashed_match.group(0).replace("-", "")
    raw_match = NOTION_ID_RE.search(stripped)
    if raw_match:
        return raw_match.group(0)
    return None


def _normalize_notion_ids(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {item_key: _normalize_notion_ids(item, item_key) for item_key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_notion_ids(item) for item in value]
    if isinstance(value, str) and key and key.endswith(("_page_id", "_database_id")):
        extracted = _extract_notion_id(value)
        if extracted:
            return extracted
    return value


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config(config_path: str) -> dict[str, Any]:
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_path, config_path)
    config = cast(dict[str, Any], json.loads(json.dumps(DEFAULT_CONFIG)))

    if os.path.exists(full_path):
        with open(full_path, "r") as handle:
            user_config = cast(dict[str, Any], json.load(handle))
        _deep_merge(config, user_config)

    resolved = _resolve_env_in_config(config)
    normalized = _normalize_notion_ids(resolved)
    return cast(dict[str, Any], normalized)


def get_project(config: dict[str, Any], name: str) -> dict[str, Any] | None:
    for project in config.get("projects", []):
        if project.get("name") == name:
            return cast(dict[str, Any], project)
    return None
