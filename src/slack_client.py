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
        data = response.json()
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

    def fetch_thread_replies(self, channel_id: str, thread_ts: str, limit: int = 200) -> list[dict]:
        params = {"channel": channel_id, "ts": thread_ts, "limit": limit}
        data = self._request("GET", "conversations.replies", params=params)
        return data.get("messages", [])

    def search_messages(self, query: str, count: int = 100) -> list[dict]:
        params = {"query": query, "count": count}
        data = self._request("GET", "search.messages", params=params)
        return data.get("messages", {}).get("matches", [])

    def update_channel_topic(self, channel_id: str, topic: str) -> None:
        payload = {"channel": channel_id, "topic": topic}
        self._request("POST", "conversations.setTopic", json_body=payload)

    def get_channel_info(self, channel_id: str) -> dict:
        params = {"channel": channel_id}
        data = self._request("GET", "conversations.info", params=params)
        return data.get("channel", {})
