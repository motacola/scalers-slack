from __future__ import annotations

import logging
import re

from .notion_client import NotionBrowserClient
from .slack_client import SlackBrowserClient

logger = logging.getLogger(__name__)


class SlackNotionCrossReferencer:
    """
    Cross-references Slack messages with Notion tickets.
    Enables finding related tickets for Slack conversations and vice versa.
    """

    def __init__(
        self,
        slack_client: SlackBrowserClient,
        notion_client: NotionBrowserClient,
        config: dict,
    ):
        self.slack = slack_client
        self.notion = notion_client
        self.config = config
        self.hub_url = config.get("settings", {}).get("notion_hub", {}).get("url", "")
        self.stats = {
            "tickets_found": 0,
            "tickets_updated": 0,
            "cross_references_created": 0,
        }

    def find_ticket_for_channel(self, channel_name: str) -> dict | None:
        """
        Find a Notion ticket that corresponds to a Slack channel.
        Uses channel name to search Notion.
        """
        # Clean up channel name for search
        search_terms = channel_name.replace("ss-", "").replace("-", " ")

        # Remove common suffixes
        for suffix in ["website hosting", "website management", "seo", "ppc", "gbp", "lsa"]:
            search_terms = search_terms.replace(suffix, "").strip()

        if not search_terms:
            return None

        # Search Notion for matching ticket
        ticket = self.notion.find_ticket_by_name(search_terms, hub_url=self.hub_url)
        if ticket:
            self.stats["tickets_found"] += 1

        return ticket

    def link_slack_thread_to_ticket(
        self,
        thread_permalink: str,
        ticket_page_id: str,
        summary: str | None = None,
    ) -> bool:
        """
        Add a Slack thread link to a Notion ticket as a note.
        """
        note_text = f"Slack Thread: {thread_permalink}"
        if summary:
            note_text = f"{summary}\n\nSlack Thread: {thread_permalink}"

        try:
            self.notion.append_audit_note(ticket_page_id, note_text)
            self.stats["cross_references_created"] += 1
            return True
        except Exception as e:
            logger.warning(f"Failed to link Slack thread to ticket: {e}")
            return False

    def sync_channel_activity_to_ticket(
        self,
        channel_id: str,
        channel_name: str,
        threads: list,
        ticket_url: str | None = None,
    ) -> dict:
        """
        Sync Slack channel activity to the corresponding Notion ticket.
        Creates a summary and links to relevant threads.
        """
        result = {
            "channel": channel_name,
            "threads_processed": 0,
            "ticket_found": False,
            "ticket_updated": False,
        }

        # Find or use provided ticket
        ticket = None
        if ticket_url:
            ticket = self.notion.extract_page_content(ticket_url)
        else:
            ticket = self.find_ticket_for_channel(channel_name)

        if not ticket:
            logger.info(f"No ticket found for channel: {channel_name}")
            return result

        result["ticket_found"] = True
        result["ticket_url"] = ticket.get("url", "")

        # Build activity summary
        if not threads:
            return result

        summary_lines = [
            "--- Slack Activity Summary ---",
            f"Channel: #{channel_name}",
            f"Threads: {len(threads)}",
            "",
        ]

        for thread in threads[:5]:  # Top 5 threads
            preview = thread.preview(100) if hasattr(thread, "preview") else str(thread)[:100]
            permalink = getattr(thread, "permalink", "") or ""
            summary_lines.append(f"• {preview}")
            if permalink:
                summary_lines.append(f"  Link: {permalink}")
            summary_lines.append("")

        summary_text = "\n".join(summary_lines)

        # Append to ticket
        try:
            page_id = self._extract_page_id(ticket.get("url", ""))
            if page_id:
                self.notion.append_audit_note(page_id, summary_text)
                result["ticket_updated"] = True
                result["threads_processed"] = min(len(threads), 5)
                self.stats["tickets_updated"] += 1
        except Exception as e:
            logger.warning(f"Failed to update ticket: {e}")

        return result

    def _extract_page_id(self, url: str) -> str | None:
        """Extract Notion page ID from URL."""
        # Match 32-character hex ID at the end of URL
        match = re.search(r"([a-f0-9]{32})(?:\?|$)", url.replace("-", ""))
        if match:
            return match.group(1)

        # Match dashed format
        match = re.search(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", url)
        if match:
            return match.group(1).replace("-", "")

        return None

    def get_stats(self) -> dict:
        """Get cross-referencing statistics."""
        return dict(self.stats)

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = {
            "tickets_found": 0,
            "tickets_updated": 0,
            "cross_references_created": 0,
        }
