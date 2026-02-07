from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, cast
from urllib.parse import urlencode, urljoin

from .base import (
    BaseBrowserClient,
    BrowserAutomationConfig,
    BrowserSession,
    SessionExpiredError,
)
from ..dom_selectors import DOMExtractor, MESSAGE_CONTAINER, MESSAGE_LIST_CONTAINER, SEARCH_RESULT

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
                if self._has_web_token(page):
                    if self.config.auto_save_storage_state:
                        self.session.save_storage_state()
                    return
            page.wait_for_timeout(1000)
        raise RuntimeError("Timed out waiting for Slack readiness (token not detected)")

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
        )

    def _fetch_channel_history_dom(
        self,
        channel_id: str,
        limit: int = 200,
        max_scrolls: int = 5,
    ) -> list[dict[str, Any]]:
        url = self._channel_url(channel_id)
        page = self.session.new_page(url)
        messages: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            extractor = DOMExtractor(page)
            if not extractor.wait_for_element(MESSAGE_LIST_CONTAINER, timeout=20000):
                raise RuntimeError("Slack DOM not ready for message extraction")

            def collect() -> None:
                for selector in MESSAGE_CONTAINER.get_all():
                    try:
                        for element in page.locator(selector).all():
                            data = extractor.extract_message_data(element)
                            if not data:
                                continue
                            key = data.get("ts") or f"{data.get('user')}::{data.get('text')}"
                            if key in seen:
                                continue
                            seen.add(key)
                            messages.append(data)
                    except Exception:
                        continue

            collect()
            container = extractor.scroll_container()
            scrolls = 0
            while len(messages) < limit and container is not None and scrolls < max_scrolls:
                try:
                    container.evaluate("el => el.scrollBy(0, -el.scrollHeight)")
                except Exception:
                    break
                page.wait_for_timeout(1000)
                collect()
                scrolls += 1

            return messages[:limit]
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

        if not text and not permalink:
            return None
        return {
            "text": text,
            "permalink": permalink,
            "ts": ts,
        }

    def _search_messages_dom(self, query: str, limit: int = 100) -> list[dict[str, Any]]:
        url = self._search_url(query)
        page = self.session.new_page(url)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            if not DOMExtractor(page).wait_for_element(SEARCH_RESULT, timeout=20000):
                raise RuntimeError("Slack search results not ready")

            for selector in SEARCH_RESULT.get_all():
                try:
                    for element in page.locator(selector).all():
                        data = self._extract_search_result_data(element, page)
                        if not data:
                            continue
                        key = data.get("ts") or data.get("permalink") or data.get("text")
                        if not key or key in seen:
                            continue
                        seen.add(key)
                        results.append(data)
                        if len(results) >= limit:
                            break
                    if len(results) >= limit:
                        break
                except Exception:
                    continue
            self._set_pagination_stats("search_dom", 1, len(results))
            return results
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
            token = _extract_token_from_storage_state()
            if token:
                return token
            try:
                return page.evaluate(
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
            except Exception:
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
                return self._fetch_channel_history_dom(channel_id, limit=dom_limit)
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

    def get_message_permalink(self, channel_id: str, message_ts: str) -> str | None:
        try:
            data = self._slack_api_call("chat.getPermalink", params={"channel": channel_id, "message_ts": message_ts})
            return cast(str | None, data.get("permalink"))
        except Exception:
            return None

    def update_channel_topic(self, channel_id: str, topic: str) -> None:
        self._slack_api_call("conversations.setTopic", method="POST", body={"channel": channel_id, "topic": topic})

    def get_channel_info(self, channel_id: str) -> dict[str, Any]:
        data = self._slack_api_call("conversations.info", params={"channel": channel_id})
        return cast(dict[str, Any], data.get("channel", {}))

    def get_user_info(self, user_id: str) -> dict[str, Any]:
        data = self._slack_api_call("users.info", params={"user": user_id})
        return cast(dict[str, Any], data.get("user", {}))

    def auth_test(self) -> dict[str, Any]:
        return self._slack_api_call("auth.test")

    def reset_stats(self) -> None:
        super().reset_stats()
        self.stats.update({
            "api_calls": 0,
            "retries": 0,
            "rate_limit_hits": 0,
            "rate_limit_sleep_s": 0.0,
            "retry_sleep_s": 0.0,
        })
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
