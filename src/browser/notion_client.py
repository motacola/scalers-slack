from __future__ import annotations

import logging
import re
import time
from typing import Any, cast

from ..dom_selectors import (
    NOTION_CONTENT_EDITABLE,
    NOTION_MAIN,
    NOTION_PAGE_CANVAS,
    NOTION_READY_INDICATORS,
)
from .base import (
    BaseBrowserClient,
    BrowserAutomationConfig,
    BrowserSession,
    SessionExpiredError,
)

logger = logging.getLogger(__name__)
DATE_VALUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")


class NotionBrowserClient(BaseBrowserClient):
    supports_verification = False
    supports_last_synced_update = True

    def __init__(self, session: BrowserSession, config: BrowserAutomationConfig):
        super().__init__(session, config)

    def _wait_for_main(self, page, timeout: int = 10000) -> None:
        for sel in NOTION_MAIN.get_all():
            try:
                page.wait_for_selector(sel, timeout=timeout)
                return
            except Exception:
                continue
        raise RuntimeError("Notion main selector not found.")

    def _get_main_locator(self, page):
        for sel in NOTION_MAIN.get_all():
            loc = page.locator(sel).first
            if loc.count() > 0:
                return loc
        return page.locator(NOTION_MAIN.primary).first

    def _wait_until_ready(self, page) -> None:
        timeout_s = max(1, int(self.config.interactive_login_timeout_ms / 1000))
        start = time.time()
        while time.time() - start < timeout_s:
            current_url = page.url or ""
            if "login" in current_url or "signup" in current_url:
                if not self.config.interactive_login or self.config.headless:
                    raise SessionExpiredError(
                        "Notion login required. Recreate browser storage state "
                        "with scripts/create_storage_state.py to avoid re-login."
                    )
                logger.warning(
                    "Notion login required. Complete login in the opened browser window (waiting up to %s seconds).",
                    int(self.config.interactive_login_timeout_ms / 1000),
                )
            try:
                # Try all ready indicators
                ready = False
                for sel in NOTION_READY_INDICATORS.get_all():
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
        raise RuntimeError("Timed out waiting for Notion to load.")

    def _page_url(self, page_id_or_url: str) -> str:
        if page_id_or_url.startswith("http"):
            return page_id_or_url
        return f"{self.config.notion_base_url.rstrip('/')}/{page_id_or_url}"

    def _locator_visible(self, locator, timeout: int = 1200) -> bool:
        try:
            if locator.count() <= 0:
                return False
        except Exception:
            return False
        try:
            return bool(locator.is_visible(timeout=timeout))
        except Exception:
            return True

    def _first_visible_locator(self, locators: list[Any], timeout: int = 1200):
        for locator in locators:
            if locator is None:
                continue
            if self._locator_visible(locator, timeout=timeout):
                return locator
        return None

    def _find_notion_editor(self, page):
        scoped_roots: list[Any] = [self._get_main_locator(page)]
        for selector in NOTION_PAGE_CANVAS.get_all():
            scoped_roots.append(page.locator(selector).first)
        scoped_roots.append(page)

        for root in scoped_roots:
            for selector in NOTION_CONTENT_EDITABLE.get_all():
                try:
                    locator = root.locator(selector).last if root is not page else page.locator(selector).last
                    if self._locator_visible(locator):
                        return locator
                except Exception:
                    continue
        for selector in ["div[role='textbox']", "div[contenteditable='true'][data-slate-editor='true']"]:
            try:
                locator = page.locator(selector).last
                if self._locator_visible(locator):
                    return locator
            except Exception:
                continue
        return None

    def _focus_canvas(self, page) -> None:
        for selector in [*NOTION_PAGE_CANVAS.get_all(), *NOTION_MAIN.get_all()]:
            try:
                locator = page.locator(selector).first
                if self._locator_visible(locator):
                    locator.click(timeout=3000)
                    return
            except Exception:
                continue

    def _verify_text_present(self, page, text: str, attempts: int = 4) -> bool:
        snippet = " ".join(text.strip().split())
        if not snippet:
            return True
        snippet = snippet[:80]
        for _ in range(max(1, attempts)):
            try:
                if page.get_by_text(snippet, exact=False).first.count() > 0:
                    return True
            except Exception:
                pass
            page.wait_for_timeout(350)
        return False

    def _verify_property_value(self, page, value_cell, date_value: str) -> bool:
        if not date_value:
            return True
        for _ in range(4):
            try:
                rendered = value_cell.evaluate("el => (el.value || el.textContent || el.innerText || '').trim()")
                if isinstance(rendered, str) and date_value in rendered:
                    return True
            except Exception:
                pass
            try:
                if page.get_by_text(date_value, exact=False).first.count() > 0:
                    return True
            except Exception:
                pass
            page.wait_for_timeout(300)
        return False

    def _normalize_property_value(self, value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        if ISO_DATETIME_RE.match(text):
            return text.split("T")[0]
        return text

    def _looks_like_date_value(self, value: str) -> bool:
        return bool(DATE_VALUE_RE.match(value.strip()))

    def _clear_active_input(self, page) -> None:
        page.keyboard.press("Control+A")
        page.keyboard.press("Meta+A")
        page.keyboard.press("Backspace")

    def _select_property_option(self, page, value: str) -> bool:
        if not value:
            return False
        candidates = [
            page.get_by_role("option", name=value, exact=True).first,
            page.get_by_text(value, exact=True).first,
            page.get_by_text(value, exact=False).first,
            page.locator("div[role='option']", has_text=value).first,
            page.locator("div[role='menuitem']", has_text=value).first,
        ]
        for locator in candidates:
            try:
                if self._locator_visible(locator, timeout=700):
                    locator.click(timeout=1500)
                    return True
            except Exception:
                continue
        return False

    def _set_property_value(self, page, value_cell, value: str) -> bool:
        try:
            value_cell.click(timeout=5000)
        except Exception:
            return False

        is_date_input = False
        try:
            meta = value_cell.evaluate(
                """
                (el) => ({
                    tag: (el.tagName || '').toLowerCase(),
                    type: (el.getAttribute('type') || '').toLowerCase(),
                    role: (el.getAttribute('role') || '').toLowerCase(),
                    contenteditable: (el.getAttribute('contenteditable') || '').toLowerCase(),
                })
                """
            )
            if isinstance(meta, dict):
                is_date_input = str(meta.get("type") or "").lower() == "date"
        except Exception:
            is_date_input = False

        try:
            if value and is_date_input and self._looks_like_date_value(value):
                try:
                    value_cell.fill(value)
                except Exception:
                    self._clear_active_input(page)
                    page.keyboard.type(value)
                page.keyboard.press("Enter")
                return True

            self._clear_active_input(page)
            if value:
                page.keyboard.type(value)
                self._select_property_option(page, value)
            page.keyboard.press("Enter")
            return True
        except Exception:
            return False

    def _find_property_label(self, page, property_name: str):
        candidates = [
            page.get_by_text(property_name, exact=True).first,
            page.get_by_text(property_name, exact=False).first,
            page.locator(f"text={property_name}").first,
        ]
        return self._first_visible_locator(candidates, timeout=1500)

    def _find_property_value_cell(self, label):
        row = label.locator("xpath=ancestor::div[@role='row' or @role='listitem' or @data-property-id][1]")
        if not self._locator_visible(row):
            row = label.locator("xpath=ancestor::div[1]")
        if not self._locator_visible(row):
            return None
        candidates = [
            row.locator("css=input[type='date']").first,
            row.locator("css=input").first,
            row.locator("css=div[contenteditable='true']").first,
            row.locator("css=div[role='textbox']").first,
            row.locator("css=div[role='button']").first,
        ]
        value_cell = self._first_visible_locator(candidates, timeout=1200)
        if value_cell is not None:
            return value_cell
        fallback = label.locator(
            "xpath=following::div[@contenteditable='true' or @role='textbox' or @role='button'][1]"
        )
        if self._locator_visible(fallback):
            return fallback
        return None

    def append_audit_note(self, page_id: str, text: str) -> str:
        url = self._page_url(page_id)

        def action(page):
            page.wait_for_timeout(1000)
            self._wait_for_main(page, timeout=15000)
            for attempt in range(3):
                editor = self._find_notion_editor(page)
                if editor is None:
                    self._focus_canvas(page)
                    page.wait_for_timeout(500)
                    continue
                try:
                    editor.click(timeout=6000)
                except Exception:
                    self._focus_canvas(page)
                    editor.click(timeout=6000)
                page.keyboard.type(text)
                page.keyboard.press("Enter")
                if self._verify_text_present(page, text):
                    return
                page.wait_for_timeout(500)
                if attempt < 2:
                    self._focus_canvas(page)
            raise RuntimeError("Could not append audit note in Notion editor.")

        self._with_page(url, action)
        self.stats["ui_actions"] += 1
        return "browser-note"

    def get_block(self, block_id: str) -> dict:
        return {}

    def update_page_property(self, page_id: str, property_name: str, date_iso: str) -> None:
        url = self._page_url(page_id)
        property_value = self._normalize_property_value(date_iso)

        def action(page):
            page.wait_for_timeout(1000)
            self._wait_for_main(page, timeout=15000)
            for attempt in range(3):
                label = self._find_property_label(page, property_name)
                if label is None:
                    page.wait_for_timeout(600)
                    continue
                value_cell = self._find_property_value_cell(label)
                if value_cell is None:
                    self._focus_canvas(page)
                    page.wait_for_timeout(500)
                    continue
                if not self._set_property_value(page, value_cell, property_value):
                    page.wait_for_timeout(500)
                    continue
                if self._verify_property_value(page, value_cell, property_value):
                    return
                if attempt < 2:
                    self._focus_canvas(page)
                    page.wait_for_timeout(600)
            raise RuntimeError(f"Could not update Notion property '{property_name}'.")

        self._with_page(url, action)
        self.stats["ui_actions"] += 1

    def get_page(self, page_id: str) -> dict:
        return {}

    def query_database(self, database_id: str, filter: dict | None = None) -> list[dict]:
        logger.warning("query_database not implemented in NotionBrowserClient fallback.")
        return []

    def search_pages(self, query: str) -> list[dict]:
        logger.warning("search_pages not implemented in NotionBrowserClient fallback.")
        return []

    def reset_stats(self) -> None:
        super().reset_stats()
        self.stats.update(
            {
                "ui_actions": 0,
            }
        )

    def get_stats(self) -> dict[str, Any]:
        return dict(self.stats)

    def check_page_access(self, page_id: str) -> bool:
        url = self._page_url(page_id)

        def action(page):
            page.wait_for_timeout(1500)
            current_url = page.url or ""
            if "login" in current_url or "signup" in current_url:
                return False
            try:
                self._wait_for_main(page, timeout=10000)
            except Exception:
                return False
            return True

        return bool(self._with_page(url, action))

    def search_pages_browser(self, query: str, max_results: int = 10) -> list[dict]:
        start_url = self.config.notion_base_url

        def action(page):
            results = []
            try:
                page.keyboard.press("Meta+k")
                page.wait_for_timeout(500)
                search_input = page.locator("input[placeholder*='Search'], input[type='text']").first
                if search_input.count() == 0:
                    page.keyboard.press("Control+k")
                    page.wait_for_timeout(500)

                search_input = page.locator(
                    "input[placeholder*='Search'], input[placeholder*='search'], "
                    "div[role='combobox'] input, input[data-testid='search-input']"
                ).first
                search_input.wait_for(timeout=5000)
                search_input.fill(query)
                page.wait_for_timeout(1500)

                result_items = page.locator(
                    "div[role='option'], div[data-testid='search-result'], "
                    "div[class*='searchResult'], a[class*='result']"
                ).all()

                for i, item in enumerate(result_items[:max_results]):
                    try:
                        title = item.inner_text().strip().split("\n")[0]
                        href = item.get_attribute("href") or ""
                        if not href:
                            link = item.locator("a").first
                            if link.count() > 0:
                                href = link.get_attribute("href") or ""
                        results.append(
                            {
                                "title": title,
                                "url": href if href.startswith("http") else f"{self.config.notion_base_url}{href}",
                                "index": i,
                            }
                        )
                    except Exception:
                        continue
                page.keyboard.press("Escape")
            except Exception as e:
                logger.warning(f"Search failed: {e}")
            return results

        return self._with_page(start_url, action) or []

    def navigate_to_database(self, database_url: str) -> dict:
        def action(page):
            result = {"url": database_url, "entries": [], "view_type": "unknown"}
            try:
                page.wait_for_timeout(2000)
                if page.locator("div[class*='board']").count() > 0:
                    result["view_type"] = "board"
                elif page.locator("table, div[class*='table']").count() > 0:
                    result["view_type"] = "table"
                elif page.locator("div[class*='gallery']").count() > 0:
                    result["view_type"] = "gallery"
                else:
                    result["view_type"] = "list"

                if result["view_type"] == "table":
                    rows = page.locator("tr[data-block-id], div[data-block-id]").all()
                    for row in rows[:50]:
                        try:
                            cells = row.locator("td, div[class*='cell']").all()
                            if cells:
                                title = cells[0].inner_text().strip() if cells else ""
                                entry = {"title": title, "cells": []}
                                for cell in cells[1:5]:
                                    entry["cells"].append(cell.inner_text().strip())
                                result["entries"].append(entry)
                        except Exception:
                            continue
                elif result["view_type"] == "board":
                    cards = page.locator("div[data-block-id][class*='card'], div[class*='boardCard']").all()
                    for card in cards[:50]:
                        try:
                            title = card.locator("div[class*='title'], span").first.inner_text().strip()
                            result["entries"].append({"title": title})
                        except Exception:
                            continue
                else:
                    items = page.locator("div[data-block-id] a[href*='notion.so'], div[class*='page'] a").all()
                    for item in items[:50]:
                        try:
                            title = item.inner_text().strip()
                            href = item.get_attribute("href") or ""
                            result["entries"].append({"title": title, "url": href})
                        except Exception:
                            continue
            except Exception as e:
                logger.warning(f"Database navigation failed: {e}")
            return result

        return self._with_page(database_url, action) or {"url": database_url, "entries": [], "view_type": "unknown"}

    def extract_page_content(self, page_id_or_url: str) -> dict:
        url = self._page_url(page_id_or_url)

        def action(page):
            result = {"url": url, "title": "", "properties": {}, "content_blocks": [], "text_content": ""}
            try:
                page.wait_for_timeout(2000)
                title_el = page.locator("h1[class*='title'], div[class*='title'] h1, div[placeholder='Untitled']").first
                if title_el.count() > 0:
                    result["title"] = title_el.inner_text().strip()
                property_rows = page.locator("div[class*='property'], div[role='row'], div[data-property-id]").all()
                for row in property_rows[:20]:
                    try:
                        parts = row.inner_text().strip().split("\n")
                        if len(parts) >= 2:
                            result["properties"][parts[0].strip()] = parts[1].strip()
                        elif len(parts) == 1:
                            label_el = row.locator("div[class*='label'], span[class*='label']").first
                            value_el = row.locator("div[class*='value'], span[class*='value']").first
                            if label_el.count() > 0 and value_el.count() > 0:
                                result["properties"][label_el.inner_text().strip()] = value_el.inner_text().strip()
                    except Exception:
                        continue
                content_area = self._get_main_locator(page)
                if content_area and content_area.count() > 0:
                    blocks = content_area.locator(
                        "div[data-block-id], p, h1, h2, h3, li, div[class*='text'], div[class*='paragraph']"
                    ).all()
                    for block in blocks[:100]:
                        try:
                            text = block.inner_text().strip()
                            if text and len(text) > 1:
                                result["content_blocks"].append(text)
                        except Exception:
                            continue
                result["text_content"] = "\n".join(result["content_blocks"])
            except Exception as e:
                logger.warning(f"Page content extraction failed: {e}")
            return result

        return self._with_page(url, action) or {
            "url": url,
            "title": "",
            "properties": {},
            "content_blocks": [],
            "text_content": "",
        }

    def find_ticket_by_name(self, project_name: str, hub_url: str | None = None) -> dict | None:
        results = self.search_pages_browser(project_name, max_results=5)
        if not results:
            return None
        project_lower = project_name.lower()
        for result in results:
            title_lower = result.get("title", "").lower()
            if project_lower in title_lower or title_lower in project_lower:
                if result.get("url"):
                    return self.extract_page_content(result["url"])
                return result
        if results and results[0].get("url"):
            return self.extract_page_content(results[0]["url"])
        return results[0] if results else None

    def navigate_hub_and_list_tickets(self, hub_url: str, status_filter: str | None = None) -> list[dict]:
        def action(page):
            tickets = []
            try:
                page.wait_for_timeout(2000)
                if status_filter:
                    filter_btn = page.locator(
                        "div[class*='filter'], button[class*='filter'], div[data-testid='filter']"
                    ).first
                    if filter_btn.count() > 0:
                        filter_btn.click()
                        page.wait_for_timeout(500)
                        status_option = page.get_by_text(status_filter, exact=False).first
                        if status_option.count() > 0:
                            status_option.click()
                            page.wait_for_timeout(1000)
                entries = page.locator(
                    "a[href*='notion.so'][data-block-id], "
                    "div[data-block-id] a[href*='notion.so'], "
                    "tr[data-block-id], div[class*='row'][data-block-id]"
                ).all()
                for entry in entries[:100]:
                    try:
                        ticket = {}
                        title_el = entry.locator("div[class*='title'], span, td:first-child").first
                        if title_el.count() > 0:
                            ticket["title"] = title_el.inner_text().strip()
                        if entry.get_attribute("href"):
                            ticket["url"] = entry.get_attribute("href")
                        else:
                            link = entry.locator("a[href*='notion.so']").first
                            if link.count() > 0:
                                ticket["url"] = link.get_attribute("href")
                        status_el = entry.locator(
                            "div[class*='status'], span[class*='tag'], div[class*='select']"
                        ).first
                        if status_el.count() > 0:
                            ticket["status"] = status_el.inner_text().strip()
                        if ticket.get("title"):
                            tickets.append(ticket)
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Hub navigation failed: {e}")
            return tickets

        return self._with_page(hub_url, action) or []

    def click_ticket_and_extract(self, hub_url: str, ticket_title: str) -> dict | None:
        def action(page):
            try:
                page.wait_for_timeout(2000)
                ticket_link = page.get_by_text(ticket_title, exact=False).first
                if ticket_link.count() == 0:
                    ticket_link = page.locator(f"a:has-text('{ticket_title}')").first
                if ticket_link.count() > 0:
                    ticket_link.click()
                    page.wait_for_timeout(2000)
                    result = {"url": page.url, "title": ticket_title, "properties": {}, "content_blocks": []}
                    self._wait_for_main(page, timeout=10000)
                    property_rows = page.locator("div[class*='property'], div[role='row']").all()
                    for row in property_rows[:20]:
                        try:
                            parts = row.inner_text().strip().split("\n")
                            if len(parts) >= 2:
                                result["properties"][parts[0].strip()] = parts[1].strip()
                        except Exception:
                            continue
                    content_area = self._get_main_locator(page)
                    if content_area and content_area.count() > 0:
                        blocks = content_area.locator("div[data-block-id], p, h1, h2, h3").all()
                        for block in blocks[:50]:
                            try:
                                text = block.inner_text().strip()
                                if text:
                                    result["content_blocks"].append(text)
                            except Exception:
                                continue
                    return result
            except Exception as e:
                logger.warning(f"Ticket click and extract failed: {e}")
            return None

        return cast(dict[Any, Any] | None, self._with_page(hub_url, action))

    def update_ticket_property_browser(self, page_id_or_url: str, property_name: str, new_value: str) -> bool:
        url = self._page_url(page_id_or_url)

        def action(page):
            try:
                page.wait_for_timeout(1500)
                property_label = page.get_by_text(property_name, exact=True)
                if property_label.count() == 0:
                    property_label = page.get_by_text(property_name, exact=False).first
                if property_label.count() == 0:
                    return False
                row = property_label.locator(
                    "xpath=ancestor::div[@role='row' or @role='listitem' or @data-property-id][1]"
                )
                if row.count() == 0:
                    row = property_label.locator("xpath=..")
                value_cell = row.locator(
                    "div[contenteditable='true'], div[role='button'], div[role='textbox'], div[class*='value']"
                ).first
                if value_cell.count() > 0:
                    value_cell.click()
                    page.wait_for_timeout(300)
                    page.keyboard.press("Control+a")
                    page.keyboard.press("Meta+a")
                    page.wait_for_timeout(100)
                    page.keyboard.type(new_value)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(500)
                    self.stats["ui_actions"] += 1
                    return True
            except Exception as e:
                logger.warning(f"Property update failed: {e}")
                self.stats["errors"] += 1
            return False

        return bool(self._with_page(url, action))
