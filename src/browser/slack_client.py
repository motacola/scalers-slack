from __future__ import annotations

import json
import logging
import time
from typing import Any, cast
from urllib.parse import urlencode

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
                if self.config.auto_save_storage_state:
                    self.session.save_storage_state()
                return
            page.wait_for_timeout(1000)
        raise RuntimeError("Timed out waiting for Slack readiness")


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

        for attempt in range(2):
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
                
                if self._is_auth_error(status, data):
                    raise SessionExpiredError(f"Slack auth error (browser): {status}")
                
                if not (200 <= status < 300):
                    error = data.get("error") if isinstance(data, dict) else "unknown_error"
                    logger.error(f"Slack API error (browser): {status} {error}")
                    raise RuntimeError(f"Slack API error (browser): {status} {error}")

                self.stats["api_calls"] += 1
                if status == 429:
                    self.stats["rate_limit_hits"] += 1
                    logger.warning(f"Rate limit hit for Slack API endpoint: {endpoint}")


                if status and status >= 400:
                    error = data.get("error") if isinstance(data, dict) else "unknown_error"
                    logger.error(f"Slack API error (browser): {status} {error}")
                    raise RuntimeError(f"Slack API error (browser): {status} {error}")

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
                if attempt == 0:
                    logger.warning("Slack auth failed; refreshing web token and retrying.")
                    self._refresh_web_token()
                    continue
                raise
            except Exception as e:
                last_error = e
                logger.error(f"Failed to execute Slack API call: {e}")
                if attempt >= 1:
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
            return _extract_token_from_storage_state()

        token = self._with_page(self._slack_client_home(), action)
        if isinstance(token, str) and token:
            self._web_token = token
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

    def search_messages_paginated(self, query: str, count: int = 100, max_pages: int = 5) -> list[dict]:
        matches: list[dict] = []
        page = 1
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
