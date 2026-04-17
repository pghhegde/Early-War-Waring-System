"""
cache.py - Simple in-memory TTL cache for the AI Early Warning System.
Prevents redundant re-processing of the same region within a time window.
"""

import time
from typing import Any, Optional


class TTLCache:
    """Thread-safe in-memory cache with time-to-live expiry per key."""

    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, tuple[Any, float]] = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if it exists and hasn't expired, else None."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        """Store a value with TTL expiry."""
        self._store[key] = (value, time.monotonic() + self.ttl)

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()

    def stats(self) -> dict:
        """Return cache statistics."""
        now = time.monotonic()
        active = sum(1 for _, (_, exp) in self._store.items() if exp > now)
        return {"total_keys": len(self._store), "active_keys": active, "ttl_seconds": self.ttl}


# Singleton cache instance used across the backend
cache = TTLCache(ttl_seconds=300)  # 5-minute cache
