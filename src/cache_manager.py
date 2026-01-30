"""Cache management for Slack API responses."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


class CacheManager:
    """Manages caching of Slack API responses."""

    def __init__(self, cache_dir: str = ".cache", ttl_seconds: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, endpoint: str, params: dict[str, Any]) -> str:
        """Generate a cache key from endpoint and params."""
        key_data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Get cached data if it exists and is not expired."""
        cache_key = self._get_cache_key(endpoint, params)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)

            # Check if expired
            cached_time = cached.get("_cached_at", 0)
            if time.time() - cached_time > self.ttl_seconds:
                cache_path.unlink()
                return None

            return cached.get("data")
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, endpoint: str, params: dict[str, Any], data: dict[str, Any]) -> None:
        """Cache data with timestamp."""
        cache_key = self._get_cache_key(endpoint, params)
        cache_path = self._get_cache_path(cache_key)

        cached = {
            "_cached_at": time.time(),
            "endpoint": endpoint,
            "data": data,
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cached, f)

    def clear(self) -> None:
        """Clear all cached data."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

    def clear_expired(self) -> int:
        """Clear expired cache entries. Returns count of removed files."""
        removed = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                cached_time = cached.get("_cached_at", 0)
                if time.time() - cached_time > self.ttl_seconds:
                    cache_file.unlink()
                    removed += 1
            except (json.JSONDecodeError, OSError):
                cache_file.unlink()
                removed += 1
        return removed

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_files = 0
        total_size = 0
        expired_files = 0
        now = time.time()

        for cache_file in self.cache_dir.glob("*.json"):
            total_files += 1
            total_size += cache_file.stat().st_size
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if now - cached.get("_cached_at", 0) > self.ttl_seconds:
                    expired_files += 1
            except (json.JSONDecodeError, OSError):
                expired_files += 1

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "expired_files": expired_files,
            "cache_dir": str(self.cache_dir),
            "ttl_seconds": self.ttl_seconds,
        }