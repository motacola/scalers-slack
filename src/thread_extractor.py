from collections import defaultdict
from datetime import datetime, timezone

from .slack_client import SlackClient


class ThreadExtractor:
    def __init__(self, slack_client: SlackClient):
        self.slack_client = slack_client

    def search_threads(self, query: str, channel_id: str | None = None, limit: int = 100) -> list[dict]:
        matches = self.slack_client.search_messages(query=query, count=limit)
        threads = defaultdict(list)

        for match in matches:
            if channel_id and match.get("channel", {}).get("id") != channel_id:
                continue
            thread_ts = match.get("thread_ts") or match.get("ts")
            threads[thread_ts].append(match)

        return [self._summarize_thread(thread_ts, items) for thread_ts, items in threads.items()]

    def fetch_channel_threads(self, channel_id: str, oldest: str | None = None, latest: str | None = None, limit: int = 200) -> list[dict]:
        messages = self.slack_client.fetch_channel_history(
            channel_id=channel_id,
            oldest=oldest,
            latest=latest,
            limit=limit,
        )
        threads = defaultdict(list)
        for message in messages:
            if message.get("thread_ts") or message.get("reply_count"):
                thread_ts = message.get("thread_ts") or message.get("ts")
                threads[thread_ts].append(message)

        return [self._summarize_thread(thread_ts, items) for thread_ts, items in threads.items()]

    def _summarize_thread(self, thread_ts: str, items: list[dict]) -> dict:
        first = items[0]
        ts_float = float(thread_ts)
        dt = datetime.fromtimestamp(ts_float, tz=timezone.utc)
        return {
            "thread_ts": thread_ts,
            "channel_id": first.get("channel", {}).get("id") or first.get("channel_id"),
            "message_count": len(items),
            "text_preview": (first.get("text") or "")[:120],
            "created_at": dt.isoformat(),
        }
