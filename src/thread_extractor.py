from collections import defaultdict
from datetime import datetime, timezone

from .slack_client import SlackClient


class ThreadExtractor:
    def __init__(self, slack_client: SlackClient):
        self.slack_client = slack_client

    def search_threads(
        self,
        query: str,
        channel_id: str | None = None,
        limit: int = 100,
        max_pages: int = 5,
    ) -> list[dict]:
        matches = self.slack_client.search_messages_paginated(query=query, count=limit, max_pages=max_pages)
        threads = defaultdict(list)

        for match in matches:
            if channel_id and match.get("channel", {}).get("id") != channel_id:
                continue
            thread_ts = match.get("thread_ts") or match.get("ts")
            if not thread_ts:
                continue
            threads[thread_ts].append(match)

        return [self._summarize_thread(thread_ts, items) for thread_ts, items in threads.items()]

    def fetch_channel_threads(
        self,
        channel_id: str,
        oldest: str | None = None,
        latest: str | None = None,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict]:
        messages = self.slack_client.fetch_channel_history_paginated(
            channel_id=channel_id,
            oldest=oldest,
            latest=latest,
            limit=limit,
            max_pages=max_pages,
        )
        threads = defaultdict(list)
        for message in messages:
            if message.get("thread_ts") or message.get("reply_count"):
                thread_ts = message.get("thread_ts") or message.get("ts")
                if not thread_ts:
                    continue
                threads[thread_ts].append(message)

        return [self._summarize_thread(thread_ts, items, channel_id=channel_id) for thread_ts, items in threads.items()]

    def _summarize_thread(self, thread_ts: str, items: list[dict], channel_id: str | None = None) -> dict:
        if not items:
            return {
                "thread_ts": thread_ts,
                "channel_id": channel_id,
                "message_count": 0,
                "text_preview": "",
                "created_at": None,
            }
        first = items[0]
        created_at = None
        try:
            ts_float = float(thread_ts)
            created_at = datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()
        except (TypeError, ValueError):
            created_at = None
        channel = first.get("channel", {}).get("id") or first.get("channel_id") or channel_id
        return {
            "thread_ts": thread_ts,
            "channel_id": channel,
            "message_count": len(items),
            "text_preview": (first.get("text") or "")[:120],
            "created_at": created_at,
        }
