"""
BugHerd Bridge - Interface to connect Scalers Slack with BugHerd QA system.

This bridge allows the Scalers Slack engine to:
1. Fetch BugHerd tasks for a project
2. Create BugHerd tickets from Slack discussions
3. Add comments to BugHerd tickets
4. Cross-reference Slack threads with BugHerd tasks

Supports both:
- API mode (when BUGHERD_API_KEY is available)
- Browser mode (uses browser automation when no API key)
"""

import logging
import os
import sys
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Add parent directory to path to import BugHerd client
# Structure: auto-bugherd/Scalers slack/src/integrations/bugherd_bridge.py
# Parent src: auto-bugherd/src/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SCALERS_SLACK_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))  # Scalers slack/
_AUTO_BUGHERD_ROOT = os.path.dirname(_SCALERS_SLACK_ROOT)  # auto-bugherd/
_PARENT_SRC = os.path.join(_AUTO_BUGHERD_ROOT, "src")

if os.path.isdir(_PARENT_SRC) and _PARENT_SRC not in sys.path:
    sys.path.insert(0, _PARENT_SRC)


@runtime_checkable
class BugHerdClientProtocol(Protocol):
    """Protocol defining expected BugHerd client interface."""

    def create_ticket(
        self,
        project_id: str,
        description: str,
        page_url: str | None = None,
        priority: str = "normal",
        tag_names: list[str] | None = None,
        assigned_to_id: int | None = None,
        status: str = "backlog",
        title: str | None = None,
    ) -> dict | None:
        ...

    def create_ticket_comment(
        self, project_id: str, task_id: str, text: str
    ) -> dict | None:
        ...

    def update_ticket(
        self,
        project_id: str,
        task_id: str,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        tag_names: list[str] | None = None,
    ) -> dict | None:
        ...

    def get_project_members(self, project_id: str) -> list[dict] | None:
        ...

    def find_member_by_name(self, project_id: str, name: str) -> dict | None:
        ...


