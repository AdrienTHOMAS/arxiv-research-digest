"""Tests for the cache service."""

from __future__ import annotations

from arxiv_digest.services.cache_service import CacheService


def test_cache_set_and_get() -> None:
    """CacheService can set and retrieve values."""
    cache = CacheService(cache_dir="/tmp/arxiv-test-cache-svc")
    cache.set("test_key", "test_value", ttl=60)
    result = cache.get("test_key")
    assert result == "test_value"
    cache.delete("test_key")


def test_cache_get_missing_key() -> None:
    """CacheService.get() returns None for missing keys."""
    cache = CacheService(cache_dir="/tmp/arxiv-test-cache-svc")
    result = cache.get("nonexistent_key_12345")
    assert result is None


def test_cache_delete() -> None:
    """CacheService.delete() removes a cached value."""
    cache = CacheService(cache_dir="/tmp/arxiv-test-cache-svc")
    cache.set("del_key", "value", ttl=60)
    cache.delete("del_key")
    result = cache.get("del_key")
    assert result is None


def test_cache_clear() -> None:
    """CacheService.clear() removes all cached values."""
    cache = CacheService(cache_dir="/tmp/arxiv-test-cache-svc")
    cache.set("clear_key1", "v1", ttl=60)
    cache.set("clear_key2", "v2", ttl=60)
    cache.clear()
    assert cache.get("clear_key1") is None
    assert cache.get("clear_key2") is None
