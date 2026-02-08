import re
from typing import Any

from jsonschema import Draft7Validator

SLACK_CHANNEL_RE = re.compile(r"^[CG][A-Z0-9]{8,}$")
NOTION_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")
NOTION_ID_DASHED_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
NOTION_ID_IN_TEXT_RE = re.compile(r"[0-9a-fA-F]{32}")
NOTION_ID_DASHED_IN_TEXT_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


FEATURE_DEFAULTS = {
    "enable_notion_audit_note": True,
    "enable_notion_last_synced": True,
    "enable_slack_topic_update": True,
    "enable_audit": True,
    "enable_run_id_idempotency": True,
}


def _int_schema(minimum: int = 0) -> dict[str, Any]:
    return {"type": "integer", "minimum": minimum}


def _number_schema(minimum: float = 0.0) -> dict[str, Any]:
    return {"type": "number", "minimum": minimum}


PAGINATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "history_limit": _int_schema(1),
        "history_max_pages": _int_schema(1),
        "search_limit": _int_schema(1),
        "search_max_pages": _int_schema(1),
    },
}


RETRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "max_attempts": _int_schema(1),
        "backoff_base": _number_schema(0.0),
        "backoff_max": _number_schema(0.0),
        "jitter": _number_schema(0.0),
        "retry_on_status": {
            "type": "array",
            "items": _int_schema(100),
        },
        "retry_on_network_error": {"type": "boolean"},
        "retry_non_idempotent": {"type": "boolean"},
    },
}


PROJECT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "slack_channel_id": {"type": "string", "pattern": r"^[CG][A-Z0-9]{8,}$"},
        "notion_audit_page_id": {"type": "string"},
        "notion_audit_page_url": {"type": "string"},
        "notion_last_synced_page_id": {"type": "string"},
        "notion_last_synced_page_url": {"type": "string"},
        "notion_page_url": {"type": "string"},
        "slack_pagination": PAGINATION_SCHEMA,
        "enable_notion_audit_note": {"type": "boolean"},
        "enable_notion_last_synced": {"type": "boolean"},
        "enable_slack_topic_update": {"type": "boolean"},
        "enable_audit": {"type": "boolean"},
        "enable_run_id_idempotency": {"type": "boolean"},
    },
    "required": ["name", "slack_channel_id"],
}


CONFIG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "settings": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "notion_hub": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "url": {"type": "string"},
                        "enforce_hub_context": {"type": "boolean"},
                    },
                },
                "ticket_rules": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "max_note_length": _int_schema(1),
                        "long_content_strategy": {"type": "string", "minLength": 1},
                        "allowed_boards_only": {"type": "boolean"},
                    },
                },
                "slack": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "token_env": {"type": "string", "minLength": 1},
                        "base_url": {"type": "string", "minLength": 1},
                        "workspace_domain": {"type": "string"},
                        "default_channel_id": {"type": "string"},
                        "timeout_seconds": _int_schema(1),
                        "pagination": PAGINATION_SCHEMA,
                        "retries": RETRY_SCHEMA,
                    },
                },
                "notion": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "token_env": {"type": "string", "minLength": 1},
                        "version": {"type": "string", "minLength": 1},
                        "timeout_seconds": _int_schema(1),
                        "retries": RETRY_SCHEMA,
                    },
                },
                "audit": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "storage_dir": {"type": "string"},
                        "sqlite_path": {"type": "string"},
                        "jsonl_path": {"type": "string"},
                        "notion_audit_page_id": {"type": "string"},
                        "notion_audit_page_url": {"type": "string"},
                        "notion_last_synced_page_id": {"type": "string"},
                        "notion_last_synced_page_url": {"type": "string"},
                        "notion_tickets_database_id": {"type": "string"},
                        "notion_builds_database_id": {"type": "string"},
                        "notion_last_synced_property": {"type": "string"},
                    },
                },
                "browser_automation": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "storage_state_path": {"type": "string"},
                        "headless": {"type": "boolean"},
                        "slow_mo_ms": _int_schema(0),
                        "timeout_ms": _int_schema(1),
                        "browser_channel": {"type": ["string", "null"]},
                        "user_data_dir": {"type": ["string", "null"]},
                        "slack_workspace_id": {"type": "string"},
                        "slack_client_url": {"type": "string", "minLength": 1},
                        "slack_api_base_url": {"type": "string", "minLength": 1},
                        "notion_base_url": {"type": "string", "minLength": 1},
                        "max_retries": _int_schema(1),
                        "retry_delay_ms": _int_schema(0),
                        "verbose_logging": {"type": "boolean"},
                        "keep_open": {"type": "boolean"},
                        "interactive_login": {"type": "boolean"},
                        "interactive_login_timeout_ms": _int_schema(1),
                        "auto_save_storage_state": {"type": "boolean"},
                        "auto_recover": {"type": "boolean"},
                        "auto_recover_refresh": {"type": "boolean"},
                        "smart_wait": {"type": "boolean"},
                        "smart_wait_network_idle": {"type": "boolean"},
                        "smart_wait_timeout_ms": _int_schema(1),
                        "smart_wait_stability_ms": _int_schema(0),
                        "overlay_enabled": {"type": "boolean"},
                        "recordings_dir": {"type": "string"},
                        "html_snapshot_on_error": {"type": "boolean"},
                        "event_log_path": {"type": "string"},
                        "screenshot_on_step": {"type": "boolean"},
                        "screenshot_on_error": {"type": "boolean"},
                        "proxy_server": {"type": ["string", "null"]},
                        "proxy_username": {"type": ["string", "null"]},
                        "proxy_password": {"type": ["string", "null"]},
                    },
                },
                "features": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "enable_notion_audit_note": {"type": "boolean"},
                        "enable_notion_last_synced": {"type": "boolean"},
                        "enable_slack_topic_update": {"type": "boolean"},
                        "enable_audit": {"type": "boolean"},
                        "enable_run_id_idempotency": {"type": "boolean"},
                    },
                },
                "validate_config_on_startup": {"type": "boolean"},
                "logging": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "json": {"type": "boolean"},
                        "level": {"type": "string", "minLength": 1},
                        "run_report_dir": {"type": "string", "minLength": 1},
                    },
                },
                "user": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "email": {"type": "string"},
                    },
                },
            },
        },
        "projects": {
            "type": "array",
            "items": PROJECT_SCHEMA,
        },
    },
    "required": ["settings", "projects"],
}


