"""Simple in-memory TTL cache for LLM responses.

Used to avoid repeated inference for identical prompts. Each entry
expires after a configurable TTL (default 1 hour). Expired entries
are evicted lazily on the next get() call.
"""

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None

        if entry.expires_at <= time.time():
            self._store.pop(key, None)
            return None

        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._store[key] = CacheEntry(value=value, expires_at=time.time() + ttl_seconds)


llm_cache = TTLCache()
