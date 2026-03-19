"""Disk-based caching service wrapping :mod:`diskcache`.

Provides a thin, structlog-instrumented interface over :class:`diskcache.Cache`
with configurable TTL. Falls back to a no-op implementation when the
``diskcache`` package is not installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

try:
    import diskcache  # type: ignore[import-untyped]

    _HAS_DISKCACHE = True
except ImportError:
    _HAS_DISKCACHE = False
    logger.warning(
        "cache.diskcache_unavailable",
        detail="diskcache is not installed; caching disabled",
    )


class CacheService:
    """Disk-backed cache with optional TTL and graceful degradation.

    When ``diskcache`` is not importable, all operations silently degrade
    to no-ops so the application can run without a cache dependency.

    Args:
        cache_dir: Filesystem path for the cache storage directory.
        default_ttl: Default time-to-live in seconds for cached entries.
    """

    def __init__(self, cache_dir: str | Path, default_ttl: int = 3600) -> None:
        self._default_ttl = default_ttl
        self._cache: diskcache.Cache | None = None

        if _HAS_DISKCACHE:
            cache_path = Path(cache_dir)
            cache_path.mkdir(parents=True, exist_ok=True)
            self._cache = diskcache.Cache(str(cache_path))
            logger.info("cache.init", path=str(cache_path), default_ttl=default_ttl)
        else:
            logger.warning("cache.disabled", reason="diskcache not installed")

    def get(self, key: str) -> Any:  # noqa: ANN401
        """Retrieve a value from the cache.

        Args:
            key: The cache key to look up.

        Returns:
            The cached value, or ``None`` if the key is absent or the cache
            is unavailable.
        """
        if self._cache is None:
            return None

        value: object = self._cache.get(key)
        hit = value is not None
        logger.debug("cache.get", key=key, hit=hit)
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:  # noqa: ANN401
        """Store a value in the cache.

        Args:
            key: The cache key.
            value: The value to store (must be picklable).
            ttl: Time-to-live in seconds.  Defaults to the service-level
                ``default_ttl`` when ``None``.
        """
        if self._cache is None:
            return

        expire = ttl if ttl is not None else self._default_ttl
        self._cache.set(key, value, expire=expire)
        logger.debug("cache.set", key=key, ttl=expire)

    def delete(self, key: str) -> bool:
        """Remove a key from the cache.

        Args:
            key: The cache key to remove.

        Returns:
            ``True`` if the key was found and removed, ``False`` otherwise.
        """
        if self._cache is None:
            return False

        deleted: bool = self._cache.delete(key)
        logger.debug("cache.delete", key=key, deleted=deleted)
        return deleted

    def clear(self) -> None:
        """Remove all entries from the cache."""
        if self._cache is None:
            return

        self._cache.clear()
        logger.info("cache.cleared")
