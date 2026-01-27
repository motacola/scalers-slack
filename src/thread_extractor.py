from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Protocol

from .models import Thread


class SlackClientProtocol(Protocol):
    def fetch_channel_history_paginated(
        self,
        channel_id: str,
        latest: str | None = None,
        oldest: str | None = None,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]: ...

    def search_messages_paginated(self, query: str, count: int = 100, max_pages: int = 5) -> list[dict[str, Any]]: ...


class ThreadExtractor:
    def __init__(self, slack_client: SlackClientProtocol):
        self.slack_client = slack_client

    def search_threads(
        self,
        query: str,
        channel_id: str | None = None,
        limit: int = 100,
        max_pages: int = 5,
    ) -> list[Thread]:
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
    ) -> list[Thread]:
        messages = self.slack_client.fetch_channel_history_paginated(
            channel_id=channel_id,
            oldest=oldest,
            latest=latest,
            limit=limit,
            max_pages=max_pages,
        )
        threads = defaultdict(list)
        for message in messages:
            thread_ts = message.get("thread_ts") or message.get("ts")
            if not thread_ts:
                continue
            threads[thread_ts].append(message)


        return [self._summarize_thread(thread_ts, items, channel_id=channel_id) for thread_ts, items in threads.items()]

    def _summarize_thread(self, thread_ts: str, items: list[dict], channel_id: str | None = None) -> Thread:
        if not items:
            return Thread(
                thread_ts=thread_ts,
                channel_id=channel_id,
                message_count=0,
                text="",
                created_at=None,
                reply_count=None,
                permalink=None,
            )
        first = items[0]
        created_at = None
        try:
            ts_float = float(thread_ts)
            created_at = datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()
        except (TypeError, ValueError):
            created_at = None
        channel = first.get("channel", {}).get("id") or first.get("channel_id") or channel_id
        reply_count = first.get("reply_count")
        if reply_count is None and len(items) > 1:
            reply_count = max(len(items) - 1, 0)

        return Thread(
            thread_ts=thread_ts,
            channel_id=channel,
            user_id=first.get("user"),
            message_count=len(items),
            text=first.get("text") or "",
            created_at=created_at,
            reply_count=reply_count,
            permalink=first.get("permalink"),
        )

