from __future__ import annotations

import logging
import time
from typing import Any, cast

from .base import (
    BaseBrowserClient,
    BrowserAutomationConfig,
    BrowserSession,
    SessionExpiredError,
)
from ..dom_selectors import (
    BUGHERD_ADD_TASK,
    BUGHERD_READY_INDICATORS,
    BUGHERD_SUBMIT,
    BUGHERD_TASK_DESCRIPTION,
    BUGHERD_TASK_TITLE,
)

logger = logging.getLogger(__name__)

class BugHerdBrowserClient(BaseBrowserClient):
    """
    Browser-based BugHerd client for when no API key is available.
    Uses Playwright to automate BugHerd web interface.
    """

    BUGHERD_BASE_URL = "https://www.bugherd.com"
    BUGHERD_APP_URL = "https://app.bugherd.com"

    SELECTORS = {
        "priority_dropdown": '[data-testid="priority-select"], .priority-select, .ant-select',
        "status_dropdown": '[data-testid="status-select"], .status-select',
        "assignee_dropdown": '[data-testid="assignee-select"], .assignee-select',
        "tags_input": '[data-testid="tags-input"], .tags-input, input[placeholder*="tag"]',
        "create_button": 'button:has-text("Create"), button[type="submit"]',
        "comment_input": 'textarea[placeholder*="comment"], .comment-input',
        "submit_comment": 'button:has-text("Comment"), button:has-text("Send")',
        "task_item": '.task-item, [data-testid="task-item"]',
    }

    # Priority mapping
    PRIORITY_MAP = {
        "critical": "Critical",
        "important": "Important",
        "normal": "Normal",
        "minor": "Minor",
    }

    # Status mapping
    STATUS_MAP = {
        "backlog": "Backlog",
        "todo": "To Do",
        "doing": "Doing",
        "done": "Done",
    }

    def __init__(self, session: BrowserSession, config: BrowserAutomationConfig):
        """Initialize BugHerd browser client."""
        super().__init__(session, config)
        self._current_project_id: str | None = None

    def _project_url(self, project_id: str) -> str:
        """Get the URL for a BugHerd project."""
        return f"{self.BUGHERD_APP_URL}/projects/{project_id}/tasks"

    def _task_url(self, project_id: str, task_id: str) -> str:
        """Get the URL for a specific task."""
        return f"{self.BUGHERD_APP_URL}/projects/{project_id}/tasks/{task_id}"


    def _wait_until_ready(self, page, timeout_s: int = 30) -> None:
        """Wait for BugHerd page to be ready."""
        start = time.time()
        while time.time() - start < timeout_s:
            current_url = page.url or ""
            if "/login" in current_url or "/signin" in current_url:
                if not self.config.interactive_login or self.config.headless:
                    raise SessionExpiredError(
                        "BugHerd login required. Please log in manually first or provide storage state."
                    )
                logger.warning(
                    "BugHerd login required. Complete login in the browser window (waiting up to %s seconds).",
                    timeout_s,
                )
            try:
                ready = False
                for sel in BUGHERD_READY_INDICATORS.get_all():
                    if page.query_selector(sel):
                        ready = True
                        break
                if ready:
                    if self.config.auto_save_storage_state:
                        self.session.save_storage_state()
                    return
            except Exception:
                pass
            page.wait_for_timeout(1000)
        raise RuntimeError("Timed out waiting for BugHerd to load.")

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
        requester_email: str | None = None,
    ) -> dict | None:
        """Create a BugHerd ticket via browser automation."""
        url = self._project_url(project_id)
        ticket_title = title or description[:100].split("\n")[0]

        def action(page):
            add_btn = None
            for sel in BUGHERD_ADD_TASK.get_all():
                loc = page.locator(sel).first
                if loc.count() > 0:
                    add_btn = loc
                    break
            
            if not add_btn:
                add_btn = page.get_by_role("button", name="Add Task")
            
            add_btn.click(timeout=10000)
            page.wait_for_timeout(500)
 
            title_input = None
            for sel in BUGHERD_TASK_TITLE.get_all():
                loc = page.locator(sel).first
                if loc.count() > 0:
                    title_input = loc
                    break
            
            if title_input:
                title_input.fill(ticket_title)
            else:
                page.locator("textarea").first.fill(ticket_title)
 
            desc_input = None
            for sel in BUGHERD_TASK_DESCRIPTION.get_all():
                loc = page.locator(sel).first
                if loc.count() > 0:
                    desc_input = loc
                    break
            
            if desc_input:
                desc_input.fill(description)

            priority_label = self.PRIORITY_MAP.get(priority.lower(), "Normal")
            try:
                priority_select = page.locator(self.SELECTORS["priority_dropdown"]).first
                if priority_select.count() > 0:
                    priority_select.click()
                    page.wait_for_timeout(200)
                    page.get_by_text(priority_label, exact=True).click()
            except Exception:
                pass

            status_label = self.STATUS_MAP.get(status.lower(), "Backlog")
            try:
                status_select = page.locator(self.SELECTORS["status_dropdown"]).first
                if status_select.count() > 0:
                    status_select.click()
                    page.wait_for_timeout(200)
                    page.get_by_text(status_label, exact=True).click()
            except Exception:
                pass

            if tag_names:
                try:
                    tags_input = page.locator(self.SELECTORS["tags_input"]).first
                    if tags_input.count() > 0:
                        for tag in tag_names:
                            tags_input.fill(tag)
                            page.keyboard.press("Enter")
                            page.wait_for_timeout(100)
                except Exception:
                    pass

            create_btn = page.locator(self.SELECTORS["create_button"]).first
            if create_btn.count() == 0:
                create_btn = page.get_by_role("button", name="Create")
            create_btn.click(timeout=10000)
            page.wait_for_timeout(1000)
            return {"task": {"title": ticket_title, "status": status}}

        try:
            result = self._with_page(url, action)
            self.stats["tickets_created"] += 1
            return cast(dict[Any, Any] | None, result)
        except Exception as e:
            logger.error(f"Failed to create BugHerd ticket: {e}")
            return None

    def create_ticket_comment(
        self,
        project_id: str,
        task_id: str,
        text: str,
    ) -> dict | None:
        """Add a comment to an existing BugHerd ticket."""
        url = self._task_url(project_id, task_id)

        def action(page):
            comment_input = page.locator(self.SELECTORS["comment_input"]).first
            if comment_input.count() == 0:
                comment_input = page.locator("textarea").last

            comment_input.fill(text)
            page.wait_for_timeout(200)

            submit_btn = page.locator(self.SELECTORS["submit_comment"]).first
            if submit_btn.count() == 0:
                submit_btn = page.get_by_role("button", name="Comment")
            submit_btn.click(timeout=10000)
            page.wait_for_timeout(500)
            return {"comment": {"text": text[:50]}}

        try:
            result = self._with_page(url, action)
            self.stats["comments_added"] += 1
            return cast(dict[Any, Any] | None, result)
        except Exception as e:
            logger.error(f"Failed to add comment to BugHerd task: {e}")
            return None

    def update_ticket(
        self,
        project_id: str,
        task_id: str,
        description: str | None = None,
        page_url: str | None = None,
        priority: str | None = None,
        tag_names: list[str] | None = None,
        assigned_to_id: int | None = None,
        status: str | None = None,
        title: str | None = None,
    ) -> dict | None:
        """Update an existing BugHerd ticket."""
        url = self._task_url(project_id, task_id)

        def action(page):
            updated_fields = []
            if status:
                status_label = self.STATUS_MAP.get(status.lower(), status)
                try:
                    status_select = page.locator(self.SELECTORS["status_dropdown"]).first
                    if status_select.count() > 0:
                        status_select.click()
                        page.wait_for_timeout(200)
                        page.get_by_text(status_label, exact=True).click()
                        updated_fields.append("status")
                except Exception:
                    pass

            if priority:
                priority_label = self.PRIORITY_MAP.get(priority.lower(), priority)
                try:
                    priority_select = page.locator(self.SELECTORS["priority_dropdown"]).first
                    if priority_select.count() > 0:
                        priority_select.click()
                        page.wait_for_timeout(200)
                        page.get_by_text(priority_label, exact=True).click()
                        updated_fields.append("priority")
                except Exception:
                    pass

            page.wait_for_timeout(500)
            return {"task": {"id": task_id, "updated_fields": updated_fields}}

        try:
            result = self._with_page(url, action)
            self.stats["tickets_updated"] += 1
            return cast(dict[Any, Any] | None, result)
        except Exception as e:
            logger.error(f"Failed to update BugHerd task: {e}")
            return None

    def get_project_members(self, project_id: str) -> list[dict] | None:
        """Get project members (browser mode returns limited info)."""
        url = f"{self.BUGHERD_APP_URL}/projects/{project_id}/settings/team"

        def action(page):
            members = []
            member_items = page.locator(".member-item, .team-member, [data-testid='member']").all()
            for item in member_items[:20]:
                try:
                    name = item.locator(".member-name, .name").text_content()
                    email = item.locator(".member-email, .email").text_content() or ""
                    members.append({
                        "display_name": name.strip() if name else "",
                        "email": email.strip(),
                    })
                except Exception:
                    pass
            return members

        try:
            return cast(list[dict] | None, self._with_page(url, action))
        except Exception as e:
            logger.error(f"Failed to get project members: {e}")
            return None

    def find_member_by_name(self, project_id: str, name: str) -> dict | None:
        """Find a project member by name (partial match)."""
        members = self.get_project_members(project_id)
        if not members:
            return None

        name_lower = name.lower()
        for member in members:
            display_name = member.get("display_name", "").lower()
            email = member.get("email", "").lower()
            if name_lower in display_name or name_lower in email:
                return member
        return None

    def list_tasks(
        self,
        project_id: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List tasks in a project."""
        url = self._project_url(project_id)
        if status:
            url += f"?status={status}"

        def action(page):
            tasks = []
            task_items = page.locator(self.SELECTORS["task_item"]).all()
            for item in task_items[:limit]:
                try:
                    title_el = item.locator(".task-title, .title, h3, h4").first
                    title = title_el.text_content() if title_el.count() > 0 else ""
                    status_el = item.locator(".task-status, .status").first
                    task_status = status_el.text_content() if status_el.count() > 0 else ""
                    tasks.append({
                        "title": title.strip() if title else "",
                        "status": task_status.strip() if task_status else "",
                    })
                except Exception:
                    pass
            return tasks

        try:
            return self._with_page(url, action) or []
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics."""
        return dict(self.stats)

    def reset_stats(self) -> None:
        """Reset client statistics."""
        super().reset_stats()
        self.stats.update({
            "tickets_created": 0,
            "tickets_updated": 0,
            "comments_added": 0,
        })