TEAM_CHANNELS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "version": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "last_updated": {"type": "string"},
        "channel_categories": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "description": {"type": "string"},
                    "channels": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                },
                "required": ["channels"],
            },
        },
        "team_members": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "slack_display_name": {"type": "string"},
                    "slack_user_id": {"type": ["string", "null"]},
                    "role": {"type": "string"},
                    "timezone": {"type": "string"},
                    "client_channels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "channel": {"type": "string", "minLength": 1},
                                "client": {"type": "string"},
                                "priority": {"type": "string", "minLength": 1},
                                "notes": {"type": "string"},
                            },
                            "required": ["channel"],
                        },
                    },
                    "always_check": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                    "keywords_to_watch": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                },
                "required": ["client_channels"],
            },
        },
        "shared_channels": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "description": {"type": "string"},
                "channels": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                },
            },
            "required": ["channels"],
        },
        "check_order": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "description": {"type": "string"},
                "order": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
        "thread_patterns": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "description": {"type": "string"},
                "completion_indicators": {"type": "array", "items": {"type": "string"}},
                "blocker_indicators": {"type": "array", "items": {"type": "string"}},
                "question_indicators": {"type": "array", "items": {"type": "string"}},
                "urgent_indicators": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "completion_indicators",
                "blocker_indicators",
                "question_indicators",
                "urgent_indicators",
            ],
        },
    },
    "required": ["channel_categories", "team_members", "shared_channels", "thread_patterns"],
}


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _effective_feature(settings: dict, project: dict, key: str) -> bool:
    settings_features = settings.get("features", {}) if isinstance(settings, dict) else {}
    project_value = project.get(key) if isinstance(project, dict) else None
    if project_value is None:
        return _coerce_bool(settings_features.get(key), FEATURE_DEFAULTS[key])
    return _coerce_bool(project_value, FEATURE_DEFAULTS[key])


def _validate_notion_id(value: str) -> bool:
    return _extract_notion_page_id(value) is not None


def _extract_notion_page_id(value: str) -> str | None:
    if NOTION_ID_RE.match(value):
        return value
    if NOTION_ID_DASHED_RE.match(value):
        return value.replace("-", "")
    dashed = NOTION_ID_DASHED_IN_TEXT_RE.search(value)
    if dashed:
        return dashed.group(0).replace("-", "")
    raw = NOTION_ID_IN_TEXT_RE.search(value)
    if raw:
        return raw.group(0)
    return None


def _schema_errors(schema: dict[str, Any], payload: Any, prefix: str) -> list[str]:
    validator = Draft7Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or "(root)"
        errors.append(f"{prefix} schema at {path}: {error.message}")
    return errors


