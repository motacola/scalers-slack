import re

from .notion_client import NotionClient

NOTION_ID_RE = re.compile(r"[0-9a-fA-F]{32}")
NOTION_ID_DASHED_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


class TicketManager:
    def __init__(self, notion: NotionClient):
        self.notion = notion

    def update_project_ticket(
        self,
        project_name: str,
        summary: str,
        database_ids: list[str],
        notion_page_id_or_url: str | None = None,
    ) -> str:
        """
        Finds a ticket/page in the provided databases matching the project name and updates it.
        If notion_page_id_or_url is provided, it skips the search and updates the page directly.
        """
        if notion_page_id_or_url:
            page_id = self._normalize_page_id(notion_page_id_or_url)
            if not page_id:
                return f"Invalid Notion page ID/URL for {project_name}"
            try:
                self.notion.append_audit_note(page_id, f"--- AI Sync Update ---\n{summary}")
                return f"Updated ticket for {project_name} using direct URL/ID"
            except Exception as e:
                return f"Failed to update ticket using direct URL/ID for {project_name}: {e}"

        for database_id in database_ids:
            if not database_id:
                continue

            # 1. Search for matching page using a filter on the 'Name' or 'Client' property
            # Some databases use 'Client', some use 'Name'
            for property_name in ["Client", "Name"]:
                filter_query = {"property": property_name, "title": {"contains": project_name}}
                try:
                    results = self.notion.query_database(database_id, filter=filter_query)
                    if results:
                        page_id = results[0]["id"]
                        self.notion.append_audit_note(page_id, f"--- AI Sync Update ---\n{summary}")
                        return f"Updated ticket for {project_name} in database {database_id}"
                except Exception:
                    continue

        return f"No ticket found for {project_name} in checked databases"

    def _normalize_page_id(self, value: str) -> str | None:
        dashed_match = NOTION_ID_DASHED_RE.search(value)
        if dashed_match:
            return dashed_match.group(0).replace("-", "")
        raw_match = NOTION_ID_RE.search(value)
        if raw_match:
            return raw_match.group(0)
        return None
