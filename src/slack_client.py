import os
import random
import time
from typing import Any, cast

import requests


class SlackClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://slack.com/api",
        timeout: int = 30,
        retry_config: dict | None = None,
    ):
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retry_max_attempts: int = 5
        self.retry_backoff_base: float = 0.5
        self.retry_backoff_max: float = 8.0
        self.retry_jitter: float = 0.25
        self.retry_on_status: set[int] = {408, 429, 500, 502, 503, 504}
        self.retry_on_network_error: bool = True
        self._configure_retries(retry_config or {})

    def _configure_retries(self, config: dict) -> None:
        self.retry_max_attempts = int(config.get("max_attempts", 5))
        self.retry_backoff_base = float(config.get("backoff_base", 0.5))
        self.retry_backoff_max = float(config.get("backoff_max", 8.0))
        self.retry_jitter = float(config.get("jitter", 0.25))
        self.retry_on_status = set(config.get("retry_on_status", [408, 429, 500, 502, 503, 504]))
        self.retry_on_network_error = bool(config.get("retry_on_network_error", True))

    def _compute_backoff(self, attempt: int, retry_after: float | None = None) -> float:
        base = float(min(self.retry_backoff_max, self.retry_backoff_base * (2 ** max(attempt - 1, 0))))
        if retry_after is not None:
            base = float(max(base, retry_after))
        jitter = float(random.uniform(0, self.retry_jitter)) if self.retry_jitter > 0 else 0.0
        return float(base + jitter)

    def _parse_retry_after(self, response: requests.Response) -> float | None:
        headers = cast(dict[str, str], response.headers)
        retry_after = headers.get("Retry-After")
        if retry_after is None:
            return None
        try:
            value = float(retry_after)
        except (TypeError, ValueError):
            return None
        return max(0.0, value)

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError("SLACK_BOT_TOKEN is not set")

        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        last_error: Exception | None = None
        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    timeout=self.timeout,
                )
            except requests.exceptions.RequestException as exc:
                last_error = exc
                if not self.retry_on_network_error or attempt >= self.retry_max_attempts:
                    raise RuntimeError("Slack API network error") from exc
                time.sleep(self._compute_backoff(attempt))
                continue

            try:
                data = cast(dict[str, Any], response.json())
            except ValueError as exc:
                last_error = exc
                if attempt >= self.retry_max_attempts:
                    raise RuntimeError(f"Slack API error: {response.status_code} {response.text}") from exc
                time.sleep(self._compute_backoff(attempt))
                continue

            if response.status_code == 429 or data.get("error") == "ratelimited":
                retry_after = self._parse_retry_after(response)
                if attempt >= self.retry_max_attempts:
                    raise RuntimeError("Slack API rate limited")
                time.sleep(self._compute_backoff(attempt, retry_after=retry_after))
                continue

            if response.status_code in self.retry_on_status and response.status_code >= 400:
                if attempt >= self.retry_max_attempts:
                    error = data.get("error", response.text) if isinstance(data, dict) else response.text
                    raise RuntimeError(f"Slack API error: {response.status_code} {error}")
                time.sleep(self._compute_backoff(attempt))
                continue

            if response.status_code >= 400:
                error = data.get("error", response.text)
                raise RuntimeError(f"Slack API error: {response.status_code} {error}")

            if not data.get("ok"):
                error_message = data.get("error", "unknown_error")
                raise RuntimeError(f"Slack API error: {error_message}")

            return data

        if last_error:
            raise RuntimeError("Slack API request failed") from last_error
        raise RuntimeError("Slack API request failed")

    def fetch_channel_history(
        self,
        channel_id: str,
        latest: str | None = None,
        oldest: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        params = {"channel": channel_id, "limit": limit}
        if latest:
            params["latest"] = latest
        if oldest:
            params["oldest"] = oldest
        data = self._request("GET", "conversations.history", params=params)
        return cast(list[dict[str, Any]], data.get("messages", []))

    def fetch_channel_history_paginated(
        self,
        channel_id: str,
        latest: str | None = None,
        oldest: str | None = None,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
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

            data = self._request("GET", "conversations.history", params=params)
            messages.extend(cast(list[dict[str, Any]], data.get("messages", [])))

            cursor = data.get("response_metadata", {}).get("next_cursor")
            page += 1
            if not cursor or page >= max_pages:
                break

        return messages

    def fetch_thread_replies(self, channel_id: str, thread_ts: str, limit: int = 200) -> list[dict[str, Any]]:
        params = {"channel": channel_id, "ts": thread_ts, "limit": limit}
        data = self._request("GET", "conversations.replies", params=params)
        return cast(list[dict[str, Any]], data.get("messages", []))

    def fetch_thread_replies_paginated(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        messages: list[dict] = []
        cursor: str | None = None
        page = 0

        while True:
            params = {"channel": channel_id, "ts": thread_ts, "limit": limit}
            if cursor:
                params["cursor"] = cursor

            data = self._request("GET", "conversations.replies", params=params)
            messages.extend(cast(list[dict[str, Any]], data.get("messages", [])))

            cursor = data.get("response_metadata", {}).get("next_cursor")
            page += 1
            if not cursor or page >= max_pages:
                break

        return messages

    def search_messages(self, query: str, count: int = 100) -> list[dict[str, Any]]:
        params = {"query": query, "count": count}
        data = self._request("GET", "search.messages", params=params)
        return cast(list[dict[str, Any]], data.get("messages", {}).get("matches", []))

    def search_messages_paginated(self, query: str, count: int = 100, max_pages: int = 5) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        page = 1

        while True:
            params = {"query": query, "count": count, "page": page}
            data = self._request("GET", "search.messages", params=params)
            message_block = cast(dict[str, Any], data.get("messages", {}))
            matches.extend(cast(list[dict[str, Any]], message_block.get("matches", [])))

            paging = cast(dict[str, Any], message_block.get("paging", {}))
            total_pages = paging.get("pages")
            if not total_pages or page >= total_pages or page >= max_pages:
                break
            page += 1

        return matches

    def update_channel_topic(self, channel_id: str, topic: str) -> None:
        payload = {"channel": channel_id, "topic": topic}
        self._request("POST", "conversations.setTopic", json_body=payload)

    def get_channel_info(self, channel_id: str) -> dict[str, Any]:
        params = {"channel": channel_id}
        data = self._request("GET", "conversations.info", params=params)
        return cast(dict[str, Any], data.get("channel", {}))