def validate_config(config: dict) -> list[str]:
    errors: list[str] = []

    errors.extend(_schema_errors(CONFIG_SCHEMA, config, "config"))

    settings = config.get("settings", {}) if isinstance(config, dict) else {}
    audit_settings = settings.get("audit", {}) if isinstance(settings, dict) else {}
    browser_settings = settings.get("browser_automation", {}) if isinstance(settings, dict) else {}

    if browser_settings.get("enabled", False):
        storage_state_path = browser_settings.get("storage_state_path")
        user_data_dir = browser_settings.get("user_data_dir")
        interactive_login = browser_settings.get("interactive_login", True)
        headless = browser_settings.get("headless", True)
        if not storage_state_path and not user_data_dir:
            errors.append("settings.browser_automation.enabled requires storage_state_path or user_data_dir")
        if headless and not interactive_login and not storage_state_path and not user_data_dir:
            errors.append(
                "settings.browser_automation: headless with interactive_login disabled "
                "requires storage state or user_data_dir"
            )
        if "event_log_path" in browser_settings and not browser_settings.get("event_log_path"):
            errors.append("settings.browser_automation.event_log_path cannot be empty")

    projects = config.get("projects", []) if isinstance(config, dict) else []
    project_names = [name for p in projects if isinstance(p, dict) for name in [p.get("name")] if isinstance(name, str)]
    duplicates = {n for n in project_names if project_names.count(n) > 1}
    for dup in sorted(duplicates):
        errors.append(f"project.name must be unique: {dup}")

    for project in projects:
        if not isinstance(project, dict):
            continue
        name = project.get("name") or "(unknown)"
        channel_id = project.get("slack_channel_id")
        if channel_id and not SLACK_CHANNEL_RE.match(channel_id):
            errors.append(f"project '{name}' has invalid slack_channel_id: {channel_id}")

        enable_audit = _effective_feature(settings, project, "enable_audit")
        enable_idempotency = _effective_feature(settings, project, "enable_run_id_idempotency")
        if enable_idempotency and not enable_audit:
            errors.append(f"project '{name}' enables run-id idempotency but audit is disabled")

        enable_audit_note = _effective_feature(settings, project, "enable_notion_audit_note")
        enable_last_synced = _effective_feature(settings, project, "enable_notion_last_synced")

        audit_page = project.get("notion_audit_page_id") or audit_settings.get("notion_audit_page_id")
        last_synced_page = project.get("notion_last_synced_page_id") or audit_settings.get("notion_last_synced_page_id")

        if enable_audit_note:
            if not audit_page:
                errors.append(f"project '{name}' missing notion_audit_page_id")
            elif not _validate_notion_id(audit_page):
                errors.append(f"project '{name}' has invalid notion_audit_page_id: {audit_page}")

        if enable_last_synced:
            if not last_synced_page:
                errors.append(f"project '{name}' missing notion_last_synced_page_id")
            elif not _validate_notion_id(last_synced_page):
                errors.append(f"project '{name}' has invalid notion_last_synced_page_id: {last_synced_page}")

            property_name = audit_settings.get("notion_last_synced_property")
            if not property_name:
                errors.append("settings.audit.notion_last_synced_property is required when last synced is enabled")

        notion_page_url = project.get("notion_page_url")
        if notion_page_url and not _extract_notion_page_id(notion_page_url):
            errors.append(f"project '{name}' has invalid notion_page_url")

        pagination = project.get("slack_pagination", {})
        if isinstance(pagination, dict):
            for key in ["history_limit", "history_max_pages", "search_limit", "search_max_pages"]:
                if key in pagination:
                    try:
                        value = int(pagination[key])
                    except (TypeError, ValueError):
                        errors.append(f"project '{name}' has invalid slack_pagination.{key}")
                        continue
                    if value <= 0:
                        errors.append(f"project '{name}' slack_pagination.{key} must be > 0")

    return errors


def validate_team_channels_config(config: Any) -> list[str]:
    errors: list[str] = []
    errors.extend(_schema_errors(TEAM_CHANNELS_SCHEMA, config, "team_channels"))

    if not isinstance(config, dict):
        return errors

    team_members = config.get("team_members", {})
    if not isinstance(team_members, dict):
        return errors

    known_members = set(team_members.keys())

    shared_map = config.get("shared_channels", {}).get("channels", {})
    if isinstance(shared_map, dict):
        for channel, members in shared_map.items():
            if not isinstance(members, list):
                continue
            for member in members:
                if member not in known_members:
                    errors.append(f"shared channel '{channel}' references unknown team member '{member}'")

    for member_name, member_data in team_members.items():
        if not isinstance(member_data, dict):
            continue

        seen_channels: set[str] = set()
        for channel_info in member_data.get("client_channels", []):
            if not isinstance(channel_info, dict):
                continue
            channel = channel_info.get("channel")
            if not isinstance(channel, str) or not channel:
                continue
            if channel in seen_channels:
                errors.append(f"team member '{member_name}' has duplicate client channel '{channel}'")
            seen_channels.add(channel)

    return errors


def validate_or_raise(config: dict) -> None:
    errors = validate_config(config)
    if errors:
        error_text = "\n".join(errors)
        raise RuntimeError(f"Config validation failed:\n{error_text}")


def validate_team_channels_or_raise(config: dict) -> None:
    errors = validate_team_channels_config(config)
    if errors:
        error_text = "\n".join(errors)
        raise RuntimeError(f"Team channel config validation failed:\n{error_text}")
