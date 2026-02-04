import re
from typing import Any

from jsonschema import Draft7Validator

SLACK_CHANNEL_RE = re.compile(r"^[CG][A-Z0-9]{8,}$")
NOTION_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")
NOTION_ID_DASHED_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
NOTION_ID_IN_TEXT_RE = re.compile(r"[0-9a-fA-F]{32}")
NOTION_ID_DASHED_IN_TEXT_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "settings": {"type": "object"},
        "projects": {
            "type": "array",
            "items": {"type": "object"},
        },
    },
    "required": ["settings", "projects"],
}


FEATURE_DEFAULTS = {
    "enable_notion_audit_note": True,
    "enable_notion_last_synced": True,
    "enable_slack_topic_update": True,
    "enable_audit": True,
    "enable_run_id_idempotency": True,
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


def validate_config(config: dict) -> list[str]:
    errors: list[str] = []

    validator = Draft7Validator(SCHEMA)
    for error in validator.iter_errors(config):
        errors.append(f"schema: {error.message}")

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

    for project in config.get("projects", []):
        name = project.get("name")
        if not name:
            errors.append("project.name is required")
            continue

    project_names = [p.get("name") for p in config.get("projects", []) if p.get("name")]
    duplicates = {n for n in project_names if project_names.count(n) > 1}
    for dup in sorted(duplicates):
        errors.append(f"project.name must be unique: {dup}")

    for project in config.get("projects", []):
        name = project.get("name") or "(unknown)"
        channel_id = project.get("slack_channel_id")
        if not channel_id:
            errors.append(f"project '{name}' missing slack_channel_id")
        elif not SLACK_CHANNEL_RE.match(channel_id):
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


def validate_or_raise(config: dict) -> None:
    errors = validate_config(config)
    if errors:
        error_text = "\n".join(errors)
        raise RuntimeError(f"Config validation failed:\n{error_text}")
