import logging
import re
from typing import Any, Protocol, cast, runtime_checkable

NOTION_ID_RE = re.compile(r"[0-9a-fA-F]{32}")
NOTION_ID_DASHED_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

logger = logging.getLogger(__name__)


@runtime_checkable
class NotionClientProtocol(Protocol):
    """Protocol for Notion clients (API or Browser-based)."""

    def append_audit_note(self, page_id: str, text: str) -> str: ...
    def query_database(self, database_id: str, filter: dict | None = None) -> list[dict]: ...


@runtime_checkable
class NotionBrowserClientProtocol(Protocol):
    """Extended protocol for browser-based Notion client."""

    def append_audit_note(self, page_id: str, text: str) -> str: ...
    def search_pages_browser(self, query: str, max_results: int = 10) -> list[dict]: ...
    def find_ticket_by_name(self, project_name: str, hub_url: str | None = None) -> dict | None: ...
    def extract_page_content(self, page_id_or_url: str) -> dict: ...


class TicketManager:
    """
    Manages Notion ticket updates with support for both API and browser-based clients.
    Automatically detects client type and uses appropriate methods.
    """

    def __init__(self, notion: Any, hub_url: str | None = None):
        self.notion = notion
        self.hub_url = hub_url
        self._is_browser_client = hasattr(notion, "search_pages_browser")

    def update_project_ticket(
        self,
        project_name: str,
        summary: str,
        database_ids: list[str],
        notion_page_id_or_url: str | None = None,
    ) -> str:
        """
        Finds a ticket/page matching the project name and updates it.
        Supports both API-based and browser-based Notion clients.

        Args:
            project_name: Name of the project to find
            summary: Summary text to append as an audit note
            database_ids: List of database IDs to search (API mode)
            notion_page_id_or_url: Direct page ID or URL (skips search)

        Returns:
            Status message indicating success or failure
        """
        # If direct URL/ID provided, use it directly
        if notion_page_id_or_url:
            return self._update_by_direct_url(project_name, summary, notion_page_id_or_url)

        # Use browser-based search if available (no API key scenario)
        if self._is_browser_client:
            return self._update_via_browser_search(project_name, summary)

        # Fall back to API-based database query
        return self._update_via_api_search(project_name, summary, database_ids)

    def _update_by_direct_url(self, project_name: str, summary: str, notion_page_id_or_url: str) -> str:
        """Update ticket using direct page ID or URL."""
        page_id = self._normalize_page_id(notion_page_id_or_url)
        if not page_id:
            # For browser client, we can use the full URL
            if self._is_browser_client and notion_page_id_or_url.startswith("http"):
                page_id = notion_page_id_or_url
            else:
                return f"Invalid Notion page ID/URL for {project_name}"

        try:
            self.notion.append_audit_note(page_id, f"--- AI Sync Update ---\n{summary}")
            logger.info(f"Updated ticket for {project_name} using direct URL/ID")
            return f"Updated ticket for {project_name} using direct URL/ID"
        except Exception as e:
            logger.error(f"Failed to update ticket for {project_name}: {e}")
            return f"Failed to update ticket using direct URL/ID for {project_name}: {e}"

    def _update_via_browser_search(self, project_name: str, summary: str) -> str:
        """Update ticket using browser-based Notion search."""
        try:
            # Clean up project name for search
            search_name = self._clean_project_name(project_name)
            logger.info(f"Browser search for ticket: {search_name}")

            # Use browser search to find ticket
            ticket = self.notion.find_ticket_by_name(search_name, hub_url=self.hub_url)

            if not ticket:
                # Try with original name
                ticket = self.notion.find_ticket_by_name(project_name, hub_url=self.hub_url)

            if not ticket:
                logger.warning(f"No ticket found for {project_name} via browser search")
                return f"No ticket found for {project_name} via browser search"

            # Get page URL or ID
            page_url = ticket.get("url", "")
            if not page_url:
                return f"Ticket found but no URL available for {project_name}"

            # Append audit note
            self.notion.append_audit_note(page_url, f"--- AI Sync Update ---\n{summary}")
            logger.info(f"Updated ticket for {project_name} via browser search")
            return f"Updated ticket for {project_name} via browser search"

        except Exception as e:
            logger.error(f"Browser-based ticket update failed for {project_name}: {e}")
            return f"Failed to update ticket for {project_name}: {e}"

    def _update_via_api_search(self, project_name: str, summary: str, database_ids: list[str]) -> str:
        """Update ticket using API-based database query."""
        for database_id in database_ids:
            if not database_id:
                continue

            # Search for matching page using a filter on 'Name' or 'Client' property
            for property_name in ["Client", "Name"]:
                filter_query = {"property": property_name, "title": {"contains": project_name}}
                try:
                    results = self.notion.query_database(database_id, filter=filter_query)
                    if results:
                        page_id = results[0]["id"]
                        self.notion.append_audit_note(page_id, f"--- AI Sync Update ---\n{summary}")
                        logger.info(f"Updated ticket for {project_name} in database {database_id}")
                        return f"Updated ticket for {project_name} in database {database_id}"
                except Exception as e:
                    logger.debug(f"Query failed for {property_name} in {database_id}: {e}")
                    continue

        return f"No ticket found for {project_name} in checked databases"

    def find_ticket(
        self,
        project_name: str,
        database_ids: list[str] | None = None,
    ) -> dict | None:
        """
        Find a ticket by project name without updating it.

        Args:
            project_name: Name of the project to find
            database_ids: List of database IDs to search (API mode)

        Returns:
            Ticket data dict or None if not found
        """
        if self._is_browser_client:
            search_name = self._clean_project_name(project_name)
            ticket = self.notion.find_ticket_by_name(search_name, hub_url=self.hub_url)
            if not ticket:
                ticket = self.notion.find_ticket_by_name(project_name, hub_url=self.hub_url)
            return cast(dict, ticket) if ticket is not None else None

        # API-based search
        if not database_ids:
            return None

        for database_id in database_ids:
            if not database_id:
                continue

            for property_name in ["Client", "Name"]:
                filter_query = {"property": property_name, "title": {"contains": project_name}}
                try:
                    results = self.notion.query_database(database_id, filter=filter_query)
                    if results:
                        return cast(dict, results[0])
                except Exception:
                    continue

        return None

    def get_ticket_details(self, ticket_url_or_id: str) -> dict:
        """
        Get full details of a ticket.

        Args:
            ticket_url_or_id: Notion page URL or ID

        Returns:
            Ticket details dict with properties and content
        """
        if self._is_browser_client:
            return cast(dict, self.notion.extract_page_content(ticket_url_or_id))

        # API-based retrieval
        page_id = self._normalize_page_id(ticket_url_or_id)
        if page_id:
            try:
                return cast(dict, self.notion.get_page(page_id))
            except Exception as e:
                logger.error(f"Failed to get ticket details: {e}")

        return {}

    def list_tickets_from_hub(self, status_filter: str | None = None) -> list[dict]:
        """
        List all tickets from the Notion hub.
        Only available with browser-based client.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of ticket dicts with title, url, status
        """
        if not self._is_browser_client:
            logger.warning("list_tickets_from_hub requires browser-based Notion client")
            return []

        if not self.hub_url:
            logger.warning("Hub URL not configured")
            return []

        return cast(list, self.notion.navigate_hub_and_list_tickets(self.hub_url, status_filter))

    def _normalize_page_id(self, value: str) -> str | None:
        """Extract and normalize Notion page ID from URL or raw ID."""
        dashed_match = NOTION_ID_DASHED_RE.search(value)
        if dashed_match:
            return dashed_match.group(0).replace("-", "")
        raw_match = NOTION_ID_RE.search(value)
        if raw_match:
            return raw_match.group(0)
        return None

    def _clean_project_name(self, project_name: str) -> str:
        """
        Clean project name for better search results.
        Removes common prefixes/suffixes like 'ss-', '-website-hosting', etc.
        """
        name = project_name.lower()

        # Remove common prefixes
        prefixes = ["ss-", "ql-", "project-"]
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix) :]

        # Remove common suffixes (apply repeatedly to handle compound suffixes)
        suffixes = [
            "-website-management-and-hosting",  # Compound suffixes first
            "-website-hosting-and-management",
            "-website-hosting",
            "-website-management",
            "-website-build",
            "-website-edits",
            "-landing-pages",
            "-website",
            "-seo",
            "-ppc",
            "-gbp",
            "-lsa",
            "-meta",
            "-full-service",
            "-call-grading",
            "-and-hosting",
            "-management",
            "-hosting",
        ]

        # Keep removing suffixes until no more match
        changed = True
        while changed:
            changed = False
            for suffix in suffixes:
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    changed = True
                    break  # Restart from beginning of suffix list

        # Convert hyphens to spaces
        name = name.replace("-", " ")

        return name.strip()
