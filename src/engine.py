import argparse
import logging
import os
from typing import Any

from .audit_logger import AuditLogger
from .config_loader import load_config, get_project
from .notion_client import NotionClient
from .slack_client import SlackClient
from .thread_extractor import ThreadExtractor
from .utils import iso_to_unix_ts, utc_now_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _coerce_int(value: object, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class ScalersSlackEngine:
    def __init__(
        self,
        config_path: str = "config.json",
        slack_client: SlackClient | None = None,
        notion_client: NotionClient | None = None,
        audit_logger: AuditLogger | None = None,
        thread_extractor: ThreadExtractor | None = None,
    ):
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config = load_config(config_path)

        slack_settings = self.config["settings"]["slack"]
        notion_settings = self.config["settings"]["notion"]
        audit_settings = self.config["settings"]["audit"]

        slack_token = os.getenv(slack_settings.get("token_env", "SLACK_BOT_TOKEN"))
        notion_token = os.getenv(notion_settings.get("token_env", "NOTION_API_KEY"))

        self.slack = slack_client or SlackClient(token=slack_token, base_url=slack_settings["base_url"])
        self.notion = notion_client or NotionClient(token=notion_token, version=notion_settings["version"])
        self.audit = audit_logger or AuditLogger(
            enabled=audit_settings.get("enabled", True),
            storage_dir=audit_settings.get("storage_dir", "audit"),
            sqlite_path=audit_settings.get("sqlite_path", "audit/audit.db"),
            jsonl_path=audit_settings.get("jsonl_path", "audit/audit.jsonl"),
        )
        self.thread_extractor = thread_extractor or ThreadExtractor(self.slack)
        self.audit_settings = audit_settings
        self.slack_settings = slack_settings

    def run_sync(self, project_name: str, since: str | None = None, query: str | None = None, dry_run: bool = False) -> None:
        project = get_project(self.config, project_name)
        if not project:
            raise RuntimeError(f"Project '{project_name}' not found in config.json")

        channel_id = project.get("slack_channel_id") or self.slack_settings.get("default_channel_id")
        if not channel_id:
            raise RuntimeError("Slack channel ID is required in config.json")

        pagination_defaults = self.slack_settings.get("pagination", {})
        pagination_overrides = project.get("slack_pagination") or {}
        pagination = {**pagination_defaults, **pagination_overrides}
        history_limit = _coerce_int(pagination.get("history_limit"), 200)
        history_max_pages = _coerce_int(pagination.get("history_max_pages"), 10)
        search_limit = _coerce_int(pagination.get("search_limit"), 100)
        search_max_pages = _coerce_int(pagination.get("search_max_pages"), 5)

        oldest = iso_to_unix_ts(since) if since else None
        sync_timestamp = utc_now_iso()

        action = "slack_sync"
        self.audit.log(action, "started", {"project": project_name, "since": since, "query": query})

        threads = []
        try:
            if query:
                threads = self.thread_extractor.search_threads(
                    query=query,
                    channel_id=channel_id,
                    limit=search_limit,
                    max_pages=search_max_pages,
                )
            else:
                threads = self.thread_extractor.fetch_channel_threads(
                    channel_id=channel_id,
                    oldest=oldest,
                    limit=history_limit,
                    max_pages=history_max_pages,
                )
        except Exception as exc:
            self.audit.log_failure(action, {"project": project_name}, error=str(exc))
            raise

        logger.info("Found %s threads", len(threads))
        self.audit.log(action, "threads_collected", {"count": len(threads), "project": project_name})

        if dry_run:
            self.audit.log(action, "dry_run", {"count": len(threads), "project": project_name})
            return

        audit_note_page = project.get("notion_audit_page_id") or self.audit_settings.get("notion_audit_page_id")
        if audit_note_page:
            note_text = self._build_audit_note(project_name, sync_timestamp, threads)
            self._write_notion_audit_note(note_text, audit_note_page)

        last_synced_page = project.get("notion_last_synced_page_id") or self.audit_settings.get("notion_last_synced_page_id")
        if last_synced_page:
            property_name = self.audit_settings.get("notion_last_synced_property", "Last Synced")
            self._update_notion_last_synced(last_synced_page, property_name, sync_timestamp)

        self._update_slack_last_synced(channel_id, sync_timestamp)
        self.audit.log(action, "completed", {"project": project_name, "threads": len(threads)})

    def _build_audit_note(self, project_name: str, sync_timestamp: str, threads: list[dict]) -> str:
        sample = ", ".join([t["thread_ts"] for t in threads[:5]])
        sample_text = sample if sample else "No threads collected"
        return (
            f"Sync completed for {project_name} at {sync_timestamp}. "
            f"Threads collected: {len(threads)}. Sample thread_ts: {sample_text}."
        )

    def _write_notion_audit_note(self, note_text: str, page_id: str) -> None:
        action = "notion_audit_note"
        try:
            block_id = self.notion.append_audit_note(page_id, note_text)
            block = self.notion.get_block(block_id)
            verified = self._verify_notion_block(block, note_text)
            if not verified:
                self.audit.log_review(action, {"page_id": page_id, "block_id": block_id}, error="Note verification failed")
                return
            self.audit.log(action, "completed", {"page_id": page_id, "block_id": block_id})
        except Exception as exc:
            self.audit.log_failure(action, {"page_id": page_id}, error=str(exc))
            raise

    def _verify_notion_block(self, block: dict, expected_text: str) -> bool:
        if not block or block.get("type") != "paragraph":
            return False
        rich_text = block.get("paragraph", {}).get("rich_text", [])
        text = "".join([item.get("plain_text", "") for item in rich_text])
        return expected_text.strip() == text.strip()

    def _update_notion_last_synced(self, page_id: str, property_name: str, sync_timestamp: str) -> None:
        action = "notion_last_synced"
        try:
            self.notion.update_page_property(page_id, property_name, sync_timestamp)
            page = self.notion.get_page(page_id)
            actual = self._extract_notion_date(page, property_name)
            if actual != sync_timestamp:
                self.audit.log_review(
                    action,
                    {"page_id": page_id, "expected": sync_timestamp, "actual": actual},
                    error="Last Synced verification failed",
                )
                return
            self.audit.log(action, "completed", {"page_id": page_id, "value": sync_timestamp})
        except Exception as exc:
            self.audit.log_failure(action, {"page_id": page_id}, error=str(exc))
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Scalers Slack Automation")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--project", required=True, help="Project name from config.json")
    parser.add_argument("--since", help="ISO8601 timestamp (e.g. 2024-01-01T00:00:00Z)")
    parser.add_argument("--query", help="Slack search query")
    parser.add_argument("--dry-run", action="store_true", help="Collect threads but skip writes")

    args = parser.parse_args()
    engine = ScalersSlackEngine(config_path=args.config)
    engine.run_sync(project_name=args.project, since=args.since, query=args.query, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
