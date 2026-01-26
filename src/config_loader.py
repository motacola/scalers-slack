import json
import os
from typing import Any, cast

DEFAULT_CONFIG = {
    "settings": {
        "slack": {
            "token_env": "SLACK_BOT_TOKEN",
            "base_url": "https://slack.com/api",
            "default_channel_id": "",
            "timeout_seconds": 30,
            "pagination": {
                "history_limit": 200,
                "history_max_pages": 5,
                "search_limit": 100,
                "search_max_pages": 3
            },
            "retries": {
                "max_attempts": 5,
                "backoff_base": 0.5,
                "backoff_max": 8.0,
                "jitter": 0.25,
                "retry_on_status": [408, 429, 500, 502, 503, 504],
                "retry_on_network_error": True
            }
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
                "retry_non_idempotent": False
            }
        },
        "features": {
            "enable_notion_audit_note": True,
            "enable_notion_last_synced": True,
            "enable_slack_topic_update": True,
            "enable_audit": True,
            "enable_run_id_idempotency": True
        },
        "validate_config_on_startup": True,
        "browser_automation": {
            "enabled": False,
            "storage_state_path": "browser_storage_state.json",
            "headless": True,
            "slow_mo_ms": 0,
            "timeout_ms": 30000,
            "slack_workspace_id": "",
            "slack_client_url": "https://app.slack.com/client",
            "slack_api_base_url": "https://slack.com/api",
            "notion_base_url": "https://www.notion.so"
        },
        "audit": {
            "enabled": True,
            "storage_dir": "audit",
            "sqlite_path": "audit/audit.db",
            "jsonl_path": "audit/audit.jsonl",
            "notion_audit_page_id": "",
            "notion_last_synced_page_id": "",
            "notion_last_synced_property": "Last Synced"
        }
    },
    "projects": []
}


def load_config(config_path: str) -> dict[str, Any]:
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_path, config_path)
    config = cast(dict[str, Any], json.loads(json.dumps(DEFAULT_CONFIG)))

    if os.path.exists(full_path):
        with open(full_path, "r") as handle:
            user_config = cast(dict[str, Any], json.load(handle))
        if "settings" in user_config:
            for key, value in user_config["settings"].items():
                if isinstance(value, dict) and key in config["settings"]:
                    config["settings"][key].update(value)
                else:
                    config["settings"][key] = value
        if "projects" in user_config:
            config["projects"] = user_config["projects"]

    return config


def get_project(config: dict[str, Any], name: str) -> dict[str, Any] | None:
    for project in config.get("projects", []):
        if project.get("name") == name:
            return cast(dict[str, Any], project)
    return None
