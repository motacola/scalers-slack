import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

from .audit_logger import AuditLogger
from .browser_automation import BrowserAutomationConfig, BrowserSession, NotionBrowserClient, SlackBrowserClient
from .config_loader import get_project, load_config
from .config_validation import validate_or_raise
from .logging_utils import configure_logging, log_event
from .models import Thread
from .notion_client import NotionClient
from .slack_client import SlackClient
from .summarizer import ActivitySummarizer
from .thread_extractor import ThreadExtractor
from .ticket_manager import TicketManager
from .utils import iso_to_unix_ts, make_run_id, utc_now_iso

logger = logging.getLogger(__name__)


def _coerce_int(value: object, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            return int(value)
        return default
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _effective_feature(feature_settings: dict, project: dict, key: str) -> bool:
    project_value = project.get(key)
    if project_value is None:
        return _coerce_bool(feature_settings.get(key), True)
    return _coerce_bool(project_value, True)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class ScalersSlackEngine:
    def __init__(
        self,
        config_path: str = "config.json",
        config: dict[str, Any] | None = None,
        slack_client: SlackClient | None = None,
        notion_client: NotionClient | None = None,
        audit_logger: AuditLogger | None = None,
        thread_extractor: ThreadExtractor | None = None,
    ):
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config = config or load_config(config_path)

        logging_settings = self.config.get("settings", {}).get("logging", {})
        logging_json = bool(logging_settings.get("json", True))
        logging_level = logging_settings.get("level", "INFO")
        configure_logging(level=logging_level, json_enabled=logging_json)
        self.json_logging = logging_json

        if self.config.get("settings", {}).get("validate_config_on_startup", True):
            validate_or_raise(self.config)

        slack_settings = self.config["settings"]["slack"]
        notion_settings = self.config["settings"]["notion"]
        audit_settings = self.config["settings"]["audit"]
        browser_settings = self.config["settings"].get("browser_automation", {})
        feature_settings = self.config["settings"].get("features", {})

        browser_config = BrowserAutomationConfig(
            enabled=browser_settings.get("enabled", False),
            storage_state_path=browser_settings.get("storage_state_path", ""),
            headless=browser_settings.get("headless", True),
            slow_mo_ms=_coerce_int(browser_settings.get("slow_mo_ms"), 0),
            timeout_ms=_coerce_int(browser_settings.get("timeout_ms"), 30000),
            browser_channel=browser_settings.get("browser_channel"),
            user_data_dir=browser_settings.get("user_data_dir"),
            slack_workspace_id=browser_settings.get("slack_workspace_id", ""),
            slack_client_url=browser_settings.get("slack_client_url", "https://app.slack.com/client"),
            slack_api_base_url=browser_settings.get("slack_api_base_url", "https://slack.com/api"),
            notion_base_url=browser_settings.get("notion_base_url", "https://www.notion.so"),
            verbose_logging=browser_settings.get("verbose_logging", False),
            keep_open=browser_settings.get("keep_open", False),
            interactive_login=browser_settings.get("interactive_login", True),
            interactive_login_timeout_ms=_coerce_int(
                browser_settings.get("interactive_login_timeout_ms"), 120000
            ),
            auto_save_storage_state=browser_settings.get("auto_save_storage_state", True),
            auto_recover=browser_settings.get("auto_recover", True),
            auto_recover_refresh=browser_settings.get("auto_recover_refresh", True),
            smart_wait=browser_settings.get("smart_wait", True),
            smart_wait_network_idle=browser_settings.get("smart_wait_network_idle", True),
            smart_wait_timeout_ms=_coerce_int(browser_settings.get("smart_wait_timeout_ms"), 15000),
            smart_wait_stability_ms=_coerce_int(browser_settings.get("smart_wait_stability_ms"), 600),
            overlay_enabled=browser_settings.get("overlay_enabled", False),
            recordings_dir=browser_settings.get("recordings_dir", "output/browser_recordings"),
            event_log_path=browser_settings.get("event_log_path", "output/browser_events.jsonl"),
            screenshot_on_step=browser_settings.get("screenshot_on_step", False),
            screenshot_on_error=browser_settings.get("screenshot_on_error", True),
        )
        slack_token = os.getenv(slack_settings.get("token_env", "SLACK_BOT_TOKEN"))
        notion_token = os.getenv(notion_settings.get("token_env", "NOTION_API_KEY"))
        slack_timeout = _coerce_int(slack_settings.get("timeout_seconds"), 30)
        notion_timeout = _coerce_int(notion_settings.get("timeout_seconds"), 30)
        slack_retries = slack_settings.get("retries", {})
        notion_retries = notion_settings.get("retries", {})

        needs_browser = browser_config.enabled and (not slack_token or not notion_token)
        self.browser_enabled = needs_browser
        if needs_browser:
            if (
                browser_config.storage_state_path
                and not os.path.exists(browser_config.storage_state_path)
                and (browser_config.headless or not browser_config.interactive_login)
            ):
                raise RuntimeError(
                    "Browser automation is enabled but storage_state_path is missing. "
                    "Create it with Playwright or disable browser_automation."
                )
            self.browser_session: BrowserSession | None = BrowserSession(browser_config)
        else:
            self.browser_session = None

        if slack_client:
            self.slack: SlackClient | SlackBrowserClient = slack_client
        elif slack_token:
            self.slack = SlackClient(
                token=slack_token,
                base_url=slack_settings["base_url"],
                timeout=slack_timeout,
                retry_config=slack_retries,
            )
        elif self.browser_session:
            self.slack = SlackBrowserClient(self.browser_session, browser_config)
        else:
            self.slack = SlackClient(
                token=slack_token,
                base_url=slack_settings["base_url"],
                timeout=slack_timeout,
                retry_config=slack_retries,
            )

        if notion_client:
            self.notion: NotionClient | NotionBrowserClient = notion_client
        elif notion_token:
            self.notion = NotionClient(
                token=notion_token,
                version=notion_settings["version"],
                timeout=notion_timeout,
                retry_config=notion_retries,
            )
        elif self.browser_session:
            self.notion = NotionBrowserClient(self.browser_session, browser_config)
        else:
            self.notion = NotionClient(
                token=notion_token,
                version=notion_settings["version"],
                timeout=notion_timeout,
                retry_config=notion_retries,
            )
        self.audit = audit_logger or AuditLogger(
            enabled=audit_settings.get("enabled", True),
            storage_dir=audit_settings.get("storage_dir", "audit"),
            sqlite_path=audit_settings.get("sqlite_path", "audit/audit.db"),
            jsonl_path=audit_settings.get("jsonl_path", "audit/audit.jsonl"),
        )
        self.thread_extractor = thread_extractor or ThreadExtractor(self.slack)
        self.audit_settings = audit_settings
        self.slack_settings = slack_settings
        self.feature_settings = feature_settings
        self.browser_config = browser_config

    def run_sync(
        self,
        project_name: str,
        since: str | None = None,
        query: str | None = None,
        dry_run: bool = False,
    ) -> None:
        project = get_project(self.config, project_name)
        if not project:
            raise RuntimeError(f"Project '{project_name}' not found in config.json")

        channel_id = project.get("slack_channel_id") or self.slack_settings.get("default_channel_id")
        if not channel_id:
            raise RuntimeError("Slack channel ID is required in config.json")

        # Pagination and time window are handled in collect_activity based on config.
        sync_timestamp = utc_now_iso()
        run_date = sync_timestamp.split("T")[0]
        run_id = make_run_id(project_name, since, query, run_date)

        enable_audit = _effective_feature(self.feature_settings, project, "enable_audit")
        enable_notion_audit_note = _effective_feature(self.feature_settings, project, "enable_notion_audit_note")
        enable_notion_last_synced = _effective_feature(self.feature_settings, project, "enable_notion_last_synced")
        enable_slack_topic_update = _effective_feature(self.feature_settings, project, "enable_slack_topic_update")
        enable_run_id = _effective_feature(self.feature_settings, project, "enable_run_id_idempotency")

        previous_audit_enabled = self.audit.enabled
        if previous_audit_enabled != enable_audit:
            self.audit.enabled = enable_audit
            if enable_audit:
                self.audit.ensure_initialized()

        action = "slack_sync"
        try:
            self.audit.log(
                action,
                "started",
                {"project": project_name, "since": since, "query": query, "run_id": run_id},
            )
            log_event(
                logger,
                action="slack_sync",
                status="started",
                project=project_name,
                run_id=run_id,
                since=since,
                query=query,
                json_enabled=self.json_logging,
            )

            skip_notion = enable_audit and enable_run_id and self.audit.has_run_id(run_id)
            if skip_notion:
                self.audit.log(action, "run_id_exists", {"project": project_name, "run_id": run_id})
                log_event(
                    logger,
                    action="slack_sync",
                    status="run_id_exists",
                    project=project_name,
                    run_id=run_id,
                    json_enabled=self.json_logging,
                )

            slack_method = "search" if query else "history"
            slack_start = time.monotonic()
            try:
                threads = self.collect_activity(project_name, since, query)
            except Exception as exc:
                self.audit.log_failure(action, {"project": project_name}, error=str(exc))
                raise

            slack_duration_ms = int((time.monotonic() - slack_start) * 1000)
            slack_stats = self._get_client_stats(self.slack)
            pagination_stats = self._get_pagination_stats(self.slack)

            log_event(
                logger,
                action="slack_fetch",
                status="completed",
                project=project_name,
                run_id=run_id,
                method=slack_method,
                thread_count=len(threads),
                sample_threads=[thread.thread_ts for thread in threads[:3]],
                duration_ms=slack_duration_ms,
                pagination=pagination_stats,
                slack_stats=slack_stats,
                json_enabled=self.json_logging,
            )

            self.audit.log(
                action,
                "threads_collected",
                {
                    "count": len(threads),
                    "project": project_name,
                    "method": slack_method,
                    "duration_ms": slack_duration_ms,
                    "pagination": pagination_stats,
                    "slack_stats": slack_stats,
                },
            )

            if dry_run:
                self.audit.log(action, "dry_run", {"count": len(threads), "project": project_name})
                log_event(
                    logger,
                    action="slack_sync",
                    status="dry_run",
                    project=project_name,
                    run_id=run_id,
                    thread_count=len(threads),
                    json_enabled=self.json_logging,
                )
                return

            notion_written = False
            if not skip_notion:
                if hasattr(self.notion, "reset_stats"):
                    self.notion.reset_stats()
                audit_note_page = project.get("notion_audit_page_id") or self.audit_settings.get("notion_audit_page_id")
                if enable_notion_audit_note and audit_note_page:
                    note_text = self._build_audit_note(project_name, sync_timestamp, threads, run_id, channel_id)
                    self._write_notion_audit_note(note_text, audit_note_page, run_id)
                    notion_written = True

                last_synced_page = project.get("notion_last_synced_page_id") or self.audit_settings.get(
                    "notion_last_synced_page_id"
                )
                if enable_notion_last_synced and last_synced_page:
                    property_name = self.audit_settings.get("notion_last_synced_property", "Last Synced")
                    self._update_notion_last_synced(last_synced_page, property_name, sync_timestamp, run_id)
                    notion_written = True

                if enable_audit and enable_run_id and notion_written:
                    self.audit.record_run_id(
                        run_id,
                        project_name,
                        status="notion_written",
                        details={"since": since, "query": query},
                    )

            if enable_slack_topic_update:
                slack_topic_start = time.monotonic()
                self._update_slack_last_synced(channel_id, sync_timestamp)
                log_event(
                    logger,
                    action="slack_topic_update",
                    status="completed",
                    project=project_name,
                    run_id=run_id,
                    duration_ms=int((time.monotonic() - slack_topic_start) * 1000),
                    json_enabled=self.json_logging,
                )

            self.audit.log(action, "completed", {"project": project_name, "threads": len(threads), "run_id": run_id})
            log_event(
                logger,
                action="slack_sync",
                status="completed",
                project=project_name,
                run_id=run_id,
                thread_count=len(threads),
                json_enabled=self.json_logging,
            )
        finally:
            if previous_audit_enabled != enable_audit:
                self.audit.enabled = previous_audit_enabled

    def _build_audit_note(
        self,
        project_name: str,
        sync_timestamp: str,
        threads: list[Thread],
        run_id: str,
        channel_id: str,
    ) -> str:
        channel_name = self._get_channel_name(channel_id)
        header = [
            f"Run ID: {run_id}",
            f"Channel: {channel_name or channel_id}",
            f"Sync completed for {project_name} at {sync_timestamp}.",
            f"Threads collected: {len(threads)}.",
        ]

        lines = []
        for thread in threads[:5]:
            preview = thread.preview(100).replace("\n", " ")
            user_name = self._resolve_user_name(thread.user_id) if thread.user_id else "unknown"
            line = f"- {thread.created_at or 'unknown'} | {user_name} | {preview}"
            if thread.permalink:
                line += f" | {thread.permalink}"
            lines.append(line)

        if not lines:
            lines.append("- No threads collected")

        return "\n".join(header + ["Top threads:"] + lines)

    def _write_notion_audit_note(self, note_text: str, page_id: str, run_id: str) -> None:
        action = "notion_audit_note"
        supports_verification = getattr(self.notion, "supports_verification", True)
        try:
            start_time = time.monotonic()
            block_id = self.notion.append_audit_note(page_id, note_text)
            if supports_verification:
                block = self.notion.get_block(block_id)
                verified = self._verify_notion_block(block, note_text)
                if not verified:
                    self.audit.log_review(
                        action,
                        {"page_id": page_id, "block_id": block_id, "run_id": run_id},
                        error="Note verification failed",
                    )
                    return
                self.audit.log(action, "completed", {"page_id": page_id, "block_id": block_id, "run_id": run_id})
            else:
                self.audit.log_review(
                    action,
                    {"page_id": page_id, "block_id": block_id, "run_id": run_id},
                    error="Browser fallback used; verify audit note manually",
                )
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log_event(
                logger,
                action="notion_audit_note",
                status="completed",
                project=None,
                run_id=run_id,
                page_id=page_id,
                block_id=block_id,
                duration_ms=duration_ms,
                notion_stats=self._get_client_stats(self.notion),
                json_enabled=self.json_logging,
            )
        except Exception as exc:
            if isinstance(self.notion, NotionBrowserClient):
                self.audit.log_review(action, {"page_id": page_id, "run_id": run_id}, error=str(exc))
                log_event(
                    logger,
                    action="notion_audit_note",
                    status="review",
                    project=None,
                    run_id=run_id,
                    page_id=page_id,
                    error=str(exc),
                    json_enabled=self.json_logging,
                )
                return
            self.audit.log_failure(action, {"page_id": page_id, "run_id": run_id}, error=str(exc))
            log_event(
                logger,
                action="notion_audit_note",
                status="failed",
                project=None,
                run_id=run_id,
                page_id=page_id,
                error=str(exc),
                json_enabled=self.json_logging,
            )
            raise

    def _verify_notion_block(self, block: dict, expected_text: str) -> bool:
        if not block or block.get("type") != "paragraph":
            return False
        rich_text = block.get("paragraph", {}).get("rich_text", [])
        text = "".join([item.get("plain_text", "") for item in rich_text])
        return expected_text.strip() == text.strip()

    def _update_notion_last_synced(self, page_id: str, property_name: str, sync_timestamp: str, run_id: str) -> None:
        action = "notion_last_synced"
        supports_update = getattr(self.notion, "supports_last_synced_update", True)
        try:
            start_time = time.monotonic()
            if not supports_update:
                self.audit.log_review(
                    action,
                    {"page_id": page_id, "expected": sync_timestamp, "run_id": run_id},
                    error="Browser fallback does not support Last Synced updates yet",
                )
                log_event(
                    logger,
                    action="notion_last_synced",
                    status="review",
                    project=None,
                    run_id=run_id,
                    page_id=page_id,
                    expected=sync_timestamp,
                    json_enabled=self.json_logging,
                )
                return

            self.notion.update_page_property(page_id, property_name, sync_timestamp)
            page = self.notion.get_page(page_id)
            actual = self._extract_notion_date(page, property_name)
            if actual != sync_timestamp:
                self.audit.log_review(
                    action,
                    {"page_id": page_id, "expected": sync_timestamp, "actual": actual, "run_id": run_id},
                    error="Last Synced verification failed",
                )
                log_event(
                    logger,
                    action="notion_last_synced",
                    status="review",
                    project=None,
                    run_id=run_id,
                    page_id=page_id,
                    expected=sync_timestamp,
                    actual=actual,
                    json_enabled=self.json_logging,
                )
                return
            self.audit.log(action, "completed", {"page_id": page_id, "value": sync_timestamp, "run_id": run_id})
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log_event(
                logger,
                action="notion_last_synced",
                status="completed",
                project=None,
                run_id=run_id,
                page_id=page_id,
                value=sync_timestamp,
                duration_ms=duration_ms,
                notion_stats=self._get_client_stats(self.notion),
                json_enabled=self.json_logging,
            )
        except Exception as exc:
            if isinstance(self.notion, NotionBrowserClient):
                self.audit.log_review(action, {"page_id": page_id, "run_id": run_id}, error=str(exc))
                log_event(
                    logger,
                    action="notion_last_synced",
                    status="review",
                    project=None,
                    run_id=run_id,
                    page_id=page_id,
                    error=str(exc),
                    json_enabled=self.json_logging,
                )
                return
            self.audit.log_failure(action, {"page_id": page_id, "run_id": run_id}, error=str(exc))
            log_event(
                logger,
                action="notion_last_synced",
                status="failed",
                project=None,
                run_id=run_id,
                page_id=page_id,
                error=str(exc),
                json_enabled=self.json_logging,
            )
            raise

    def _extract_notion_date(self, page: dict, property_name: str) -> str | None:
        properties: dict[str, Any] = page.get("properties", {})
        prop = properties.get(property_name, {})
        date = prop.get("date") if isinstance(prop, dict) else None
        return date.get("start") if isinstance(date, dict) else None

    def _update_slack_last_synced(self, channel_id: str, sync_timestamp: str) -> None:
        action = "slack_last_synced"
        topic = f"Last Synced: {sync_timestamp}"
        try:
            self.slack.update_channel_topic(channel_id, topic)
            channel = self.slack.get_channel_info(channel_id)
            current_topic = channel.get("topic", {}).get("value")
            if current_topic != topic:
                self.audit.log_review(
                    action,
                    {"channel_id": channel_id, "expected": topic, "actual": current_topic},
                    error="Slack topic verification failed",
                )
                return
            self.audit.log(action, "completed", {"channel_id": channel_id, "value": topic})
        except Exception as exc:
            self.audit.log_failure(action, {"channel_id": channel_id}, error=str(exc))
            raise

    def _get_channel_name(self, channel_id: str) -> str | None:
        try:
            info = self.slack.get_channel_info(channel_id)
        except Exception:
            return None
        return info.get("name") or info.get("name_normalized")

    def _get_client_stats(self, client: object) -> dict[str, Any]:
        if hasattr(client, "get_stats"):
            return cast(dict[str, Any], client.get_stats())
        return {}

    def _get_pagination_stats(self, client: object) -> dict[str, Any]:
        if hasattr(client, "get_pagination_stats"):
            return cast(dict[str, Any], client.get_pagination_stats())
        return {}

    def _resolve_user_name(self, user_id: str) -> str:
        if not user_id:
            return "unknown"
        cached = self.audit.get_user_name(user_id)
        if cached:
            return cached
        try:
            user = self.slack.get_user_info(user_id)
            real_name = user.get("real_name", "")
            display_name = user.get("name", "")
            self.audit.set_user_name(user_id, real_name, display_name)
            return real_name or display_name or user_id
        except Exception:
            return user_id

    def run_summarize(self, since: str | None = None, concurrency: int = 5) -> str:
        projects = self.config.get("projects", [])
        project_names = [p["name"] for p in projects]
        activity_map: dict[str, list[Thread]] = {}

        def fetch_one(p_name: str) -> tuple[str, list[Thread]]:
            try:
                return p_name, self.collect_activity(project_name=p_name, since=since)
            except Exception:
                return p_name, []

        if concurrency > 1 and len(project_names) > 1:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                results = executor.map(fetch_one, project_names)
                for name, threads in results:
                    if threads:
                        activity_map[name] = threads
        else:
            for name in project_names:
                project_name, threads = fetch_one(name)
                if threads:
                    activity_map[project_name] = threads

        summarizer = ActivitySummarizer(self)
        return summarizer.synthesize_standup(activity_map)

    def run_ticket_update(self, project_name: str, since: str | None = None) -> str:
        """
        Fetches activity for a project, generates a summary,
        and updates the corresponding Notion ticket.
        """
        database_id = os.getenv("NOTION_TICKETS_DATABASE_ID") or self.audit_settings.get("notion_tickets_database_id")
        builds_db_id = os.getenv("NOTION_BUILDS_DATABASE_ID") or self.audit_settings.get("notion_builds_database_id")
        
        database_ids = [db for db in [database_id, builds_db_id] if db]
        if not database_ids:
            return "Error: No Notion Database IDs found in ENV or config.json"

        # 1. Collect activity
        project = get_project(self.config, project_name)
        if not project:
            return f"Project '{project_name}' not found in config.json"

        threads = self.collect_activity(project_name, since=since)
        if not threads:
            return f"No activity found for {project_name}"

        # 2. Format a concise summary
        activity_map = {project_name: threads}
        summarizer = ActivitySummarizer(self)
        summary_text = summarizer.format_activity(activity_map)

        # 3. Update Notion
        manager = TicketManager(cast(NotionClient, self.notion))
        notion_url = project.get("notion_page_url")
        return manager.update_project_ticket(project_name, summary_text, database_ids, notion_page_id_or_url=notion_url)


    def collect_activity(
        self,
        project_name: str,
        since: str | None = None,
        query: str | None = None,
    ) -> list[Thread]:
        project = get_project(self.config, project_name)
        if not project:
            return []

        channel_id = project.get("slack_channel_id") or self.slack_settings.get("default_channel_id")
        if not channel_id:
            return []

        pagination_defaults = self.slack_settings.get("pagination", {})
        pagination_overrides = project.get("slack_pagination") or {}
        pagination = {**pagination_defaults, **pagination_overrides}
        history_limit = _coerce_int(pagination.get("history_limit"), 200)
        history_max_pages = _coerce_int(pagination.get("history_max_pages"), 5)
        search_limit = _coerce_int(pagination.get("search_limit"), 100)
        search_max_pages = _coerce_int(pagination.get("search_max_pages"), 3)

        oldest = iso_to_unix_ts(since) if since else None

        if hasattr(self.slack, "reset_stats"):
            self.slack.reset_stats()

        if query:
            return self.thread_extractor.search_threads(
                query=query,
                channel_id=channel_id,
                limit=search_limit,
                max_pages=search_max_pages,
            )
        else:
            return self.thread_extractor.fetch_channel_threads(
                channel_id=channel_id,
                oldest=oldest,
                limit=history_limit,
                max_pages=history_max_pages,
            )

    def close(self) -> None:
        if not self.browser_session:
            return
        if self.browser_config.keep_open:
            logger.info("Keeping browser session open (keep_open enabled).")
            return
        try:
            self.browser_session.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Scalers Slack Automation")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--project", help="Project name from config.json")
    parser.add_argument("--all", action="store_true", help="Sync all projects in config.json")
    parser.add_argument("--since", help="ISO8601 timestamp (e.g. 2024-01-01T00:00:00Z)")
    parser.add_argument("--query", help="Slack search query")
    parser.add_argument("--dry-run", action="store_true", help="Collect threads but skip writes")
    parser.add_argument("--validate-config", action="store_true", help="Validate config and exit")
    parser.add_argument("--summarize", action="store_true", help="Generate an AI standup report")
    parser.add_argument("--update-tickets", action="store_true", help="Update Notion tickets with project activity")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of projects to sync in parallel")
    parser.add_argument("--verbose-browser", action="store_true", help="Enable verbose browser logging")
    parser.add_argument(
        "--keep-browser-open",
        action="store_true",
        help="Keep the browser session open after the run (useful for debugging)",
    )
    parser.add_argument(
        "--refresh-storage-state",
        action="store_true",
        help="Allow interactive login to refresh browser storage state",
    )
    parser.add_argument("--browser-channel", help="Browser channel (e.g. chrome, msedge)")
    parser.add_argument("--user-data-dir", help="Persistent browser profile directory")
    parser.add_argument("--recordings-dir", help="Directory for browser recordings (screenshots)")
    parser.add_argument("--event-log-path", help="Path for browser event log (JSONL)")
    parser.add_argument("--screenshot-on-step", action="store_true", help="Screenshot after successful actions")
    parser.add_argument("--no-screenshot-on-error", action="store_true", help="Disable screenshots on errors")
    parser.add_argument("--smart-wait", action="store_true", help="Enable smart wait for page stability")
    parser.add_argument("--no-smart-wait", action="store_true", help="Disable smart wait for page stability")
    parser.add_argument("--overlay", action="store_true", help="Show browser status overlay")
    parser.add_argument("--auto-recover", action="store_true", help="Enable auto-recovery on failures")
    parser.add_argument("--no-auto-recover", action="store_true", help="Disable auto-recovery on failures")
    headless_group = parser.add_mutually_exclusive_group()
    headless_group.add_argument("--headless", action="store_true", help="Force headless browser mode")
    headless_group.add_argument("--headed", action="store_true", help="Force headed browser mode")

    args = parser.parse_args()
    if args.validate_config:
        config = load_config(args.config)
        validate_or_raise(config)
        print("Config OK")
        return

    if not args.project and not args.all and not args.summarize:
        parser.error("Either --project, --all, or --summarize is required unless --validate-config is used")

    config = load_config(args.config)
    browser_overrides: dict[str, Any] = {}
    if args.verbose_browser:
        browser_overrides["verbose_logging"] = True
    if args.keep_browser_open:
        browser_overrides["keep_open"] = True
    if args.refresh_storage_state:
        browser_overrides["interactive_login"] = True
        browser_overrides["auto_save_storage_state"] = True
    if args.headless:
        browser_overrides["headless"] = True
    if args.headed:
        browser_overrides["headless"] = False
    if args.browser_channel:
        browser_overrides["browser_channel"] = args.browser_channel
    if args.user_data_dir:
        browser_overrides["user_data_dir"] = args.user_data_dir
    if args.recordings_dir:
        browser_overrides["recordings_dir"] = args.recordings_dir
    if args.event_log_path:
        browser_overrides["event_log_path"] = args.event_log_path
    if args.screenshot_on_step:
        browser_overrides["screenshot_on_step"] = True
    if args.no_screenshot_on_error:
        browser_overrides["screenshot_on_error"] = False
    if args.smart_wait:
        browser_overrides["smart_wait"] = True
    if args.no_smart_wait:
        browser_overrides["smart_wait"] = False
    if args.overlay:
        browser_overrides["overlay_enabled"] = True
    if args.auto_recover:
        browser_overrides["auto_recover"] = True
    if args.no_auto_recover:
        browser_overrides["auto_recover"] = False
    if browser_overrides:
        config = _deep_merge(
            config,
            {"settings": {"browser_automation": browser_overrides}},
        )

    engine = ScalersSlackEngine(config_path=args.config, config=config)
    try:
        if args.summarize:
            report_prompt = engine.run_summarize(since=args.since, concurrency=args.concurrency)
            print(report_prompt)
            return

        if args.update_tickets:
            if args.all:
                projects = config.get("projects", [])
                for p in projects:
                    res = engine.run_ticket_update(p["name"], since=args.since)
                    print(f"[{p['name']}] {res}")
            elif args.project:
                print(engine.run_ticket_update(args.project, since=args.since))
            else:
                parser.error("--update-tickets requires --project or --all")
            return

        if args.all:
            projects_to_run = [p["name"] for p in config.get("projects", [])]
        else:
            projects_to_run = [args.project] if args.project else []

        if not projects_to_run:
            print("No projects to run.")
            return

        def sync_one(p_name: str) -> None:
            try:
                engine.run_sync(project_name=p_name, since=args.since, query=args.query, dry_run=args.dry_run)
            except Exception as exc:
                print(f"Error syncing project '{p_name}': {exc}", file=sys.stderr)

        if args.concurrency > 1 and len(projects_to_run) > 1:
            with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                executor.map(sync_one, projects_to_run)
        else:
            for project_name in projects_to_run:
                sync_one(project_name)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
