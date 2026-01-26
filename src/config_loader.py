import json
import os

DEFAULT_CONFIG = {
    "settings": {
        "slack": {
            "token_env": "SLACK_BOT_TOKEN",
            "base_url": "https://slack.com/api",
            "default_channel_id": ""
        },
        "notion": {
            "token_env": "NOTION_API_KEY",
            "version": "2022-06-28"
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


def load_config(config_path: str) -> dict:
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_path, config_path)
    config = json.loads(json.dumps(DEFAULT_CONFIG))

    if os.path.exists(full_path):
        with open(full_path, "r") as handle:
            user_config = json.load(handle)
        if "settings" in user_config:
            for key, value in user_config["settings"].items():
                if isinstance(value, dict) and key in config["settings"]:
                    config["settings"][key].update(value)
                else:
                    config["settings"][key] = value
        if "projects" in user_config:
            config["projects"] = user_config["projects"]

    return config


def get_project(config: dict, name: str) -> dict | None:
    for project in config.get("projects", []):
        if project.get("name") == name:
            return project
    return None