class BugHerdBridge:
    """
    Bridge to connect Scalers Slack engine with BugHerd QA system.

    Provides a clean interface for:
    - Creating tickets from Slack discussions
    - Adding comments to existing tickets
    - Cross-referencing Slack threads with BugHerd tasks

    Supports both API mode (with API key) and browser mode (no API key).
    """

    def __init__(
        self,
        api_key: str | None = None,
        config: dict | None = None,
        browser_client: Any = None,
    ):
        """
        Initialize the BugHerd bridge.

        Args:
            api_key: BugHerd API key (defaults to BUGHERD_API_KEY env var)
            config: Optional config dict with project mappings
            browser_client: Optional BugHerdBrowserClient for browser mode
        """
        self._api_client: Any = None
        self._browser_client: Any = browser_client
        self._api_key = api_key or os.getenv("BUGHERD_API_KEY")
        self._config = config or {}
        self._project_mapping: dict[str, str] = {}  # project_name -> bugherd_project_id
        self._mode: str = "none"  # "api", "browser", or "none"
        self._stats: dict[str, Any] = {
            "tickets_created": 0,
            "comments_added": 0,
            "errors": 0,
        }

        # Load project mappings from config
        self._load_project_mappings()

    def _load_project_mappings(self) -> None:
        """Load BugHerd project ID mappings from config."""
        projects = self._config.get("projects", [])
        for project in projects:
            name = project.get("name", "").lower()
            bugherd_id = project.get("bugherd_project_id")
            if name and bugherd_id:
                self._project_mapping[name] = str(bugherd_id)

    def set_browser_client(self, browser_client: Any) -> None:
        """
        Set browser client for browser mode.

        Args:
            browser_client: BugHerdBrowserClient instance
        """
        self._browser_client = browser_client
        if browser_client is not None:
            logger.info("BugHerd browser client set - browser mode available")

    @property
    def client(self) -> Any:
        """Get the active BugHerd client (API or browser)."""
        # Prefer API client if available
        if self._api_client is not None:
            return self._api_client

        # Try to initialize API client if we have an API key
        if self._api_key and self._api_client is None:
            self._api_client = self._load_api_client()
            if self._api_client:
                self._mode = "api"
                return self._api_client

        # Fall back to browser client
        if self._browser_client is not None:
            self._mode = "browser"
            return self._browser_client

        self._mode = "none"
        return None

    def _load_api_client(self) -> Any:
        """Load the API-based BugHerd client."""
        try:
            # Try direct import first (if parent src is in path)
            from bugherd_client import BugHerdClient
            client = BugHerdClient(api_key=self._api_key)
            logger.info("BugHerd API client initialized successfully")
            return client
        except ImportError:
            # Try alternative: load the module file directly
            try:
                import importlib.util
                bugherd_path = os.path.join(_PARENT_SRC, "bugherd_client.py")
                if os.path.exists(bugherd_path):
                    spec = importlib.util.spec_from_file_location(
                        "bugherd_client", bugherd_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        client = module.BugHerdClient(api_key=self._api_key)
                        logger.info("BugHerd API client initialized via direct load")
                        return client
            except Exception as e:
                logger.debug(f"Could not load API client directly: {e}")
        except Exception as e:
            logger.debug(f"Could not initialize API client: {e}")

        return None

    @property
    def is_available(self) -> bool:
        """Check if BugHerd integration is available (API or browser mode)."""
        # Check API mode
        if self._api_key:
            client = self._load_api_client()
            if client:
                return True

        # Check browser mode
        if self._browser_client is not None:
            return True

        return False

    @property
    def mode(self) -> str:
        """Get current operating mode: 'api', 'browser', or 'none'."""
        # Force client resolution to determine mode
        _ = self.client
        return self._mode

    def get_bugherd_project_id(self, project_name: str) -> str | None:
        """
        Get BugHerd project ID for a given project name.

        Args:
            project_name: Project name from Slack/Notion

        Returns:
            BugHerd project ID or None if not mapped
        """
        name_lower = project_name.lower()

        # Direct match
        if name_lower in self._project_mapping:
            return self._project_mapping[name_lower]

        # Partial match
        for key, value in self._project_mapping.items():
            if key in name_lower or name_lower in key:
                return value

        return None

    def create_ticket_from_slack(
        self,
        project_name: str,
        slack_message: str,
        slack_thread_url: str | None = None,
        page_url: str | None = None,
        priority: str = "normal",
        tags: list[str] | None = None,
        assignee_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a BugHerd ticket from a Slack message/discussion.

        Args:
            project_name: Project name to find BugHerd project
            slack_message: Message content to include in ticket
            slack_thread_url: Optional Slack thread permalink
            page_url: Optional URL of the page with the issue
            priority: Ticket priority (critical, important, normal, minor)
            tags: Optional list of tags
            assignee_name: Optional name to assign ticket to

        Returns:
            Dict with status, ticket_id, and any errors
        """
        if not self.is_available:
            return {
                "status": "error",
                "error": "BugHerd integration not available (no API key or browser session)",
            }

        project_id = self.get_bugherd_project_id(project_name)
        if not project_id:
            return {
                "status": "error",
                "error": f"No BugHerd project mapped for '{project_name}'",
            }

        # Build description
        description = f"**From Slack Discussion**\n\n{slack_message}"
        if slack_thread_url:
            description += f"\n\n---\n:speech_balloon: **Slack Thread:** {slack_thread_url}"

        # Find assignee ID if name provided (API mode only)
        assigned_to_id = None
        if assignee_name and self._mode == "api":
            member = self.client.find_member_by_name(project_id, assignee_name)
            if member:
                assigned_to_id = member.get("id")

        # Add default tags
        all_tags = ["from-slack"]
        if tags:
            all_tags.extend(tags)

        try:
            result = self.client.create_ticket(
                project_id=project_id,
                description=description,
                page_url=page_url,
                priority=priority,
                tag_names=all_tags,
                assigned_to_id=assigned_to_id,
                status="backlog",
                title=slack_message[:100].split("\n")[0],
            )

            if result:
                task_id = result.get("task", {}).get("id") or result.get("task", {}).get("title")
                self._stats["tickets_created"] += 1
                logger.info(f"Created BugHerd ticket via {self._mode}: {task_id}")
                return {
                    "status": "success",
                    "ticket_id": task_id,
                    "project_id": project_id,
                    "mode": self._mode,
                }
            else:
                self._stats["errors"] += 1
                return {
                    "status": "error",
                    "error": "Failed to create ticket",
                    "mode": self._mode,
                }

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error creating BugHerd ticket: {e}")
            return {
                "status": "error",
                "error": str(e),
                "mode": self._mode,
            }

    def add_comment_from_slack(
        self,
        project_name: str,
        task_id: str,
        comment_text: str,
        slack_user: str | None = None,
    ) -> dict[str, Any]:
        """
        Add a comment to an existing BugHerd ticket from Slack.

        Args:
            project_name: Project name to find BugHerd project
            task_id: BugHerd task ID
            comment_text: Comment content
            slack_user: Optional Slack username to attribute

        Returns:
            Dict with status and any errors
        """
        if not self.is_available:
            return {
                "status": "error",
                "error": "BugHerd integration not available",
            }

        project_id = self.get_bugherd_project_id(project_name)
        if not project_id:
            return {
                "status": "error",
                "error": f"No BugHerd project mapped for '{project_name}'",
            }

        # Format comment with Slack attribution
        full_comment = comment_text
        if slack_user:
            full_comment = f"[From Slack - @{slack_user}]\n\n{comment_text}"

        try:
            result = self.client.create_ticket_comment(
                project_id=project_id,
                task_id=task_id,
                text=full_comment,
            )

            if result:
                self._stats["comments_added"] += 1
                logger.info(f"Added comment to BugHerd ticket #{task_id} via {self._mode}")
                return {"status": "success", "task_id": task_id, "mode": self._mode}
            else:
                self._stats["errors"] += 1
                return {
                    "status": "error",
                    "error": "Failed to add comment",
                    "mode": self._mode,
                }

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error adding comment to BugHerd: {e}")
            return {
                "status": "error",
                "error": str(e),
                "mode": self._mode,
            }

    def update_ticket_status(
        self,
        project_name: str,
        task_id: str,
        status: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """
        Update a BugHerd ticket's status.

        Args:
            project_name: Project name
            task_id: BugHerd task ID
            status: New status (backlog, todo, doing, done)
            comment: Optional comment to add with status change

        Returns:
            Dict with status and any errors
        """
        if not self.is_available:
            return {
                "status": "error",
                "error": "BugHerd integration not available",
            }

        project_id = self.get_bugherd_project_id(project_name)
        if not project_id:
            return {
                "status": "error",
                "error": f"No BugHerd project mapped for '{project_name}'",
            }

        try:
            result = self.client.update_ticket(
                project_id=project_id,
                task_id=task_id,
                status=status,
            )

            if result:
                # Add comment if provided
                if comment:
                    self.add_comment_from_slack(
                        project_name, task_id, f"Status changed to '{status}': {comment}"
                    )
                logger.info(f"Updated BugHerd ticket #{task_id} status to {status} via {self._mode}")
                return {"status": "success", "task_id": task_id, "mode": self._mode}
            else:
                self._stats["errors"] += 1
                return {
                    "status": "error",
                    "error": "Failed to update ticket",
                    "mode": self._mode,
                }

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error updating BugHerd ticket: {e}")
            return {
                "status": "error",
                "error": str(e),
                "mode": self._mode,
            }

    def get_stats(self) -> dict[str, Any]:
        """Get bridge usage statistics."""
        stats = dict(self._stats)
        stats["mode"] = self._mode
        return stats

    def reset_stats(self) -> None:
        """Reset usage statistics."""
        self._stats = {
            "tickets_created": 0,
            "comments_added": 0,
            "errors": 0,
        }
