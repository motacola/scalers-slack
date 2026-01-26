from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Thread:
    thread_ts: str
    channel_id: Optional[str]
    created_at: Optional[str]
    text: str
    message_count: int
    reply_count: Optional[int] = None
    permalink: Optional[str] = None

    def preview(self, length: int = 120) -> str:
        text = self.text or ""
        return text[:length]
