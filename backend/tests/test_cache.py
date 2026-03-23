import time

from app.core.cache import TTLCache


def test_cache_returns_none_for_unknown_key():
    cache = TTLCache()
    assert cache.get("missing") is None


def test_cache_stores_and_retrieves_value():
    cache = TTLCache()
    cache.set("key", {"data": 42}, ttl_seconds=60)
    assert cache.get("key") == {"data": 42}


def test_cache_expires_after_ttl(monkeypatch):
    cache = TTLCache()
    cache.set("key", "value", ttl_seconds=10)

    future = time.time() + 11
    monkeypatch.setattr(time, "time", lambda: future)

    assert cache.get("key") is None
