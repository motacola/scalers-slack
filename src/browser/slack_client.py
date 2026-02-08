from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, cast
from urllib.parse import urlencode, urljoin

from ..dom_selectors import (
    CHANNEL_HEADER_NAME,
    CHANNEL_SIDEBAR,
    CHANNEL_TOPIC,
    MESSAGE_CONTAINER,
    MESSAGE_LIST_CONTAINER,
    SEARCH_RESULT,
    THREAD_MESSAGE_CONTAINER,
    THREAD_PANE_CONTAINER,
    THREAD_REPLIES,
    DOMExtractor,
)
from .base import (
    BaseBrowserClient,
    BrowserAutomationConfig,
    BrowserSession,
    SessionExpiredError,
)

logger = logging.getLogger(__name__)


class SlackBrowserClient(BaseBrowserClient):
    def __init__(self, session: BrowserSession, config: BrowserAutomationConfig):
        super().__init__(session, config)
        self.pagination_stats: dict[str, Any] = {}
        self._web_token: str | None = None

    def _slack_client_home(self) -> str:
        if self.config.slack_workspace_id:
            return f"{self.config.slack_client_url}/{self.config.slack_workspace_id}"
        return self.config.slack_client_url

    def _channel_url(self, channel_id: str) -> str:
        return f"{self._slack_client_home()}/{channel_id}"

    def _search_url(self, query: str) -> str:
        query_string = urlencode({"query": query})
        return f"{self._slack_client_home()}/search?{query_string}"

    def _parse_channel_id_from_text(self, value: str) -> str | None:
        match = re.search(r"/client/[^/]+/([CGD][A-Z0-9]{8,})", value)
        if match:
            return match.group(1)
        match = re.search(r"/archives/([CGD][A-Z0-9]{8,})", value)
        if match:
            return match.group(1)
        return None

    def _parse_workspace_id_from_text(self, value: str) -> str | None:
        match = re.search(r"/client/(T[A-Z0-9]{8,})", value)
        if match:
            return match.group(1)
        return None

    def _parse_ts_from_permalink(self, permalink: str) -> str | None:
        match = re.search(r"/p(\d{10,})", permalink)
        if not match:
            return None
        raw = match.group(1)
        if len(raw) <= 6:
            return None
        return f"{raw[:-6]}.{raw[-6:]}"

    def _normalize_ts(self, ts: Any) -> str:
        if ts is None:
            return ""
        if isinstance(ts, (int, float)):
            return f"{float(ts):.6f}"
        text = str(ts).strip()
        if not text:
            return ""
        if re.fullmatch(r"\d+(\.\d+)?", text):
            if "." in text:
                whole, frac = text.split(".", 1)
                return f"{whole}.{frac[:6].ljust(6, '0')}"
            return f"{text}.000000"
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return f"{parsed.timestamp():.6f}"
        except Exception:
            return ""

    def _ts_to_float(self, ts: Any) -> float | None:
        normalized = self._normalize_ts(ts)
        if not normalized:
            return None
        try:
            return float(normalized)
        except Exception:
            return None

    def _passes_time_window(self, ts: Any, oldest: str | None = None, latest: str | None = None) -> bool:
        ts_value = self._ts_to_float(ts)
        if ts_value is None:
            return True
        oldest_value = self._ts_to_float(oldest) if oldest else None
        latest_value = self._ts_to_float(latest) if latest else None
        if oldest_value is not None and ts_value < oldest_value:
            return False
        if latest_value is not None and ts_value > latest_value:
            return False
        return True

    def _build_api_like_message(
        self,
        dom_message: dict[str, Any],
        channel_id: str | None = None,
        page_url: str | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any] | None:
        text = str(dom_message.get("text") or "").strip()
        permalink = str(dom_message.get("permalink") or "").strip()
        parsed_channel = (
            self._parse_channel_id_from_text(permalink)
            or self._parse_channel_id_from_text(page_url or "")
            or channel_id
        )
        ts = self._normalize_ts(dom_message.get("ts"))
        if not ts and permalink:
            ts = self._normalize_ts(self._parse_ts_from_permalink(permalink))
        if not text and not ts and not permalink:
            return None
        normalized_thread_ts = self._normalize_ts(thread_ts or dom_message.get("thread_ts")) or ts
        user_name = str(dom_message.get("user") or "").strip()
        user_id = str(dom_message.get("user_id") or "").strip()
        user = user_id or user_name or "unknown"
        result: dict[str, Any] = {
            "type": "message",
            "text": text,
            "user": user,
            "ts": ts or "",
            "thread_ts": normalized_thread_ts or "",
            "permalink": permalink,
            "channel_id": parsed_channel,
            "channel": {"id": parsed_channel} if parsed_channel else {},
        }
        if user_name:
            result["user_profile"] = {"real_name": user_name, "display_name": user_name}
            result["username"] = user_name
        return result

    def _build_api_like_search_match(self, dom_result: dict[str, Any]) -> dict[str, Any] | None:
        channel_id = str(dom_result.get("channel_id") or "").strip() or None
        message = self._build_api_like_message(dom_result, channel_id=channel_id)
        if not message:
            return None
        return message

    def _sort_messages_desc(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(messages, key=lambda item: self._ts_to_float(item.get("ts")) or 0.0, reverse=True)

    def _sort_messages_asc(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(messages, key=lambda item: self._ts_to_float(item.get("ts")) or 0.0)

    def _thread_url_candidates(self, channel_id: str, thread_ts: str) -> list[str]:
        normalized = self._normalize_ts(thread_ts) or thread_ts
        compact_ts = normalized.replace(".", "")
        channel_url = self._channel_url(channel_id)
        candidates = [
            channel_url,
            f"{channel_url}?thread_ts={normalized}&cid={channel_id}",
            f"{channel_url}/thread/{channel_id}-{normalized}",
            f"{channel_url}/thread/{channel_id}-{compact_ts}",
        ]
        seen: set[str] = set()
        ordered: list[str] = []
        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            ordered.append(candidate)
        return ordered

    def _thread_pane_scope(self, page, timeout: int = 1500):
        return self._find_first_visible_locator(page, THREAD_PANE_CONTAINER.get_all(), timeout=timeout)

    def _find_root_message_for_thread(self, page, extractor: DOMExtractor, thread_ts: str):
        for selector in MESSAGE_CONTAINER.get_all():
            try:
                for message in page.locator(selector).all():
                    data = extractor.extract_message_data(message, require_text=False)
                    if not data:
                        continue
                    candidate_ts = self._normalize_ts(data.get("ts"))
                    if not candidate_ts:
                        candidate_ts = self._normalize_ts(
                            self._parse_ts_from_permalink(str(data.get("permalink") or ""))
                        )
                    if candidate_ts == thread_ts:
                        return message
            except Exception:
                continue
        return None

    def _click_thread_trigger(self, message) -> bool:
        trigger_locators: list[Any] = []
        for selector in THREAD_REPLIES.get_all():
            trigger_locators.append(message.locator(selector).first)
        trigger_locators.extend(
            [
                message.locator("button[aria-label*='thread' i]").first,
                message.locator("button[aria-label*='reply' i]").first,
                message.locator("a[data-ts]").first,
                message.locator("time[data-ts]").first,
                message.locator("a[href*='/p']").first,
            ]
        )

        for trigger in trigger_locators:
            try:
                if trigger.count() <= 0:
                    continue
            except Exception:
                continue
            try:
                if trigger.is_visible(timeout=800):
                    trigger.click(timeout=1800)
                    return True
            except Exception:
                continue
        return False

    def _open_thread_from_root_message(
        self,
        page,
        channel_id: str,
        thread_ts: str,
        max_scrolls: int = 16,
    ) -> bool:
        normalized_thread_ts = self._normalize_ts(thread_ts)
        if not normalized_thread_ts:
            return False
        extractor = DOMExtractor(page)
        extractor.wait_for_element(MESSAGE_LIST_CONTAINER, timeout=10000)
        container = extractor.scroll_container()
        if container is None:
            return False

        for attempt in range(max(1, max_scrolls)):
            root_message = self._find_root_message_for_thread(page, extractor, normalized_thread_ts)
            if root_message is not None and self._click_thread_trigger(root_message):
                page.wait_for_timeout(700)
                if self._thread_pane_scope(page, timeout=1600) is not None:
                    return True
            try:
                container.evaluate("el => el.scrollBy(0, -Math.max(el.clientHeight * 1.8, 1400))")
            except Exception:
                try:
                    page.mouse.wheel(0, -2200)
                except Exception:
                    break
            page.wait_for_timeout(650)
            if attempt % 3 == 2 and self._thread_pane_scope(page, timeout=500) is not None:
                return True

        return self._thread_pane_scope(page, timeout=1000) is not None

    def _collect_messages_from_scope(
        self,
        page,
        extractor: DOMExtractor,
        selector_set: list[str],
        messages: list[dict[str, Any]],
        seen: set[str],
        channel_id: str,
        limit: int,
        thread_ts: str | None = None,
        scope=None,
    ) -> int:
        added = 0
        require_text = thread_ts is None
        for selector in selector_set:
            try:
                elements = []
                if scope is not None:
                    elements = scope.locator(selector).all()
                    if not elements and " " in selector:
                        nested_selector = selector.split(" ", 1)[1].strip()
                        if nested_selector:
                            elements = scope.locator(nested_selector).all()
                    if not elements:
                        elements = page.locator(selector).all()
                else:
                    elements = page.locator(selector).all()
            except Exception:
                continue
            for element in elements:
                if len(messages) >= limit:
                    return added
                data = extractor.extract_message_data(element, require_text=require_text)
                if not data:
                    continue
                api_message = self._build_api_like_message(
                    data,
                    channel_id=channel_id,
                    page_url=page.url,
                    thread_ts=thread_ts,
                )
                if not api_message:
                    continue
                key = (
                    api_message.get("ts")
                    or api_message.get("permalink")
                    or (f"{api_message.get('user')}::{api_message.get('text')}")
                )
                if key in seen:
                    continue
                seen.add(key)
                messages.append(api_message)
                added += 1
        return added

    def _find_first_visible_locator(self, page, selectors: list[str], timeout: int = 1500):
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() > 0 and locator.is_visible(timeout=timeout):
                    return locator
            except Exception:
                continue
        return None

    def _fetch_thread_replies_dom(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 200,
        max_scrolls: int = 8,
    ) -> list[dict[str, Any]]:
        normalized_thread_ts = self._normalize_ts(thread_ts)
        if not normalized_thread_ts:
            return []

        messages: list[dict[str, Any]] = []
        seen: set[str] = set()
        total_pages = 0

        for url in self._thread_url_candidates(channel_id, normalized_thread_ts):
            page = self.session.new_page(url)
            try:
                self._wait_until_ready(page)
                extractor = DOMExtractor(page)
                thread_scope = self._thread_pane_scope(page, timeout=2500)
                if thread_scope is None:
                    self._open_thread_from_root_message(page, channel_id=channel_id, thread_ts=normalized_thread_ts)
                    thread_scope = self._thread_pane_scope(page, timeout=2500)
                if thread_scope is None:
                    extractor.wait_for_element(MESSAGE_LIST_CONTAINER, timeout=8000)

                self._collect_messages_from_scope(
                    page,
                    extractor,
                    THREAD_MESSAGE_CONTAINER.get_all(),
                    messages,
                    seen,
                    channel_id=channel_id,
                    limit=limit,
                    thread_ts=normalized_thread_ts,
                    scope=thread_scope,
                )

                scrolls = 0
                stagnant_rounds = 0
                while (
                    len(messages) < limit and thread_scope is not None and scrolls < max_scrolls and stagnant_rounds < 3
                ):
                    before = len(messages)
                    try:
                        thread_scope.evaluate("el => el.scrollBy(0, -Math.max(el.clientHeight * 1.8, 1400))")
                    except Exception:
                        try:
                            page.mouse.wheel(0, -2200)
                        except Exception:
                            break
                    page.wait_for_timeout(900)
                    added = self._collect_messages_from_scope(
                        page,
                        extractor,
                        THREAD_MESSAGE_CONTAINER.get_all(),
                        messages,
                        seen,
                        channel_id=channel_id,
                        limit=limit,
                        thread_ts=normalized_thread_ts,
                        scope=thread_scope,
                    )
                    scrolls += 1
                    if added <= 0 and len(messages) == before:
                        stagnant_rounds += 1
                    else:
                        stagnant_rounds = 0

                if messages:
                    total_pages = max(1, scrolls + 1)
                    break
            finally:
                try:
                    page.close()
                except Exception:
                    pass

        sorted_messages = self._sort_messages_asc(messages)
        self._set_pagination_stats("thread_dom", max(1, total_pages), len(sorted_messages))
        return sorted_messages[:limit]

    def _has_web_token(self, page) -> bool:
        try:
            token = page.evaluate(
                """
                (workspaceId) => {
                    const keys = ["localConfig_v2", "localConfig"];
                    for (const key of keys) {
                        const raw = window.localStorage.getItem(key);
                        if (!raw) continue;
                        try {
                            const parsed = JSON.parse(raw);
                            const teams = parsed && parsed.teams ? parsed.teams : null;
                            if (!teams) continue;
                            if (workspaceId && teams[workspaceId] && teams[workspaceId].token) {
                                return teams[workspaceId].token;
                            }
                            for (const id of Object.keys(teams)) {
                                const team = teams[id];
                                if (team && team.token) return team.token;
                            }
                        } catch (e) {
                            continue;
                        }
                    }
                    return null;
                }
                """,
                self.config.slack_workspace_id or None,
            )
            return bool(token)
        except Exception:
            return False

    def _wait_until_ready(self, page) -> None:
        """Wait for Slack interface to be ready."""
        timeout_s = max(1, int(self.config.interactive_login_timeout_ms / 1000))
        start = time.time()
        while time.time() - start < timeout_s:
            url = page.url or ""
            if "login" in url or "signin" in url:
                if not self.config.interactive_login or self.config.headless:
                    raise SessionExpiredError("Slack login required. Please refresh storage state.")
                logger.info("Slack login required. Waiting for manual login...")

            # Check for Slack specific elements
            if page.query_selector("[data-qa='channel_sidebar_name'], .p-client_container, .c-message_list"):
                if self._has_web_token(page) and self.config.auto_save_storage_state:
                    self.session.save_storage_state()
                return
            page.wait_for_timeout(1000)
        raise RuntimeError("Timed out waiting for Slack readiness")

    def _token_diagnostics(self) -> dict[str, Any]:
        try:
            state = self.session.context.storage_state()
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc)}
        teams: list[str] = []
        token_present = False
        for origin in state.get("origins", []):
            if "slack.com" not in origin.get("origin", ""):
                continue
            for entry in origin.get("localStorage", []):
                if entry.get("name") not in {"localConfig_v2", "localConfig"}:
                    continue
                raw = entry.get("value")
                if not isinstance(raw, str):
                    continue
                try:
                    parsed = json.loads(raw)
                except Exception:
                    continue
                teams_data = parsed.get("teams") if isinstance(parsed, dict) else None
                if not isinstance(teams_data, dict):
                    continue
                for team_id, team in teams_data.items():
                    teams.append(team_id)
                    if isinstance(team, dict) and isinstance(team.get("token"), str) and team.get("token"):
                        token_present = True
        return {"status": "ok", "teams": sorted(set(teams)), "token_present": token_present}

    def _log_api_failure(self, endpoint: str, error: str, status: int | None, data: Any | None) -> None:
        payload = {
            "ts": time.time(),
            "endpoint": endpoint,
            "status": status,
            "error": error,
            "token_diagnostics": self._token_diagnostics(),
            "data_error": data if isinstance(data, dict) else None,
        }
        debug_dir = os.path.join("output", "slack_debug")
        try:
            os.makedirs(debug_dir, exist_ok=True)
            path = os.path.join(debug_dir, "api_failures.jsonl")
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
            if self.config.auto_save_storage_state:
                self.session.save_storage_state()
        except Exception:
            pass

    def _should_fallback_to_dom(self, error: Exception) -> bool:
        message = str(error).lower()
        return (
            "slack web token not found" in message
            or "auth error" in message
            or "not_authed" in message
            or "token_expired" in message
            or "slack api error (browser)" in message
            or "rate limit exceeded" in message
        )

    def _fetch_channel_history_dom(
        self,
        channel_id: str,
        latest: str | None = None,
        oldest: str | None = None,
        limit: int = 200,
        max_scrolls: int = 6,
    ) -> list[dict[str, Any]]:
        url = self._channel_url(channel_id)
        page = self.session.new_page(url)
        messages: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            extractor = DOMExtractor(page)
            if not extractor.wait_for_element(MESSAGE_LIST_CONTAINER, timeout=20000):
                raise RuntimeError("Slack DOM not ready for message extraction")

            effective_scrolls = max(max_scrolls, min(60, max(6, limit // 40)))

            def collect() -> int:
                added = 0
                for selector in MESSAGE_CONTAINER.get_all():
                    try:
                        for element in page.locator(selector).all():
                            data = extractor.extract_message_data(element)
                            if not data:
                                continue
                            api_message = self._build_api_like_message(data, channel_id=channel_id, page_url=page.url)
                            if not api_message:
                                continue
                            if not self._passes_time_window(api_message.get("ts"), oldest=oldest, latest=latest):
                                continue
                            key = api_message.get("ts") or f"{api_message.get('user')}::{api_message.get('text')}"
                            if key in seen:
                                continue
                            seen.add(key)
                            messages.append(api_message)
                            added += 1
                    except Exception:
                        continue
                return added

            collect()
            container = extractor.scroll_container()
            scrolls = 0
            stagnant_rounds = 0
            while (
                len(messages) < limit and container is not None and scrolls < effective_scrolls and stagnant_rounds < 3
            ):
                before_count = len(messages)
                before_top = None
                try:
                    before_top = container.evaluate("el => el.scrollTop")
                    container.evaluate("el => el.scrollBy(0, -el.scrollHeight)")
                except Exception:
                    break
                page.wait_for_timeout(1000)
                added = collect()
                scrolls += 1
                after_top = None
                try:
                    after_top = container.evaluate("el => el.scrollTop")
                except Exception:
                    after_top = None
                if added <= 0 and len(messages) == before_count and after_top == before_top:
                    stagnant_rounds += 1
                else:
                    stagnant_rounds = 0

            sorted_messages = self._sort_messages_desc(messages)
            self._set_pagination_stats("history_dom", max(1, scrolls + 1), len(sorted_messages))
            return sorted_messages[:limit]
        finally:
            try:
                page.close()
            except Exception:
                pass

    def _extract_search_result_data(self, element, page) -> dict[str, Any] | None:
        try:
            text = element.inner_text().strip()
        except Exception:
            text = ""

        permalink = ""
        ts = ""
        try:
            link = element.locator("a[href]").first
            if link.count() > 0:
                href = link.get_attribute("href") or ""
                if href:
                    permalink = href if href.startswith("http") else urljoin(page.url, href)
        except Exception:
            pass

        try:
            ts_el = element.locator("a[data-ts], time").first
            if ts_el.count() > 0:
                ts = ts_el.get_attribute("data-ts") or ts_el.get_attribute("datetime") or ""
        except Exception:
            pass

        if not ts and permalink:
            ts = self._parse_ts_from_permalink(permalink) or ""

        channel_id = self._parse_channel_id_from_text(permalink) or self._parse_channel_id_from_text(page.url or "")

        if not text and not permalink:
            return None
        return {
            "text": text,
            "permalink": permalink,
            "ts": ts,
            "thread_ts": ts,
            "channel_id": channel_id,
        }

    def _search_messages_dom(self, query: str, limit: int = 100) -> list[dict[str, Any]]:
        url = self._search_url(query)
        page = self.session.new_page(url)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            if not DOMExtractor(page).wait_for_element(SEARCH_RESULT, timeout=20000):
                raise RuntimeError("Slack search results not ready")

            def collect() -> int:
                added = 0
                for selector in SEARCH_RESULT.get_all():
                    try:
                        for element in page.locator(selector).all():
                            data = self._extract_search_result_data(element, page)
                            if not data:
                                continue
                            match = self._build_api_like_search_match(data)
                            if not match:
                                continue
                            key = match.get("ts") or match.get("permalink") or match.get("text")
                            if not key or key in seen:
                                continue
                            seen.add(key)
                            results.append(match)
                            added += 1
                            if len(results) >= limit:
                                return added
                    except Exception:
                        continue
                return added

            collect()
            scrolls = 0
            stagnant_rounds = 0
            max_scrolls = max(6, min(50, max(6, limit // 20)))
            while len(results) < limit and scrolls < max_scrolls and stagnant_rounds < 3:
                before_count = len(results)
                try:
                    page.mouse.wheel(0, 2200)
                except Exception:
                    try:
                        page.evaluate("window.scrollBy(0, Math.max(1200, Math.floor(window.innerHeight * 1.8)))")
                    except Exception:
                        break
                page.wait_for_timeout(900)
                added = collect()
                scrolls += 1
                if added <= 0 and len(results) == before_count:
                    stagnant_rounds += 1
                else:
                    stagnant_rounds = 0

            results = self._sort_messages_desc(results)
            self._set_pagination_stats("search_dom", max(1, scrolls + 1), len(results))
            return results[:limit]
        finally:
            try:
                page.close()
            except Exception:
                pass

    def _slack_api_call(
        self,
        endpoint: str,
        params: dict | None = None,
        method: str = "GET",
        body: dict | None = None,
    ) -> dict[str, Any]:
        base_url = f"{self.config.slack_api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        url = f"{base_url}?{urlencode(params or {})}" if params else base_url
        request = self.session.request()
        last_error: Exception | None = None
        last_status: int | None = None
        last_data: Any | None = None

        max_attempts = max(1, int(self.config.max_retries or 1))
        for attempt in range(max_attempts):
            token = self._get_web_token()
            if not token:
                raise RuntimeError(
                    "Slack web token not found. Recreate browser storage state "
                    "with scripts/create_storage_state.py to avoid re-login."
                )
            headers = {"Content-Type": "application/json; charset=utf-8", "Authorization": f"Bearer {token}"}
            try:
                if method.upper() == "GET":
                    response = request.get(url, headers=headers)
                else:
                    payload = json.dumps(body or {})
                    response = request.fetch(url, method=method, headers=headers, data=payload)

                status = response.status
                try:
                    data: Any = response.json()
                except Exception:
                    data = {}
                last_status = status
                last_data = data

                if status == 429:
                    retry_after = response.headers.get("retry-after")
                    try:
                        sleep_s = float(retry_after) if retry_after else 1.0
                    except Exception:
                        sleep_s = 1.0
                    self.stats["rate_limit_hits"] += 1
                    self.stats["rate_limit_sleep_s"] += sleep_s
                    if attempt < max_attempts - 1:
                        self.stats["retries"] += 1
                        time.sleep(sleep_s)
                        continue
                    raise RuntimeError("Slack API rate limit exceeded (browser)")

                if self._is_auth_error(status, data):
                    raise SessionExpiredError(f"Slack auth error (browser): {status}")

                if not (200 <= status < 300):
                    error = data.get("error") if isinstance(data, dict) else "unknown_error"
                    logger.error(f"Slack API error (browser): {status} {error}")
                    raise RuntimeError(f"Slack API error (browser): {status} {error}")

                self.stats["api_calls"] += 1

                if isinstance(data, dict) and not data.get("ok", True):
                    error_msg = data.get("error", "unknown_error")
                    logger.error(f"Slack API error (browser): {error_msg}")
                    raise RuntimeError(f"Slack API error (browser): {error_msg}")

                if not isinstance(data, dict):
                    logger.error("Slack API error (browser): invalid response")
                    raise RuntimeError("Slack API error (browser): invalid response")

                logger.info(f"Slack API call successful: {endpoint}")
                return cast(dict[str, Any], data)
            except SessionExpiredError as e:
                last_error = e
                self.stats["errors"] += 1
                if attempt < max_attempts - 1:
                    self.stats["retries"] += 1
                    logger.warning("Slack auth failed; refreshing web token and retrying.")
                    self._refresh_web_token()
                    continue
                self._log_api_failure(endpoint, str(e), last_status, last_data)
                raise
            except Exception as e:
                last_error = e
                self.stats["errors"] += 1
                logger.error(f"Failed to execute Slack API call: {e}")
                if attempt < max_attempts - 1:
                    self.stats["retries"] += 1
                    time.sleep(self.config.retry_delay_ms / 1000)
                    continue
                self._log_api_failure(endpoint, str(e), last_status, last_data)
                raise
        if last_error:
            raise last_error
        raise RuntimeError("Slack API call failed")

    def _get_web_token(self) -> str | None:
        if self._web_token:
            return self._web_token

        workspace_id = self.config.slack_workspace_id

        def _extract_token_from_storage_state() -> str | None:
            try:
                state = self.session.context.storage_state()
            except Exception:
                return None
            for origin in state.get("origins", []):
                if "slack.com" not in origin.get("origin", ""):
                    continue
                for entry in origin.get("localStorage", []):
                    if entry.get("name") not in {"localConfig_v2", "localConfig"}:
                        continue
                    raw = entry.get("value")
                    if not isinstance(raw, str):
                        continue
                    try:
                        parsed = json.loads(raw)
                    except Exception:
                        continue
                    teams = parsed.get("teams") if isinstance(parsed, dict) else None
                    if not isinstance(teams, dict):
                        continue
                    if workspace_id and workspace_id in teams and isinstance(teams[workspace_id], dict):
                        token = teams[workspace_id].get("token")
                        if isinstance(token, str):
                            return token
                    for team in teams.values():
                        if isinstance(team, dict):
                            token = team.get("token")
                            if isinstance(token, str):
                                return token
            return None

        def action(page):
            for _ in range(4):
                token = _extract_token_from_storage_state()
                if token:
                    return token
                try:
                    token = page.evaluate(
                        """
                    (workspaceId) => {
                        const keys = ["localConfig_v2", "localConfig"];
                        for (const key of keys) {
                            const raw = window.localStorage.getItem(key);
                            if (!raw) continue;
                            try {
                                const parsed = JSON.parse(raw);
                                const teams = parsed && parsed.teams ? parsed.teams : null;
                                if (!teams) continue;
                                if (workspaceId && teams[workspaceId] && teams[workspaceId].token) {
                                    return teams[workspaceId].token;
                                }
                                for (const id of Object.keys(teams)) {
                                    const team = teams[id];
                                    if (team && team.token) return team.token;
                                }
                            } catch (e) {
                                continue;
                            }
                        }
                        return null;
                    }
                    """,
                        workspace_id or None,
                    )
                    if token:
                        return token
                except Exception:
                    pass
                page.wait_for_timeout(500)
            return None

        token = self._with_page(self._slack_client_home(), action)
        if isinstance(token, str) and token:
            self._web_token = token
            if self.config.auto_save_storage_state:
                self.session.save_storage_state()
            return self._web_token

        if self.config.interactive_login and not self.config.headless:
            token = self._interactive_login_slack()
            if isinstance(token, str) and token:
                self._web_token = token
        return self._web_token

    def _is_auth_error(self, status: int | None, data: Any) -> bool:
        auth_errors = {"not_authed", "invalid_auth", "token_revoked", "account_inactive", "token_expired"}
        if status in {401, 403}:
            return True
        if isinstance(data, dict):
            return data.get("error") in auth_errors
        return False

    def _refresh_web_token(self) -> str | None:
        previous = self._web_token
        self._web_token = None
        token = self._get_web_token()
        if token and token != previous:
            logger.info("Slack web token refreshed.")
            if self.config.auto_save_storage_state:
                self.session.save_storage_state()
        return token

    def _interactive_login_slack(self) -> str | None:
        page = self.session.new_page(self._slack_client_home())
        try:
            logger.warning(
                "Slack login required. Complete login in the opened browser window (waiting up to %s seconds).",
                int(self.config.interactive_login_timeout_ms / 1000),
            )
            page.wait_for_selector(
                "div[role='application'], div[data-qa='client_container']",
                timeout=self.config.interactive_login_timeout_ms,
            )
            if self.config.auto_save_storage_state:
                self.session.save_storage_state()
            token = self._get_web_token()
            if isinstance(token, str) and token:
                return token
        except Exception as exc:
            logger.error("Slack interactive login failed: %s", exc)
        finally:
            try:
                page.close()
            except Exception:
                pass
        return None

    def fetch_channel_history_paginated(
        self,
        channel_id: str,
        latest: str | None = None,
        oldest: str | None = None,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict]:
        messages: list[dict] = []
        cursor: str | None = None
        page = 0

        try:
            while True:
                params = {"channel": channel_id, "limit": limit}
                if latest:
                    params["latest"] = latest
                if oldest:
                    params["oldest"] = oldest
                if cursor:
                    params["cursor"] = cursor
                data = self._slack_api_call("conversations.history", params=params)
                messages.extend(data.get("messages", []))
                cursor = data.get("response_metadata", {}).get("next_cursor")
                page += 1
                if not cursor or page >= max_pages:
                    break
            self._set_pagination_stats("history", page, len(messages))
            return messages
        except Exception as exc:
            if self._should_fallback_to_dom(exc):
                logger.warning("Slack API unavailable; falling back to DOM extraction.")
                dom_limit = max(1, limit) * max(1, max_pages)
                return self._fetch_channel_history_dom(channel_id, latest=latest, oldest=oldest, limit=dom_limit)
            raise

    def search_messages_paginated(self, query: str, count: int = 100, max_pages: int = 5) -> list[dict]:
        matches: list[dict] = []
        page = 1
        try:
            while True:
                params = {"query": query, "count": count, "page": page}
                data = self._slack_api_call("search.messages", params=params)
                message_block = data.get("messages", {}) if isinstance(data, dict) else {}
                matches.extend(message_block.get("matches", []))
                paging = message_block.get("paging", {}) if isinstance(message_block, dict) else {}
                total_pages = paging.get("pages")
                if not total_pages or page >= total_pages or page >= max_pages:
                    break
                page += 1
            self._set_pagination_stats("search", page, len(matches))
            return matches
        except Exception as exc:
            if self._should_fallback_to_dom(exc):
                logger.warning("Slack API search unavailable; falling back to DOM search.")
                dom_limit = max(1, count) * max(1, max_pages)
                return self._search_messages_dom(query, limit=dom_limit)
            raise

    def list_conversations_paginated(
        self,
        types: str = "im,mpim",
        limit: int = 200,
        max_pages: int = 10,
        exclude_archived: bool = True,
    ) -> list[dict[str, Any]]:
        """List conversations (supports DMs via types=im,mpim)."""
        conversations: list[dict[str, Any]] = []
        cursor: str | None = None
        page = 0
        try:
            while True:
                params: dict[str, Any] = {
                    "types": types,
                    "limit": limit,
                    "exclude_archived": 1 if exclude_archived else 0,
                }
                if cursor:
                    params["cursor"] = cursor
                data = self._slack_api_call("conversations.list", params=params)
                conversations.extend(cast(list[dict[str, Any]], data.get("channels", [])))
                cursor = cast(dict, data.get("response_metadata", {}) or {}).get("next_cursor")
                page += 1
                if not cursor or page >= max_pages:
                    break
            self._set_pagination_stats("conversations.list", page, len(conversations))
            return conversations
        except Exception as exc:
            if self._should_fallback_to_dom(exc):
                logger.warning("Slack API conversations.list unavailable; falling back to DOM sidebar parsing.")
                dom_limit = max(1, limit) * max(1, max_pages)
                return self._list_conversations_dom(limit=dom_limit)
            raise

    def fetch_thread_replies_paginated(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        cursor: str | None = None
        page = 0
        try:
            while True:
                params: dict[str, Any] = {"channel": channel_id, "ts": thread_ts, "limit": limit}
                if cursor:
                    params["cursor"] = cursor
                data = self._slack_api_call("conversations.replies", params=params)
                messages.extend(cast(list[dict[str, Any]], data.get("messages", [])))
                cursor = cast(dict, data.get("response_metadata", {}) or {}).get("next_cursor")
                page += 1
                if not cursor or page >= max_pages:
                    break
            return messages
        except Exception as exc:
            if self._should_fallback_to_dom(exc):
                logger.warning("Slack API thread replies unavailable; falling back to DOM thread extraction.")
                dom_limit = max(1, limit) * max(1, max_pages)
                dom_replies = self._fetch_thread_replies_dom(channel_id, thread_ts=thread_ts, limit=dom_limit)
                if dom_replies:
                    return dom_replies
                logger.warning("Thread pane fallback unavailable; using channel history approximation.")
                history = self._fetch_channel_history_dom(channel_id, limit=max(200, dom_limit))
                target_thread_ts = self._normalize_ts(thread_ts) or thread_ts
                replies = [
                    message
                    for message in history
                    if (
                        (self._normalize_ts(message.get("thread_ts")) or str(message.get("thread_ts") or ""))
                        == target_thread_ts
                        or (self._normalize_ts(message.get("ts")) or str(message.get("ts") or "")) == target_thread_ts
                    )
                ]
                return replies[:dom_limit]
            raise

    def get_message_permalink(self, channel_id: str, message_ts: str) -> str | None:
        try:
            data = self._slack_api_call("chat.getPermalink", params={"channel": channel_id, "message_ts": message_ts})
            return cast(str | None, data.get("permalink"))
        except Exception:
            return None

    def update_channel_topic(self, channel_id: str, topic: str) -> None:
        self._slack_api_call("conversations.setTopic", method="POST", body={"channel": channel_id, "topic": topic})

    def get_channel_info(self, channel_id: str) -> dict[str, Any]:
        try:
            data = self._slack_api_call("conversations.info", params={"channel": channel_id})
            return cast(dict[str, Any], data.get("channel", {}))
        except Exception as exc:
            if self._should_fallback_to_dom(exc):
                logger.warning("Slack API channel info unavailable; falling back to DOM channel header parsing.")
                return self._get_channel_info_dom(channel_id)
            raise

    def get_user_info(self, user_id: str) -> dict[str, Any]:
        try:
            data = self._slack_api_call("users.info", params={"user": user_id})
            return cast(dict[str, Any], data.get("user", {}))
        except Exception as exc:
            if self._should_fallback_to_dom(exc):
                logger.warning("Slack API user info unavailable; returning minimal DOM-safe user info.")
                return {
                    "id": user_id,
                    "name": user_id,
                    "real_name": user_id,
                    "profile": {"real_name": user_id, "display_name": user_id},
                }
            raise

    def auth_test(self) -> dict[str, Any]:
        try:
            return self._slack_api_call("auth.test")
        except Exception as exc:
            if self._should_fallback_to_dom(exc):
                logger.warning("Slack API auth.test unavailable; using DOM auth check fallback.")
                return self._auth_test_dom()
            raise

    def _get_channel_info_dom(self, channel_id: str) -> dict[str, Any]:
        page = self.session.new_page(self._channel_url(channel_id))
        try:
            self._wait_until_ready(page)
            name = ""
            topic = ""
            for selector in CHANNEL_HEADER_NAME.get_all():
                try:
                    locator = page.locator(selector).first
                    if locator.count() > 0 and locator.is_visible(timeout=1000):
                        name = (locator.inner_text() or "").strip()
                        if name:
                            break
                except Exception:
                    continue
            for selector in CHANNEL_TOPIC.get_all():
                try:
                    locator = page.locator(selector).first
                    if locator.count() > 0 and locator.is_visible(timeout=1000):
                        topic = (locator.inner_text() or "").strip()
                        if topic:
                            break
                except Exception:
                    continue
            if not name:
                name = channel_id
            return {
                "id": channel_id,
                "name": name,
                "name_normalized": name.lower().replace(" ", "-"),
                "topic": {"value": topic},
            }
        finally:
            try:
                page.close()
            except Exception:
                pass

    def _list_conversations_dom(self, limit: int = 200) -> list[dict[str, Any]]:
        page = self.session.new_page(self._slack_client_home())
        results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        try:
            self._wait_until_ready(page)
            DOMExtractor(page).wait_for_element(CHANNEL_SIDEBAR, timeout=10000)
            for anchor in page.locator("a[href*='/client/']").all():
                if len(results) >= limit:
                    break
                try:
                    href = anchor.get_attribute("href") or ""
                    channel_id = self._parse_channel_id_from_text(href)
                    if not channel_id or channel_id in seen_ids:
                        continue
                    name = (anchor.inner_text() or "").strip().split("\n")[0].strip()
                    if not name:
                        name = channel_id
                    seen_ids.add(channel_id)
                    results.append(
                        {
                            "id": channel_id,
                            "name": name,
                            "name_normalized": name.lower().replace(" ", "-"),
                            "is_archived": False,
                        }
                    )
                except Exception:
                    continue
            self._set_pagination_stats("conversations_dom", 1, len(results))
            return results
        finally:
            try:
                page.close()
            except Exception:
                pass

    def _auth_test_dom(self) -> dict[str, Any]:
        page = self.session.new_page(self._slack_client_home())
        try:
            self._wait_until_ready(page)
            team_id = self._parse_workspace_id_from_text(page.url or "")
            if not team_id:
                team_id = self.config.slack_workspace_id or None
            return {
                "ok": True,
                "user": "browser_session",
                "user_id": "browser_session",
                "team_id": team_id,
                "team": team_id,
            }
        finally:
            try:
                page.close()
            except Exception:
                pass

    def reset_stats(self) -> None:
        super().reset_stats()
        self.stats.update(
            {
                "api_calls": 0,
                "retries": 0,
                "rate_limit_hits": 0,
                "rate_limit_sleep_s": 0.0,
                "retry_sleep_s": 0.0,
            }
        )
        self.pagination_stats = {}

    def get_stats(self) -> dict[str, Any]:
        return dict(self.stats)

    def get_pagination_stats(self) -> dict[str, Any]:
        return dict(self.pagination_stats)

    def _set_pagination_stats(self, method: str, pages: int, messages: int) -> None:
        self.pagination_stats = {
            "method": method,
            "pages": pages,
            "messages": messages,
        }
