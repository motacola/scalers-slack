import os
import requests


class SlackClient:
    def __init__(self, token: str | None = None, base_url: str = "https://slack.com/api"):
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, params: dict | None = None, json_body: dict | None = None) -> dict:
        if not self.token:
            raise RuntimeError("SLACK_BOT_TOKEN is not set")

        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        response = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=30)
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Slack API error: {response.status_code} {response.text}") from exc

        if response.status_code >= 400:
            error = data.get("error", response.text) if isinstance(data, dict) else response.text
            raise RuntimeError(f"Slack API error: {response.status_code} {error}")

        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error', 'unknown_error')}")

        return data

    def fetch_channel_history(self, channel_id: str, latest: str | None = None, oldest: str | None = None, limit: int = 200) -> list[dict]:
        params = {"channel": channel_id, "limit": limit}
        if latest:
            params["latest"] = latest
        if oldest:
            params["oldest"] = oldest
        data = self._request("GET", "conversations.history", params=params)
        return data.get("messages", [])

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

            data = self._request("GET", "conversations.history", params=params)
            messages.extend(data.get("messages", []))

            cursor = data.get("response_metadata", {}).get("next_cursor")
            page += 1
            if not cursor or page >= max_pages:
                break

        return messages

    def fetch_thread_replies(self, channel_id: str, thread_ts: str, limit: int = 200) -> list[dict]:
        params = {"channel": channel_id, "ts": thread_ts, "limit": limit}
        data = self._request("GET", "conversations.replies", params=params)
        return data.get("messages", [])

    def fetch_thread_replies_paginated(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict]:
        messages: list[dict] = []
        cursor: str | None = None
        page = 0

        while True:
            params = {"channel": channel_id, "ts": thread_ts, "limit": limit}
            if cursor:
                params["cursor"] = cursor

            data = self._request("GET", "conversations.replies", params=params)
            messages.extend(data.get("messages", []))

            cursor = data.get("response_metadata", {}).get("next_cursor")
            page += 1
            if not cursor or page >= max_pages:
                break

        return messages

    def search_messages(self, query: str, count: int = 100) -> list[dict]:
        params = {"query": query, "count": count}
        data = self._request("GET", "search.messages", params=params)
        return data.get("messages", {}).get("matches", [])

    def search_messages_paginated(self, query: str, count: int = 100, max_pages: int = 5) -> list[dict]:
        matches: list[dict] = []
        page = 1

        while True:
            params = {"query": query, "count": count, "page": page}
            data = self._request("GET", "search.messages", params=params)
            message_block = data.get("messages", {})
            matches.extend(message_block.get("matches", []))

            paging = message_block.get("paging", {}) if isinstance(message_block, dict) else {}
            total_pages = paging.get("pages")
            if not total_pages or page >= total_pages or page >= max_pages:
                break
            page += 1

        return matches

    def update_channel_topic(self, channel_id: str, topic: str) -> None:
        payload = {"channel": channel_id, "topic": topic}
        self._request("POST", "conversations.setTopic", json_body=payload)

    def get_channel_info(self, channel_id: str) -> dict:
        params = {"channel": channel_id}
        data = self._request("GET", "conversations.info", params=params)
        return data.get("channel", {})
